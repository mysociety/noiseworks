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
        assignable_staff = User.objects.filter(
            Q(is_active=True)
            & (
                Q(user_permissions__codename="get_assigned")
                | Q(groups__permissions__codename="get_assigned")
            )
        )
        ward_staff = []
        other_staff = []
        for user in assignable_staff:
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
        help_text=(
            "You can upload documents by adding a link or links to shared documents"
        ),
    )


def combine_date_and_time(date, action_time):
    combined_unaware = datetime.combine(
        date,
        action_time,
    )
    return make_aware(combined_unaware)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BaseActionForm(GDSForm, forms.ModelForm):
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
    files = MultipleFileField(label="Attachments", required=False)

    def __init__(self, *args, case=None, **kwargs):
        self.case = case
        super().__init__(*args, **kwargs)

    def clean_files(self):
        files = self.files.getlist("files")
        upload_size_bytes = 0
        for f in files:
            upload_size_bytes += f.size
            if len(f.name) > 128:
                raise ValidationError(f'Filename {f.name} too long, please rename')
        remaining_bytes = self.case.file_storage_remaining_bytes
        if upload_size_bytes > remaining_bytes:
            human_readable_remaining_space = naturalsize(remaining_bytes)
            raise ValidationError(
                f"There is only {human_readable_remaining_space} left for attachments"
                " on this case. You can store files to the Google Drive and link to"
                " them in action notes instead."
            )

    def clean(self):
        in_the_past = self.cleaned_data.get("in_the_past", None)
        date = self.cleaned_data.get("date", None)
        action_time = self.cleaned_data.get("action_time", None)

        if in_the_past:
            if date and action_time:
                _time = combine_date_and_time(date, action_time)
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
            self.instance.time = combine_date_and_time(date, action_time)
        else:
            self.instance.time = now()

        super().save()


class LogActionForm(BaseActionForm):
    submit_text = "Log action"

    class Meta:
        model = Action
        fields = ["type", "notes"]

    type = forms.ChoiceField(widget=forms.RadioSelect, required=True)

    notes = action_notes_field()

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)

        action_types = ActionType.objects.exclude(visibility="internal").order_by(
            "name"
        )
        common = []
        other = []
        for typ in action_types:
            if typ == ActionType.visit:
                continue
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
                HTML('{% include "cases/_action_form_log_visit_link.html" %}'),
                "notes",
                "files",
                "in_the_past",
                "date",
                "action_time",
                HTML('{% include "cases/_action_form_files_too_big_prompt.html" %}'),
                HTML('{% include "cases/_action_form_cant_upload_prompt.html" %}'),
                HTML('{% include "cases/_action_form_close_prompt.html" %}'),
            )
        )

    def clean_type(self):
        type = self.cleaned_data["type"]
        type = ActionType.objects.get(id=type)
        return type

    def clean(self):
        cleaned_data = super().clean()
        in_the_past = self.cleaned_data.get("in_the_past", None)
        _type = self.cleaned_data.get("type", None)
        if in_the_past and _type in [ActionType.case_closed, ActionType.case_reopened]:
            raise ValidationError(
                f"You can’t {'close' if _type==ActionType.case_closed else 'reopen'} a"
                " case in the past."
            )
        return cleaned_data


class LogVisitForm(BaseActionForm):
    class Meta:
        model = Action
        fields = []

    submit_text = "Log visit"

    weather_conditions = forms.CharField(
        label="Weather conditions",
        help_text=(
            "What were the weather conditions? Could your listening skills have been"
            " affected by wind or rain?"
        ),
        required=False,
    )
    parked_arrival_time = forms.CharField(
        label="Arrival time",
        help_text="What time did you arrive (park up) at the location?",
        required=False,
    )
    first_impressions = forms.CharField(
        label="First impressions",
        help_text=(
            "What were your first impressions when getting out of the car? Were there"
            " people hanging around outside the location?"
        ),
        required=False,
    )
    sound_from_parked = forms.CharField(
        label="Sound from parked location",
        help_text="What could you hear from where you parked?",
        required=False,
    )
    complainants_property_arrival_time = forms.CharField(
        label="Complainant's property arrival time",
        help_text="What time did you arrive at the complainant's property?",
        required=False,
    )
    went_inside = forms.ChoiceField(
        label="Entered complainant's property",
        help_text="Did you go inside the complainant's property?",
        choices=[
            ("Yes", "Yes"),
            ("No", "No"),
        ],
        initial="No",
        required=False,
    )
    distance_from_complainants_property = forms.CharField(
        label="Distance from complainant's property",
        help_text="How far were you from the complainant's property?",
        required=False,
    )
    room_affected = forms.CharField(
        label="Room affected",
        help_text="Which room is affected by the noise? Is it furnished?",
        required=False,
    )
    doors_and_windows = forms.CharField(
        label="Doors and windows open",
        help_text=(
            "Were any doors or windows open? Could they have been closed to prevent the"
            " noise?"
        ),
        required=False,
    )
    sound_at_complainants_property = forms.CharField(
        label="Sound at complainant's property",
        help_text=(
            "Apply your listening skills and describe in detail what you can hear. What"
            " type of music or noise could you hear? Was it continuous or intermittent?"
            " If it was music, do you recognise it or can you hear the lyrics? Did the"
            " track change at all?"
        ),
        required=False,
    )
    time_spent_listening = forms.CharField(
        label="Time spent listening",
        help_text=(
            "How long did you spend listening to the noise at the complainant's"
            " property? Remember it should be a minimum of 20 minutes."
        ),
        required=False,
    )
    not_statutory_nuisance_reasoning = forms.CharField(
        label="Reasoning if not statutory nuisance",
        help_text=(
            "If you heard the noise but did not deem it a statutory nuisance, explain"
            " your reasons why."
        ),
        required=False,
    )
    time_complainants_property_left = forms.CharField(
        label="Time complainant's property left",
        help_text="What time did you leave the complainant's property?",
        required=False,
    )
    additional_notes = forms.CharField(
        label="Additional notes",
        widget=forms.Textarea,
        required=False,
    )

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, case=case, **kwargs)
        self.helper.layout = Layout(
            Fieldset(
                "weather_conditions",
                "parked_arrival_time",
                "first_impressions",
                "sound_from_parked",
                "complainants_property_arrival_time",
                "went_inside",
                HTML('<div name="hide-when-inside">'),
                "distance_from_complainants_property",
                HTML("</div>"),
                HTML('<div name="show-when-inside">'),
                "room_affected",
                "doors_and_windows",
                HTML("</div>"),
                "sound_at_complainants_property",
                "time_spent_listening",
                "not_statutory_nuisance_reasoning",
                "time_complainants_property_left",
                "additional_notes",
                "files",
                "in_the_past",
                "date",
                "action_time",
                HTML('{% include "cases/_action_form_files_too_big_prompt.html" %}'),
                HTML('{% include "cases/_action_form_cant_upload_prompt.html" %}'),
            )
        )

    def _assemble_prompt_responses(self):
        assembled = ""
        prompt_field_names = [
            "weather_conditions",
            "parked_arrival_time",
            "first_impressions",
            "sound_from_parked",
            "complainants_property_arrival_time",
            "went_inside",
            "distance_from_complainants_property",
            "room_affected",
            "doors_and_windows",
            "sound_at_complainants_property",
            "time_spent_listening",
            "not_statutory_nuisance_reasoning",
            "time_complainants_property_left",
            "additional_notes",
        ]
        for name in prompt_field_names:
            data = self.cleaned_data.get(name, None)
            if data:
                assembled += f"{self.fields[name].label}:\n{data}\n\n"
        return assembled

    def save(self):
        self.instance.type = ActionType.visit
        self.instance.notes = self._assemble_prompt_responses()
        super().save()


class EditActionForm(GDSForm, forms.ModelForm):
    submit_text = "Edit logged action"

    class Meta:
        model = Action
        fields = ["notes"]

    notes = action_notes_field()

    def save(self):
        self.instance.notes_last_edit_time = now()
        super().save()


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
