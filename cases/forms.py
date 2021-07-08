from django import forms
from accounts.models import User
from .models import Case, Action
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

    assigned = forms.ModelChoiceField(
        label="Reassign to",
        widget=forms.RadioSelect,
        queryset=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_assigned = self.instance.assigned
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        if self.instance.assigned:
            staff_users = staff_users.exclude(id=self.instance.assigned.id)
        self.fields["assigned"].queryset = staff_users

        self.helper.legend_size = "xl"

    def save(self, case, user):
        super().save()
        Action.objects.create(
            created_by=user,
            case=self.instance,
            assigned_old=self.current_assigned,
            assigned_new=self.instance.assigned,
        )


class ActionForm(GDSForm, forms.ModelForm):
    submit_text = "Log action"

    class Meta:
        model = Action
        fields = ["type", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].empty_label = None
        self.fields["type"].widget = forms.RadioSelect()
        self.fields["type"].required = True
        self.fields["notes"].label = "Internal notes"
        self.fields["notes"].required = True

    def save(self, case, user):
        self.instance.case = case
        self.instance.created_by = user
        super().save()
