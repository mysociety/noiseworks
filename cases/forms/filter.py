from django import forms
from noiseworks.forms import GDSForm


class FilterForm(GDSForm, forms.Form):
    """Filter forms can use GET by default"""

    submit_text = "Filter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_method = "GET"
        self.helper.checkboxes_small = True
