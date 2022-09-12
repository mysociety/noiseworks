from crispy_forms_gds.choices import Choice
from django import forms

from noiseworks.forms import GDSForm

from ..models import Action, ActionType


class LogForm(GDSForm, forms.ModelForm):
    submit_text = "Log action"

    class Meta:
        model = Action
        fields = ["type", "notes"]

    type = forms.ChoiceField(widget=forms.RadioSelect, required=True)
    notes = forms.CharField(
        widget=forms.Textarea,
        label="Internal notes",
        help_text="You can upload documents by adding a link or links to shared documents",
    )

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

    def clean_type(self):
        type = self.cleaned_data["type"]
        type = ActionType.objects.get(id=type)
        return type

    def save(self, case):
        self.instance.case = case
        super().save()


class UpdateForm(GDSForm):
    submit_text = "Update"


class UpdateInternalNotesForm(UpdateForm, forms.ModelForm):
    class Meta:
        model = Action
        fields = ["notes"]

    notes = forms.CharField(
        widget=forms.Textarea,
        label="Internal notes",
        help_text="You can upload documents by adding a link or links to shared documents",
    )
