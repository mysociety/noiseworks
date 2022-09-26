import pytest
from importlib import import_module
from django.utils import timezone
from ..models import Action, ActionType, Case, Complaint, User

# We can't use the standard import expression because migrations start
# with a number.
migration_0031 = import_module(
    "cases.migrations.0033_populate_case_last_update_type",
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def action_type(db):
    ActionType.objects.create(name="An action type", common=True),


@pytest.fixture
def staff_user_1(db):
    return User.objects.create(is_staff=True, username="staffuser1")


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
        kind="diy", assigned=staff_user_1, created_by=normal_user, ward="E05009373"
    )


def test_migration_0031(action_type, case_1):
    def update_case_and_assert_last_update_type_matches(expected_type):
        case_1.last_update_type = ""
        case_1.save()
        migration_0031.update_cases(Case.objects.all())
        case_1.refresh_from_db()
        assert case_1.last_update_type == expected_type

    update_case_and_assert_last_update_type_matches("")

    action_1 = Action.objects.create(
        case=case_1,
        type=action_type,
    )
    update_case_and_assert_last_update_type_matches(Case.LastUpdateTypes.ACTION)

    Complaint.objects.create(
        case=case_1,
        happening_now=True,
    )
    update_case_and_assert_last_update_type_matches(Case.LastUpdateTypes.COMPLAINT)

    action_1.time = timezone.now()
    action_1.save()
    update_case_and_assert_last_update_type_matches(Case.LastUpdateTypes.ACTION)

    action_1.delete()
    update_case_and_assert_last_update_type_matches(Case.LastUpdateTypes.COMPLAINT)
