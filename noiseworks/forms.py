from crispy_forms_gds.helper import FormHelper
from crispy_forms_gds.layout import Submit
from django import forms

from cobrands.registry import get_cobrand


class GDSForm:
    """Mixin to add a submit button to the form"""

    submit_text = "Submit"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("", self.submit_text, css_class="nw-button"))


class StepForm(GDSForm, forms.Form):
    submit_text = "Next"

    # Reporting form sends step/kind/group if known, but Recurrence form does not
    def __init__(self, step=None, kind=None, group=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_tag = False

    def form_label_lookup(self, kwargs, default, key_override=None):
        group = kwargs["group"]
        kind = kwargs["kind"]
        step = kwargs["step"]
        cobrand = get_cobrand()
        key = key_override or step
        return (
            cobrand.form_labels.get(kind, {}).get(key)
            or cobrand.form_labels.get(group, {}).get(key)
            or default
        )
