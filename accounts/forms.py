import base64
import uuid

import phonenumbers
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from phonenumber_field.phonenumber import PhoneNumber, to_python
from sesame.utils import get_user

from noiseworks import cobrand
from noiseworks.base32 import base32_to_bytes
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.NOTIFY_API_KEY:
            self.fields["username"].label = "Email address"

    def clean_username(self):
        username = self.cleaned_data["username"].lower()

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


class UserForm(GDSForm, forms.ModelForm):
    is_staff = forms.BooleanField(label="Staff member", initial=True, required=False)

    def __init__(self, can_edit_staff, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_edit_staff:
            del self.fields["is_staff"]

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean(self):
        email = self.cleaned_data.get("email")
        phone = self.cleaned_data.get("phone")
        email_verified = self.cleaned_data["email_verified"]
        phone_verified = self.cleaned_data["phone_verified"]
        if email and email_verified:
            user = User.objects.filter(email=email, email_verified=True)
            user = user.exclude(pk=self.instance.pk)
            if user.exists():
                self.add_error("email", "A user with this email address already exists")
        if phone and phone_verified:
            user = User.objects.filter(phone=phone, phone_verified=True)
            user = user.exclude(pk=self.instance.pk)
            if user.exists():
                self.add_error("phone", "A user with this phone number already exists")


class EditUserForm(UserForm):
    contact_warning = forms.CharField(
        help_text="Optionally provide a warning for when contacting this person.",
        required=False,
        widget=forms.Textarea,
    )
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
            "is_staff",
            "email",
            "email_verified",
            "phone",
            "phone_verified",
            "uprn",
            "address",
            "contact_warning",
            "best_time",
            "best_method",
        )

    def __init__(self, *args, can_edit_contact_warning=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_edit_contact_warning:
            del self.fields["contact_warning"]


def get_wards_as_choices():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    return list(wards.items())


class EditStaffForm(UserForm):
    wards = forms.MultipleChoiceField(
        choices=get_wards_as_choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    principal_wards = forms.MultipleChoiceField(
        choices=get_wards_as_choices,
        help_text="When a staff member is the principal for a ward, all non-housing reports will be automatically assigned to them. Only one staff member can be the principal for a ward at a time.",
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    case_worker = forms.BooleanField(
        help_text="Case workers have more permissions for interacting with cases.",
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "is_staff",
            "email",
            "email_verified",
            "phone",
            "phone_verified",
            "case_worker",
            "wards",
            "principal_wards",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Staff must always have a name and verified email
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True
        self.fields["email_verified"].required = True
        self.fields["email_verified"].initial = True
        self.fields["email_verified"].disabled = True
        if not self.instance.pk:
            self.fields["is_staff"].disabled = True
        else:
            is_case_worker = "case_workers" in [
                g.name for g in self.instance.groups.all()
            ]
            self.fields["case_worker"].initial = is_case_worker

    def clean_principal_wards(self):
        principal_wards = self.cleaned_data.get("principal_wards", [])
        if principal_wards:
            for w in principal_wards:
                existing_principals = User.objects.filter(
                    principal_wards__contains=[w]
                ).all()
                if len(existing_principals) > 0:
                    ward_mappings = {
                        ward["gss"]: ward["name"] for ward in cobrand.api.wards()
                    }
                    raise ValidationError(
                        f"{ward_mappings[w]} already has principal {existing_principals[0].email}."
                        + " This user must be unassigned as principal before a new principal can be assigned."
                    )
        return principal_wards

    def save(self, *args, **kwargs):
        if not self.instance.username:
            self.instance.username = str(uuid.uuid4())

        # Ensure that a staff member is always assigned to a ward they are the principal of.
        principal_wards = self.cleaned_data.get("principal_wards", [])
        for w in principal_wards:
            if w not in self.cleaned_data["wards"]:
                self.cleaned_data["wards"].append(w)

        super().save(*args, **kwargs)

        case_workers = Group.objects.get(name="case_workers")
        is_case_worker = case_workers in self.instance.groups.all()
        case_worker_selected = self.cleaned_data.get("case_worker", False)
        if case_worker_selected and not is_case_worker:
            case_workers.user_set.add(self.instance)
        elif not case_worker_selected and is_case_worker:
            case_workers.user_set.remove(self.instance)


class StaffSettingsForm(GDSForm, forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "staff_email_notifications",
            "staff_web_notifications",
        )
        labels = {
            "staff_email_notifications": "Receive email notifications.",
            "staff_web_notifications": "Receive web notifications.",
        }
