import pytest
from .models import User

pytestmark = pytest.mark.django_db


def test_create_phone_user():
    user = User.objects.create_user(is_staff=True, username="0121 496 0000")
    assert user.phone_verified
    assert not user.email_verified
