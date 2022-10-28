import pytest
from http import HTTPStatus

from accounts.models import User
from pytest_django.asserts import assertContains

from ..models import Case, Notification

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
        kind="diy", assigned=staff_user, created_by=normal_user, ward="E05009373"
    )


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
