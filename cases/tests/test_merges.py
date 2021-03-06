import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.contrib.gis.geos import Point
from accounts.models import User
from ..models import Case, ActionType, Action

pytestmark = pytest.mark.django_db


@pytest.fixture
def case(db):
    return Case.objects.create(
        kind="diy",
        point=Point(470267, 122766),
        uprn="123456",
        location_cache="Flat 4, 2 Example Road, E8 2DP",
    )


@pytest.fixture
def same_case(db):
    return Case.objects.create(kind="diy", location_cache="Identical case")


@pytest.fixture
def already_merged_case(db):
    c1 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Combined case",
        point=Point(470267, 122766),
    )
    c2 = Case.objects.create(
        kind="diy",
        ward="E05009373",
        location_cache="Merged case",
        point=Point(470267, 122766),
    )
    Action.objects.create(case=c1, case_old=c2)
    return c2


@pytest.fixture
def cases(db):
    return [
        Case.objects.create(
            kind="diy",
            point=Point(470267, 122766),
            uprn="123456",
            location_cache="Same UPRN",
        ),
        Case.objects.create(
            kind="diy",
            point=Point(470267, 122767),
            location_cache="Within 500m",
        ),
        Case.objects.create(
            kind="diy",
            point=Point(470267, 123267),
            location_cache="Too far away",
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


def test_merging_cases(admin_client, case, same_case, action_types):
    response = admin_client.post(f"/cases/{case.id}/merge")
    response = admin_client.post(
        f"/cases/{same_case.id}/merge", {"dupe": 1}, follow=True
    )
    assertContains(response, "has been merged into")

    a = Action.objects.create(
        case=same_case, notes="Internal note", type=action_types[1]
    )

    response = admin_client.get(f"/cases/{case.id}")
    assertContains(response, "This case has been merged into")
    assertContains(response, "Noise witnessed")
