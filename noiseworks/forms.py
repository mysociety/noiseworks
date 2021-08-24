from crispy_forms_gds.helper import FormHelper
from crispy_forms_gds.layout import Submit


class GDSForm:
    """Mixin to add a submit button to the form"""

    submit_text = "Submit"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.add_input(
            Submit("", self.submit_text, css_class="lbh-button")
        )  # XXX Hackney
