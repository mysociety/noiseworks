from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import phonenumbers
from phonenumber_field.phonenumber import PhoneNumber, to_python
from noiseworks.forms import GDSForm


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
