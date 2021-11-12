from datetime import date
from django.core.validators import ValidationError
from crispy_forms_gds.helper import FormHelper
from crispy_forms_gds.fields import DateInputField
from crispy_forms_gds.layout import Submit


def monkeypatch(self, data_list):
    day, month, year = data_list
    if day and month and year:
        try:
            return date(day=int(day), month=int(month), year=int(year))
        except ValueError as e:
            raise ValidationError(str(e)) from e
    else:  # pragma: no cover
        return None


DateInputField.compress = monkeypatch


class GDSForm:
    """Mixin to add a submit button to the form"""

    submit_text = "Submit"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.add_input(Submit("", self.submit_text, css_class="nw-button"))
