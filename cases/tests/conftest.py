import re

import pytest
from django.utils.timezone import localtime, make_aware, now

from accounts.models import User

from ..models import Action, ActionType, Case


@pytest.fixture
def staff_user_1(db):
    return User.objects.create(is_staff=True, username="staffuser1")


@pytest.fixture
def staff_user_2(db):
    return User.objects.create(is_staff=True, username="staffuser2")


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
def case_1(db, staff_user_1, normal_user):
    return Case.objects.create(
        kind="diy", assigned=staff_user_1, created_by=normal_user, ward="GSS1"
    )


@pytest.fixture
def logged_action_1(case_1, staff_user_1, action_types):
    return Action.objects.create(
        type=action_types[0],
        notes="internal notes",
        case=case_1,
        created_by=staff_user_1,
    )


@pytest.fixture
def action_types(db):
    return [
        ActionType.objects.create(name="Letter sent", common=True),
        ActionType.objects.create(name="Noise witnessed"),
        ActionType.objects.create(name="Abatement Notice “Section 80” served"),
    ]


def add_time_to_log_payload(payload, time=None):
    if not time:
        time = now()
    time = localtime(time)
    date = time.date()
    payload["date_0"] = date.day
    payload["date_1"] = date.month
    payload["date_2"] = date.year
    payload["action_time"] = time.strftime("%I:%M %p")
    return payload
