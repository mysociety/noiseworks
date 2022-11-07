from datetime import datetime
import re

from crispy_forms_gds.choices import Choice
from crispy_forms_gds.fields import DateInputField
from crispy_forms_gds.layout import Fieldset, Layout, HTML
from django import forms
from django.db.models import Q
from django.utils.timezone import make_aware, now
from django.core.exceptions import ValidationError
from humanize import naturalsize

from accounts.models import User
from noiseworks import cobrand
from noiseworks.forms import GDSForm

from ..models import Action, ActionType, Case
from .widgets import TimeWidget


class ReassignForm(GDSForm, forms.ModelForm):
    """Reassign a case to another staff user"""

    submit_text = "Reassign"

    class Meta:
        model = Case
        fields = ["assigned"]

    assigned = forms.ChoiceField(
        label="Reassign to",
        widget=forms.RadioSelect,
        help_text="This ward’s team members shown first",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_assigned = self.instance.assigned
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        ward_staff = []
        other_staff = []
        for user in staff_users:
            user_str = f"{user} ({user.get_wards_display()})"
            if user.wards and self.instance.ward in user.wards:
                ward_staff.append(Choice(user.id, user_str))
            else:
                other_staff.append(Choice(user.id, user_str))
        if ward_staff:
            ward_staff[-1].divider = "or"
        self.fields["assigned"].choices = ward_staff + other_staff

        self.helper.legend_size = "xl"

    def clean_assigned(self):
        assigned = self.cleaned_data["assigned"]
        assigned = User.objects.get(id=assigned)
        return assigned


class FollowersForm(GDSForm, forms.ModelForm):
    """Change followers on a case"""

    submit_text = "Update"

    class Meta:
        model = Case
        fields = ["followers"]
        widgets = {"followers": forms.CheckboxSelectMultiple}
        help_texts = {"followers": "This ward’s team members shown first"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        staff_that_can_follow = User.objects.filter(
            Q(is_active=True)
            & (
                Q(user_permissions__codename="follow")
                | Q(groups__permissions__codename="follow")
            )
        )
        ward_staff = []
        other_staff = []
        for user in staff_that_can_follow:
            if user.wards and self.instance.ward in user.wards:
                ward_staff.append(Choice(user.id, user))
            else:
                other_staff.append(Choice(user.id, user))
        self.fields["followers"].choices = ward_staff + other_staff
        self.fields["followers"].required = False

        self.helper.legend_size = "xl"

    def save(self):
        super().save()
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        Action.objects.create(case=self.instance, type=typ, notes="Updated followers")


class KindForm(GDSForm, forms.ModelForm):
    """Update the kind of case"""

    submit_text = "Update"

    class Meta:
        model = Case
        fields = ["kind", "kind_other"]

    kind = forms.ChoiceField(
        label="Type",
        widget=forms.RadioSelect,
        choices=Case.KIND_CHOICES,
    )


def action_notes_field():
    return forms.CharField(
        widget=forms.Textarea,
        label="Internal notes",
        help_text="You can upload documents by adding a link or links to shared documents",
    )


class LogActionForm(GDSForm, forms.ModelForm):
    submit_text = "Log action"

    class Meta:
        model = Action
        fields = ["type", "notes"]

    type = forms.ChoiceField(widget=forms.RadioSelect, required=True)
    notes = action_notes_field()

    in_the_past = forms.BooleanField(
        label="This happened in the past",
        required=False,
    )
    date = DateInputField(
        label="When did it happen?",
        required=False,
    )
    action_time = forms.TimeField(
        widget=TimeWidget,
        label="Time",
        help_text="For example, 9pm or 2:30am – enter 12am for midnight",
        required=False,
    )

    files = forms.FileField(
        label="Attachments",
        widget=forms.ClearableFileInput(attrs={"multiple": True}),
        required=False,
    )

    def __init__(self, *args, case=None, **kwargs):
        self.case = case
        super().__init__(*args, **kwargs)

        action_types = ActionType.objects.exclude(visibility="internal").order_by(
            "name"
        )
        common = []
        other = []
        for typ in action_types:
            if typ.common:
                common.append(Choice(typ.id, typ))
            else:
                other.append(Choice(typ.id, typ))
        if common:
            common[-1].divider = "or"
        self.fields["type"].choices = common + other

        self.helper.layout = Layout(
            Fieldset(
                "type",
                "notes",
                "in_the_past",
                "date",
                "action_time",
                "files",
                HTML('{% include "cases/_action_form_files_too_big_prompt.html" %}'),
                HTML('{% include "cases/_action_form_cant_upload_prompt.html" %}'),
                HTML('{% include "cases/_action_form_close_prompt.html" %}'),
            )
        )

    def clean_type(self):
        type = self.cleaned_data["type"]
        type = ActionType.objects.get(id=type)
        return type

    def clean_files(self):
        files = self.files.getlist("files")
        upload_size_bytes = sum([f.size for f in files])
        remaining_bytes = self.case.file_storage_remaining_bytes
        if upload_size_bytes > remaining_bytes:
            human_readable_remaining_space = naturalsize(remaining_bytes)
            raise ValidationError(
                f"There is only {human_readable_remaining_space} left for attachments on this case. "
                "You can store files to the Google Drive and link to them in action notes instead."
            )

    def clean(self):
        in_the_past = self.cleaned_data.get("in_the_past", None)
        _type = self.cleaned_data.get("type", None)
        date = self.cleaned_data.get("date", None)
        action_time = self.cleaned_data.get("action_time", None)

        if in_the_past:
            if _type and _type in [ActionType.case_closed, ActionType.case_reopened]:
                raise ValidationError(
                    f"You can’t {'close' if _type==ActionType.case_closed else 'reopen'} a case in the past."
                )

            if date and action_time:
                _time = self._get_combined_time(date, action_time)
                if _time > now():
                    raise ValidationError(
                        "The time of the action can’t be in the future."
                    )
            else:
                raise ValidationError(
                    "A date and time must be specified for actions in the past."
                )

        return self.cleaned_data

    def save(self):
        self.instance.case = self.case

        in_the_past = self.cleaned_data.get("in_the_past", None)
        date = self.cleaned_data.get("date", None)
        action_time = self.cleaned_data.get("action_time", None)
        if in_the_past and date and action_time:
            self.instance.time = self._get_combined_time(date, action_time)
        else:
            self.instance.time = now()

        super().save()

    def _get_combined_time(self, date, action_time):
        combined_unaware = datetime.combine(
            date,
            action_time,
        )
        return make_aware(combined_unaware)


class EditActionForm(GDSForm, forms.ModelForm):
    submit_text = "Edit logged action"

    class Meta:
        model = Action
        fields = ["notes"]

    notes = action_notes_field()


class LocationForm(GDSForm, forms.ModelForm):
    """Update the location of case"""

    submit_text = "Update"

    radius = forms.TypedChoiceField(
        coerce=int,
        required=False,
        empty_value=None,
        choices=(
            ("", "----"),
            (30, "Small (100ft / 30m)"),
            (180, "Medium (200yd / 180m)"),
            (800, "Large (half a mile / 800m)"),
        ),
    )

    postcode = forms.CharField(max_length=8, required=False)
    addresses = forms.ChoiceField(
        required=False, widget=forms.RadioSelect, label="Address"
    )

    class Meta:
        model = Case
        fields = ["point", "radius", "uprn", "where", "estate"]
        widgets = {"point": forms.HiddenInput, "uprn": forms.HiddenInput}

    def address_choices(self, pc):
        addresses = cobrand.api.addresses_for_postcode(pc)
        if "error" in addresses:
            raise ValidationError("We could not recognise that postcode")
        choices = []
        for addr in addresses["addresses"]:
            choices.append((addr["value"], addr["label"]))
        return choices

    def clean(self):
        if self.cleaned_data.get("addresses"):
            self.cleaned_data["radius"] = None
            self.cleaned_data["uprn"] = self.cleaned_data["addresses"]
            self.instance.location_cache = ""
            self.instance.estate = ""
            del self.cleaned_data["addresses"]
        if self.cleaned_data.get("radius"):
            self.cleaned_data["uprn"] = ""
            self.instance.location_cache = ""
            self.instance.estate = ""
        return self.cleaned_data

    def clean_addresses(self):
        uprn = self.cleaned_data["addresses"]
        if re.match("[0-9]+$", uprn):
            return uprn
        if self.fields["addresses"].choices:
            raise forms.ValidationError("Please select one of the addresses below")
        return uprn

    def clean_postcode(self):
        pc = self.cleaned_data["postcode"]
        if pc:
            self.fields["addresses"].choices = self.address_choices(pc)
        return pc

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Submitting the form with an address selected
        if "addresses" in self.data and "postcode" in self.data:
            choices = self.address_choices(self.data["postcode"])
            self.fields["addresses"].choices = choices


class ReviewDateForm(GDSForm, forms.ModelForm):
    submit_text = "Update"

    class Meta:
        model = Case
        fields = ["review_date"]

    has_review_date = forms.BooleanField(
        label="This case has a review date", required=False
    )
    review_date = DateInputField(label="", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper.layout = Layout(
            Fieldset(
                "has_review_date",
                "review_date",
            )
        )

    def save(self):
        m = super().save(commit=False)
        if not self.cleaned_data["has_review_date"]:
            m.review_date = None
        m.save()
        return m


class PriorityForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["priority"]
        widgets = {"priority": forms.HiddenInput}
