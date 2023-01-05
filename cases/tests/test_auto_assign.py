import pytest
from django.core import mail

from accounts.models import User

from ..models import Case
from ..signals import new_case_reported

pytestmark = pytest.mark.django_db


@pytest.fixture
def ward_gss():
    return "E05009372"


@pytest.fixture
def staff_user(db, ward_gss):
    return User.objects.create(
        is_staff=True,
        username="staffuser1",
        email="staff@staff.com",
        wards=[ward_gss],
        principal_wards=[ward_gss],
        staff_email_notifications=True,
    )


def test_staff_auto_assigned_case_when_ward_principal_and_not_estate(
    staff_user, ward_gss
):
    c = Case.objects.create(ward=ward_gss, estate="n")
    new_case_reported.send(sender=None, case=c, case_absolute_url="some_absolute_url")
    c.refresh_from_db()
    assert c.assigned == staff_user
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [staff_user.email]
    assert sent.subject == "You have been assigned"
