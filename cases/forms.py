from django import forms
from accounts.models import User
from crispy_forms_gds.helper import FormHelper
from crispy_forms_gds.layout import Submit
from .models import Case


class ReassignForm(forms.ModelForm):
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

        self.helper = FormHelper(self)
        self.helper.legend_size = "xl"
        self.helper.add_input(Submit("submit", "Reassign"))

    def save(self):
        super().save()
        Action.objects.create(
            assigned_old=self.current_assigned,
            assigned_new=self.instance.assigned,
        )
