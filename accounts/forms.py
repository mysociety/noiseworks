import base64
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import phonenumbers
from phonenumber_field.phonenumber import PhoneNumber, to_python
from sesame.utils import get_user
from noiseworks.base32 import base32_to_bytes, bytes_to_base32
from noiseworks.forms import GDSForm
from noiseworks import cobrand
from .models import User


# Note, will return false for numbers that could be fixed or mobile e.g. US +1 numbers
def is_mobile(self):
    phone_number_type = phonenumbers.number_type(self)
    return phone_number_type == phonenumbers.PhoneNumberType.MOBILE


PhoneNumber.is_mobile = is_mobile


class SignInForm(GDSForm, forms.Form):
    username = forms.CharField(label="Email or mobile number")
    username_type = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.NOTIFY_API_KEY:
            self.fields["username"].label = "Email address"

    def clean_username(self):
        username = self.cleaned_data["username"].lower()
        any_valid = False

        phone_number = to_python(username)
        if phone_number.is_valid() and settings.NOTIFY_API_KEY:
            if phone_number.is_mobile():
                self.cleaned_data["username_type"] = "phone"
                return username
            else:
                raise ValidationError("Please provide a mobile number")

        # Not a phone number, assume email
        validate_email(username)

        self.cleaned_data["username_type"] = "email"
        return username


class CodeForm(GDSForm, forms.Form):
    code = forms.CharField(label="Token")
    user_id = forms.IntegerField(widget=forms.HiddenInput)
    timestamp = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_action = "/a/code"

    def clean_user_id(self):
        user_id = self.cleaned_data["user_id"]
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError("Bad request")
        user = user.pk.to_bytes(4, byteorder="big")
        return user

    def clean_code(self):
        try:
            code = self.cleaned_data["code"].lower()
            return base32_to_bytes(code, length=5)
        except (OverflowError, ValueError):
            return b""

    def clean_timestamp(self):
        try:
            return base32_to_bytes(self.cleaned_data["timestamp"], length=4)
        except (OverflowError, ValueError):
            return b""

    def clean(self):
        if (
            "code" not in self.cleaned_data
            or "user_id" not in self.cleaned_data
            or "timestamp" not in self.cleaned_data
        ):
            return
        code = self.cleaned_data["code"]
        user = self.cleaned_data["user_id"]
        timestamp = self.cleaned_data["timestamp"]

        token = user + timestamp + code
        token = base64.urlsafe_b64encode(token).rstrip(b"=").decode()
        user = get_user(token)
        if user is None:
            raise ValidationError("Incorrect or expired code")
        self.user = user


class EditUserForm(GDSForm, forms.ModelForm):
    best_time = forms.MultipleChoiceField(
        choices=User.BEST_TIME_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    best_method = forms.ChoiceField(
        choices=User.BEST_METHOD_CHOICES + [("", "Unknown")],
        widget=forms.RadioSelect,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "email_verified",
            "phone",
            "phone_verified",
            "uprn",
            "address",
            "best_time",
            "best_method",
        )


def get_wards():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    return list(wards.items())


class EditStaffForm(GDSForm, forms.ModelForm):
    wards = forms.MultipleChoiceField(
        choices=get_wards, widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "email_verified",
            "phone",
            "phone_verified",
            "wards",
        )
