import base64
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import phonenumbers
from phonenumber_field.phonenumber import PhoneNumber, to_python
from sesame.utils import get_user
from noiseworks.base32 import base32_to_bytes, bytes_to_base32
from noiseworks.forms import GDSForm
from .models import User


# Note, will return false for numbers that could be fixed or mobile e.g. US +1 numbers
def is_mobile(self):
    phone_number_type = phonenumbers.number_type(self)
    return phone_number_type == phonenumbers.PhoneNumberType.MOBILE


PhoneNumber.is_mobile = is_mobile


class SignInForm(GDSForm, forms.Form):
    username = forms.CharField(label="Email or mobile number")
    username_type = None

    def clean_username(self):
        username = self.cleaned_data["username"]
        any_valid = False

        phone_number = to_python(username)
        if phone_number.is_valid():
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
    username = forms.CharField(widget=forms.HiddenInput)
    timestamp = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_action = "/a/code"

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError("Bad request")
        user = user.pk.to_bytes(4, byteorder="big")
        return user

    def clean_code(self):
        return base32_to_bytes(self.cleaned_data["code"], length=5)

    def clean_timestamp(self):
        return base32_to_bytes(self.cleaned_data["timestamp"], length=4)

    def clean(self):
        if (
            "code" not in self.cleaned_data
            or "username" not in self.cleaned_data
            or "timestamp" not in self.cleaned_data
        ):
            return
        code = self.cleaned_data["code"]
        user = self.cleaned_data["username"]
        timestamp = self.cleaned_data["timestamp"]

        token = user + timestamp + code
        token = base64.urlsafe_b64encode(token).rstrip(b"=").decode()
        user = get_user(token)
        if user is None:
            raise ValidationError("Incorrect or expired code")
        self.user = user
