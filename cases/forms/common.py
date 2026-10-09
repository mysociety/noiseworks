from django.contrib.gis import forms

from cobrands.interface import PlaceLookupError
from cobrands.registry import get_cobrand


def get_address_choices_for_postcode(pc):
    try:
        addresses = get_cobrand().address_candidates_for_postcode(pc)
    except PlaceLookupError:
        raise forms.ValidationError(
            (
                "Sorry, something went wrong when looking up the postcode, "
                "please try again later"
            )
        )
    if not addresses:
        raise forms.ValidationError("We could not recognise that postcode")

    return [(a.uprn, a.label) for a in addresses]


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result
