from crispy_forms_gds.helper import FormHelper
from crispy_forms_gds.layout import Submit
from django import forms


class GDSForm:
    """Mixin to add a submit button to the form"""

    submit_text = "Submit"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("", self.submit_text, css_class="nw-button"))


class StepForm(GDSForm, forms.Form):
    submit_text = "Next"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_tag = False
