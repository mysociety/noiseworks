import datetime

import pytest
from django.contrib.gis.geos import Point
from django.utils.timezone import now
from pytest_django.asserts import assertContains, assertNotContains

from ..models import Action, ActionType, Case, MergeRecord, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def case(db):
    return Case.objects.create(
        kind="diy",
        point=Point(470267, 122766),
        uprn="123456",
        location_cache="Flat 4, 2 Example Road, E8 2DP",
        estate="?",
    )


@pytest.fixture
def same_case(db):
    return Case.objects.create(kind="diy", location_cache="Identical case", estate="?")


@pytest.fixture
def merged_case_setup(db):
    c1 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Combined case",
        estate="?",
        point=Point(470267, 122766),
    )
    c2 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Merged case",
        estate="?",
        point=Point(470267, 122766),
    )
    c2.merge_into(c1)
    c2.save()
    return (c1, c2)


@pytest.fixture
def already_merged_case(db, merged_case_setup):
    _, c = merged_case_setup
    return c


@pytest.fixture
def cases(db):
    return [
        Case.objects.create(
            kind="diy",
            point=Point(470267, 122766),
            uprn="123456",
            location_cache="Same UPRN",
            estate="?",
        ),
        Case.objects.create(
            kind="diy",
            point=Point(470267, 122767),
            location_cache="Within 500m",
            estate="?",
        ),
        Case.objects.create(
            kind="diy",
            point=Point(470267, 123267),
            location_cache="Too far away",
            estate="?",
        ),
    ]


@pytest.fixture
def action_types(db):
    return [
        ActionType.objects.create(name="Letter sent", common=True),
        ActionType.objects.create(name="Noise witnessed"),
        ActionType.objects.create(name="Abatement Notice “Section 80” served"),
    ]


def test_merge_no_location(admin_client, same_case):
    admin_client.get(f"/cases/{same_case.id}/merge")


def test_merge_stop_not_started(admin_client, case):
    response = admin_client.post(f"/cases/{case.id}/merge", {"stop": 1}, follow=True)
    assertNotContains(response, "We have forgotten your current merging.")


def test_merging_cases_list(admin_client, case, cases, already_merged_case):
    response = admin_client.post(f"/cases/{case.id}/merge")
    assertContains(response, "Select a case to merge into")
    assertContains(response, "Same UPRN")
    assertContains(response, "Within 500m")
    assertContains(response, "Combined case")
    assertNotContains(response, "Too far away")
    assertNotContains(response, "Merged case")
    response = admin_client.get(f"/cases/{already_merged_case.id}")
    assertNotContains(
        response,
        f"Merge #{case.id} (DIY at Flat 4, 2 Example Road, E8 2DP) into this case",
    )


def test_merging_case_stopping(admin_client, case, same_case):
    response = admin_client.post(f"/cases/{case.id}/merge")
    response = admin_client.get(f"/cases/{same_case.id}")
    assertContains(
        response,
        f"Merge #{case.id} (DIY at Flat 4, 2 Example Road, E8 2DP) into this case",
    )
    response = admin_client.post(f"/cases/{case.id}/merge", {"stop": 1}, follow=True)
    assertContains(response, "We have forgotten your current merging.")
    assertNotContains(
        response,
        f"Merge #{case.id} (DIY at Flat 4, 2 Example Road, E8 2DP) into this case",
    )


def test_merging_cases(admin_client, same_case, case, action_types):
    response = admin_client.post(f"/cases/{case.id}/merge")
    response = admin_client.post(
        f"/cases/{same_case.id}/merge", {"dupe": 1}, follow=True
    )
    assertContains(response, "has been merged into")

    # Check showing list of cases and last update is not 'editing'
    response = admin_client.get("/cases")
    assertNotContains(response, "edited case details")

    Action.objects.create(case=same_case, notes="Internal note", type=action_types[1])

    response = admin_client.get(f"/cases/{case.id}")
    assertContains(response, "This case has been merged into")
    assertContains(response, "Noise witnessed")


def test_case_actions_reversed_only_inclues_actions_from_mergee_after_merge_time(
    merged_case_setup,
):
    """
    If case A is merged into case B, we expect case A's actions_reversed to only inlcude
    case B actions that have a time after the time of the merge action, regardless of when
    these actions are created.
    """
    into, merged = merged_case_setup
    before_the_merge = now() - datetime.timedelta(days=1)
    action_created_for_past_event = Action.objects.create(
        case=into, time=before_the_merge
    )
    merged_actions = merged.actions_reversed
    assert len(merged_actions) == 0
