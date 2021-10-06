from django import forms
from accounts.models import User
from .models import Case, Action, ActionType
from crispy_forms_gds.choices import Choice
from noiseworks.forms import GDSForm


class FilterForm(GDSForm, forms.Form):
    """Filter forms can use GET by default"""

    submit_text = "Filter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_method = "GET"


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

    def save(self):
        super().save()
        typ, _ = ActionType.objects.get_or_create(name="Edit case")
        Action.objects.create(case=self.instance, type=typ, notes="Updated type")


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
