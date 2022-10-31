import pytest
from http import HTTPStatus

from accounts.models import User
from pytest_django.asserts import assertContains

from ..models import ActionType, Case, Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def normal_user(db):
    return User.objects.create(
        username="normal@example.org",
        email="normal@example.org",
        email_verified=True,
        phone="+447700900123",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create(is_staff=True, username="staffuser")


@pytest.fixture
def staff_user_2(db):
    return User.objects.create(is_staff=True, username="staffuser2")


@pytest.fixture
def case(db, staff_user, normal_user):
    return Case.objects.create(
        kind="diy",
        assigned=staff_user,
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def case_2(db, staff_user, normal_user):
    return Case.objects.create(
        kind="diy",
        assigned=staff_user,
        created_by=normal_user,
        ward="E05009373",
    )


@pytest.fixture
def action_type(db):
    return ActionType.objects.create(name="Testing action type", common=True)


def test_delete_notifications(staff_user, case, db, client):
    notifications = [
        Notification.objects.create(recipient=staff_user, case=case, message="1"),
        Notification.objects.create(recipient=staff_user, case=case, message="2"),
    ]

    client.force_login(staff_user)
    response = client.post(
        "/cases/notifications/delete",
        {
            "notification_ids": [n.id for n in notifications],
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    for n in notifications:
        with pytest.raises(Notification.DoesNotExist):
            Notification.objects.get(pk=n.id)


def test_mark_notification_as_read(staff_user, case, db, client):
    notifications = [
        Notification.objects.create(recipient=staff_user, case=case, message="1"),
        Notification.objects.create(recipient=staff_user, case=case, message="2"),
    ]

    client.force_login(staff_user)
    response = client.post(
        "/cases/notifications/read",
        {
            "notification_ids": [n.id for n in notifications],
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    for n in notifications:
        n.refresh_from_db()
        assert n.read


def test_consume_notification(staff_user, staff_user_2, case, db, client):
    notification = Notification.objects.create(
        recipient=staff_user, case=case, message="test consume"
    )

    client.force_login(staff_user_2)
    response = client.get(f"/cases/notifications/{notification.id}")
    assert response.status_code == HTTPStatus.FORBIDDEN

    client.force_login(staff_user)
    response = client.get(f"/cases/notifications/{notification.id}")
    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == case.get_absolute_url()
    notification.refresh_from_db()
    assert notification.read


def test_notification_list(staff_user, case, db, client):
    notifications = [
        Notification.objects.create(
            recipient=staff_user, case=case, message="notification 1"
        ),
        Notification.objects.create(
            recipient=staff_user, case=case, message="notification 2"
        ),
    ]

    client.force_login(staff_user)
    response = client.get("/cases/notifications")
    assert response.status_code == HTTPStatus.OK
    for n in notifications:
        assertContains(response, n.message)


def test_notify_case_followers(case, staff_user, staff_user_2):
    case.followers.set([staff_user, staff_user_2])
    case.notify_followers("test", triggered_by=staff_user)
    assert len(staff_user.notifications.all()) == 0
    assert len(staff_user_2.notifications.all()) == 1


def test_logged_action_notifications(
    case, staff_user, staff_user_2, action_type, client
):
    case.followers.set([staff_user])

    def _log_action_and_check_for_notification(
        triggerer, type_, expected_recipient, expected_message
    ):
        client.force_login(triggerer)
        client.post(
            f"/cases/{case.id}/log",
            {
                "notes": "notes",
                "type": type_.id,
                "in_the_past": False,
            },
            follow=True,
        )
        matching = Notification.objects.filter(
            triggered_by=triggerer,
            recipient=expected_recipient,
            message=expected_message,
            case=case,
        )
        assert len(matching) == 1, f"No notification for {expected_message}"

    _log_action_and_check_for_notification(
        staff_user_2,
        action_type,
        staff_user,
        f"Added '{action_type}'.",
    )

    _log_action_and_check_for_notification(
        staff_user_2,
        ActionType.case_closed,
        staff_user,
        "Closed case.",
    )

    _log_action_and_check_for_notification(
        staff_user_2,
        ActionType.case_reopened,
        staff_user,
        "Opened case.",
    )


def test_case_assigned_notifications(case, staff_user, staff_user_2, client):
    case.followers.set([staff_user])
    client.force_login(staff_user_2)
    client.post(
        f"/cases/{case.id}/reassign",
        {
            "assigned": staff_user.id,
        },
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message=f"Assigned {staff_user}.",
        case=case,
    )
    assert len(matching) == 1


def test_case_review_date_changed_notifications(case, staff_user, staff_user_2, client):
    case.followers.set([staff_user])
    client.force_login(staff_user_2)
    client.post(
        f"/cases/{case.id}/edit-review-date",
        {
            "has_review_date": False,
        },
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Set no review date.",
        case=case,
    )
    assert len(matching) == 1
    client.post(
        f"/cases/{case.id}/edit-review-date",
        {
            "has_review_date": True,
            "review_date_0": 1,
            "review_date_1": 2,
            "review_date_2": 2022,
        },
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Set review date to 2022-02-01.",
        case=case,
    )
    assert len(matching) == 1


def test_case_priority_changed_notifications(case, staff_user, staff_user_2, client):
    case.followers.set([staff_user])

    def _set_priority_and_check_for_notification(
        triggerer, priority, expected_recipient, expected_message
    ):
        client.force_login(triggerer)
        client.post(
            f"/cases/{case.id}/priority",
            {
                "priority": priority,
            },
        )
        matching = Notification.objects.filter(
            triggered_by=triggerer,
            recipient=expected_recipient,
            message=expected_message,
            case=case,
        )
        assert len(matching) == 1

    _set_priority_and_check_for_notification(
        staff_user_2,
        True,
        staff_user,
        "Marked as priority.",
    )

    _set_priority_and_check_for_notification(
        staff_user_2,
        False,
        staff_user,
        "Marked as not priority.",
    )


def test_case_kind_changed_notifications(case, staff_user, staff_user_2, client):
    case.followers.set([staff_user])

    def _set_kind_and_check_for_notification(
        triggerer, kind, expected_recipient, expected_message
    ):
        client.force_login(triggerer)
        client.post(
            f"/cases/{case.id}/edit-kind",
            {
                "kind": kind,
            },
        )
        matching = Notification.objects.filter(
            triggered_by=triggerer,
            recipient=expected_recipient,
            message=expected_message,
            case=case,
        )
        assert len(matching) == 1

    _set_kind_and_check_for_notification(
        staff_user_2,
        "diy",
        staff_user,
        "Set kind to diy.",
    )


def test_case_location_changed_notifications(
    case, staff_user, staff_user_2, client, address_lookup
):
    case.followers.set([staff_user])
    client.force_login(staff_user_2)
    client.post(
        f"/cases/{case.id}/edit-location",
        {
            "postcode": "E8 3DY",
            "addresses": "10008315925",
            "where": "residence",
        },
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Changed location.",
        case=case,
    )
    assert len(matching) == 1


def test_case_removed_perpetrator_notifications(
    case, staff_user, staff_user_2, normal_user, client
):
    case.perpetrators.set([normal_user])
    case.followers.set([staff_user])
    client.force_login(staff_user_2)
    client.post(
        f"/cases/{case.id}/remove-perpetrator/{normal_user.id}",
        {},
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Removed perpetrator.",
        case=case,
    )
    assert len(matching) == 1


def test_case_add_perpetrator_notifications(case, staff_user, staff_user_2, client):
    case.followers.set([staff_user])
    client.force_login(staff_user_2)
    client.get(f"/cases/{case.id}/perpetrator/add", follow=True)
    client.post(
        f"/cases/{case.id}/perpetrator/add/user_search",
        {
            f"perpetrator_wizard_{case.id}-current_step": "user_pick",
            "user_search-search": "search",
        },
        follow=True,
    )
    client.post(
        f"/cases/{case.id}/perpetrator/add/user_pick",
        {
            f"perpetrator_wizard_{case.id}-current_step": "user_pick",
            "user_pick-user": 0,
            "user_pick-first_name": "test",
            "user_pick-last_name": "test",
            "user_pick-email": "test@test.com",
        },
        follow=True,
    )
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Added perpetrator.",
        case=case,
    )
    assert len(matching) == 1


def test_case_merged_notifications(case, case_2, staff_user, staff_user_2, client):
    case.followers.set([staff_user])
    case_2.followers.set([staff_user])

    client.force_login(staff_user_2)
    client.get(f"/cases/{case.id}/merge")
    client.post(
        f"/cases/{case_2.id}/merge",
        {
            "dupe": True,
        },
    )

    expected_message = f"Merged case #{case.id} into case #{case_2.id}."
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message=expected_message,
        case=case,
    )
    assert len(matching) == 1

    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message=expected_message,
        case=case_2,
    )
    assert len(matching) == 1


def test_case_unmerged_notifications(case, case_2, staff_user, staff_user_2, client):
    case.followers.set([staff_user])
    case_2.followers.set([staff_user])

    client.force_login(staff_user_2)
    client.get(f"/cases/{case.id}/merge")
    client.post(
        f"/cases/{case_2.id}/merge",
        {
            "dupe": True,
        },
    )
    client.post(f"/cases/{case.id}/unmerge")

    expected_message = f"Unmerged case #{case.id} from case #{case_2.id}."
    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message=expected_message,
        case=case,
    )
    assert len(matching) == 1

    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message=expected_message,
        case=case_2,
    )
    assert len(matching) == 1


def test_case_recurrence_notifications(
    case, staff_user, staff_user_2, client, settings
):
    case.followers.set([staff_user])
    # Handle send staff email attempt.
    settings.COBRAND_SETTINGS["staff_destination"] = {
        "housing": "someaddress@email.com"
    }

    client.force_login(staff_user_2)
    client.get(f"/cases/{case.id}/complaint/add", follow=True)
    response = client.post(
        f"/cases/{case.id}/complaint/add/isitnow",
        {
            f"recurrence_wizard_{case.id}-current_step": "isitnow",
            "isitnow-happening_now": 1,
        },
        follow=True,
    )
    response = client.post(
        f"/cases/{case.id}/complaint/add/isnow",
        {
            f"recurrence_wizard_{case.id}-current_step": "isnow",
            "isnow-start_date": "today",
            "isnow-start_time": "1pm",
        },
        follow=True,
    )
    response = client.post(
        f"/cases/{case.id}/complaint/add/rooms",
        {
            f"recurrence_wizard_{case.id}-current_step": "rooms",
            "rooms-rooms": "rooms",
        },
        follow=True,
    )
    resonse = client.post(
        f"/cases/{case.id}/complaint/add/describe",
        {
            f"recurrence_wizard_{case.id}-current_step": "describe",
            "describe-description": "description",
        },
        follow=True,
    )
    response = client.post(
        f"/cases/{case.id}/complaint/add/effect",
        {
            f"recurrence_wizard_{case.id}-current_step": "effect",
            "effect-effect": "effect",
        },
        follow=True,
    )
    response = client.post(
        f"/cases/{case.id}/complaint/add/user_search",
        {
            f"recurrence_wizard_{case.id}-current_step": "user_search",
            "user_search-search": "search",
        },
        follow=True,
    )
    response = client.post(
        f"/cases/{case.id}/complaint/add/user_pick",
        {
            f"recurrence_wizard_{case.id}-current_step": "user_pick",
            "user_pick-user": 0,
            "user_pick-first_name": "test",
            "user_pick-last_name": "test",
            "user_pick-email": "test@test.com",
        },
        follow=True,
    )
    client.post(
        f"/cases/{case.id}/complaint/add/summary",
        {
            f"recurrence_wizard_{case.id}-current_step": "summary",
            "summary-true_statement": "on",
        },
        follow=True,
    )

    matching = Notification.objects.filter(
        triggered_by=staff_user_2,
        recipient=staff_user,
        message="Recurrence added.",
        case=case,
    )
    assert len(matching) == 1
