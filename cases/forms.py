import re
from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User
from .models import Case, Action, ActionType
from crispy_forms_gds.choices import Choice
from noiseworks import cobrand
from noiseworks.forms import GDSForm


class LogActionMixin:
    def save(self):
        super().save()
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        Action.objects.create(case=self.instance, type=typ, notes=self.log_note)


class FilterForm(GDSForm, forms.Form):
    """Filter forms can use GET by default"""

    submit_text = "Filter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_method = "GET"
        self.helper.checkboxes_small = True


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
            if user.wards and self.instance.ward in user.wards:
                ward_staff.append(Choice(user.id, user))
            else:
                other_staff.append(Choice(user.id, user))
        if ward_staff:
            ward_staff[-1].divider = "or"
        self.fields["assigned"].choices = ward_staff + other_staff

        self.helper.legend_size = "xl"

    def clean_assigned(self):
        assigned = self.cleaned_data["assigned"]
        assigned = User.objects.get(id=assigned)
        return assigned

    def save(self):
        super().save()
        if (
            not self.current_assigned
            or self.current_assigned.id != self.instance.assigned.id
        ):
            Action.objects.create(
                case=self.instance,
                assigned_old=self.current_assigned,
                assigned_new=self.instance.assigned,
            )


class KindForm(LogActionMixin, GDSForm, forms.ModelForm):
    """Update the kind of case"""

    submit_text = "Update"
    log_note = "Updated type"

    class Meta:
        model = Case
        fields = ["kind", "kind_other"]

    kind = forms.ChoiceField(
        label="Type",
        widget=forms.RadioSelect,
        choices=Case.KIND_CHOICES,
    )


class ActionForm(GDSForm, forms.ModelForm):
    submit_text = "Log action"

    class Meta:
        model = Action
        fields = ["type", "notes"]

    type = forms.ChoiceField(widget=forms.RadioSelect, required=True)

    def __init__(self, *args, **kwargs):
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

        self.fields["notes"].label = "Internal notes"
        self.fields["notes"].required = True

    def clean_type(self):
        type = self.cleaned_data["type"]
        type = ActionType.objects.get(id=type)
        return type

    def save(self, case):
        self.instance.case = case
        super().save()


class LocationForm(LogActionMixin, GDSForm, forms.ModelForm):
    """Update the location of case"""

    submit_text = "Update"
    log_note = "Updated location"

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
            del self.cleaned_data["addresses"]
        if self.cleaned_data.get("radius"):
            self.cleaned_data["uprn"] = ""
            self.instance.location_cache = ""
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
