import re

from crispy_forms_gds.choices import Choice
from django.contrib.gis import forms
from phonenumber_field.formfields import PhoneNumberField
from requests.exceptions import RequestException

from accounts.models import User
from cobrands.interface import PlaceLookupError
from cobrands.registry import get_cobrand
from noiseworks.forms import GDSForm, StepForm

from ..models import Case
from ..widgets import MapWidget
from .common import get_address_choices_for_postcode


class ExistingForm(GDSForm, forms.Form):
    existing = forms.ChoiceField(
        choices=(
            ("new", "New issue"),
            Choice(
                "existing",
                "I have reported this before",
                hint="You can log a new occurrence against your existing report",
            ),
        ),
        widget=forms.RadioSelect,
        label="Is this a new issue or have you reported this before?",
    )


class AboutYouForm(StepForm):
    title = "About you"

    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField(
        label="Email address",
        help_text="We’ll only use this to send you updates on your report",
    )
    phone = PhoneNumberField(
        label="Telephone number",
        help_text="We will call you on this number to discuss your report and if necessary arrange a visit",
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            if user.email_verified:
                self.fields["email"].disabled = True
            if user.phone_verified:
                self.fields["phone"].disabled = True

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class BestTimeForm(StepForm):
    title = "Contacting you"
    best_time = forms.MultipleChoiceField(
        choices=User.BEST_TIME_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="When is the best time to contact you?",
        help_text="Tick all that apply",
    )
    best_method = forms.ChoiceField(
        choices=User.BEST_METHOD_CHOICES,
        label="What is the best method for contacting you?",
        widget=forms.RadioSelect,
    )

    def __init__(self, staff, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if staff:
            self.title = "Contacting the complainant"
            self.fields["best_time"].label = (
                "When is the best time to contact the complainant?"
            )
            self.fields["best_method"].label = (
                "What is the best method for contacting the complainant?"
            )


class PostcodeForm(StepForm):
    title = "What is your address?"
    postcode = forms.CharField(max_length=8)

    def clean_postcode(self):
        pc = self.cleaned_data["postcode"]
        choices = get_address_choices_for_postcode(pc)
        self.to_store = {"postcode_results": choices}
        return pc


class AddressForm(StepForm):
    title = "What is your address?"
    address_uprn = forms.ChoiceField(widget=forms.RadioSelect, label="Address")
    address_manual = forms.CharField(
        label="Your address", widget=forms.Textarea, required=False
    )

    def __init__(self, address_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.radios_small = True
        choices = []
        for choice in address_choices:
            choices.append(choice)
        choices[-1] = Choice(*choices[-1], divider="or")
        choices.append(("missing", "I can’t find my address"))
        self.fields["address_uprn"].choices = choices


class ReportingKindGroupForm(StepForm):
    title = "About the problem"
    group = forms.ChoiceField(
        label="What type of problem is it?",
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        group = self.fields["group"]
        cobrand = get_cobrand()
        group.choices = [(c["value"], c["label"]) for c in cobrand.kinds]


class ReportingKindForm(StepForm):
    title = "About the problem"
    kind = forms.ChoiceField(
        widget=forms.RadioSelect,
        help_text=get_cobrand().reporting_kind_form_help_text,
    )
    kind_other = forms.CharField(label="Other", required=False, max_length=100)

    def clean(self):
        kind = self.cleaned_data.get("kind")
        other = self.cleaned_data.get("kind_other")
        if kind == "other" and not other:
            self.add_error(
                "kind_other", forms.ValidationError("Please specify the type of noise")
            )

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.radios_small = True
        kind = self.fields["kind"]
        cobrand = get_cobrand()
        for g in cobrand.kinds:
            if g["value"] == group:
                group_name = g["label"]
                kind.choices = [(k, v) for k, v in g["kinds"].items()]
        if kind.choices[-1][0] == "other":
            kind.choices[-2] = Choice(
                kind.choices[-2][0], kind.choices[-2][1], divider="or"
            )
        kind.label = f"What kind of {group_name.lower()} problem?"
        self.kind_group = group


class WhereForms(StepForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = self.form_label_lookup(
            kwargs, "The location of the issue", "source"
        )


class WhereForm(WhereForms):
    where = forms.ChoiceField(
        widget=forms.RadioSelect,
        choices=Case.WHERE_CHOICES,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        where = self.fields["where"]
        where.label = self.form_label_lookup(kwargs, "Where is it coming from?")


def canonical_postcode(pc):
    outcode_pattern = "[A-PR-UWYZ]([0-9]{1,2}|([A-HIK-Y][0-9](|[0-9]|[ABEHMNPRVWXY]))|[0-9][A-HJKSTUW])"
    incode_pattern = "[0-9][ABD-HJLNP-UW-Z]{2}"
    postcode_regex = re.compile(r"^%s %s$" % (outcode_pattern, incode_pattern))
    space_regex = re.compile(r" *(%s)$" % incode_pattern)

    pc = re.sub("[^A-Z0-9]", "", pc.upper())
    pc = space_regex.sub(r" \1", pc)
    if postcode_regex.search(pc):
        return pc
    return None


class WhereLocationForm(WhereForms):
    search = forms.CharField(
        label="Postcode, or street name and area of the source",
        help_text="If you know the postcode please use that",
    )

    def clean_search(self):
        search = self.cleaned_data["search"]

        canon_postcode = canonical_postcode(search)
        if canon_postcode:
            choices = get_address_choices_for_postcode(canon_postcode)
            self.to_store = {"postcode_results": choices}
        else:
            try:
                candidates = get_cobrand().location_candidates_for_string(search)
            except PlaceLookupError:
                raise forms.ValidationError(
                    "Sorry, address lookup by name is not working at the moment, please search by postcode instead"
                )

            results = []
            for c in candidates:
                p = c.point
                p.transform(4326)
                coord_string = f"{p.coords[0]},{p.coords[1]}"
                results.append((coord_string, c.label))

            if len(results) > 1:
                self.to_store = {"geocode_results": results}
            elif len(results) == 1:
                self.to_store = {"geocode_result": results[0]}
            else:
                raise forms.ValidationError("We could not find that location")
        return search


class WherePostcodeResultsForm(WhereForms):
    source_uprn = forms.ChoiceField(
        widget=forms.RadioSelect, label="Please pick the address"
    )

    def __init__(self, address_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make sure we don't edit the thing passed in, it gets re-stored
        choices = []
        for choice in address_choices:
            choices.append(choice)
        # if choices:
        #    choices[-1] = Choice(*choices[-1], divider = "or")
        # choices.append(("missing", "I can’t find my address"))
        self.fields["source_uprn"].choices = choices


class WhereGeocodeResultsForm(WhereForms):
    geocode_result = forms.ChoiceField(
        widget=forms.RadioSelect, label="Please pick a match"
    )

    def __init__(self, geocode_choices=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if geocode_choices:
            self.fields["geocode_result"].choices = geocode_choices


class WhereMapForm(WhereForms):
    point = forms.PointField(
        srid=27700, widget=MapWidget, label="Click the map at the source of the issue"
    )
    zoom = forms.IntegerField(widget=forms.HiddenInput)
    radius = forms.TypedChoiceField(
        coerce=int,
        widget=forms.RadioSelect,
        choices=(
            (30, "Small (100ft / 30m)"),
            (180, "Medium (200yd / 180m)"),
            (800, "Large (half a mile / 800m)"),
        ),
        label="Area size",
        help_text="Adjust the area size to indicate roughly where you believe the source to be",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        zoom = self.data.get("where-map-zoom") or self.initial.get("zoom")
        radius = self.data.get("where-map-radius") or self.initial.get("radius")
        try:
            self.fields["point"].widget.zoom = int(zoom)
        except (TypeError, ValueError):
            pass
        self.fields["point"].widget.radius = radius
        self.helper.radios_small = True


class ConfirmationForm(StepForm):
    title = "Confirmation"
    code = forms.CharField(label="Token", max_length=6)

    def __init__(self, token, *args, **kwargs):
        self.token = token
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data["code"]
        if code != self.token:
            raise forms.ValidationError("Incorrect or expired code")
        return code
