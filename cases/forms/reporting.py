import re
from django.contrib.gis import forms
from crispy_forms_gds.choices import Choice
from phonenumber_field.formfields import PhoneNumberField
from noiseworks.forms import GDSForm
from noiseworks import cobrand
from accounts.models import User
from ..models import Case
from ..widgets import MapWidget


class StepForm(GDSForm, forms.Form):
    submit_text = "Next"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_tag = False


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
    email = forms.CharField(
        label="Email address",
        help_text="We’ll only use this to send you updates on your report",
    )
    phone = PhoneNumberField(
        label="Telephone number",
        help_text="We will call you on this number to discuss your report and if necessary arrange a visit",
    )


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
            self.title = "Contacting the reporter"
            self.fields[
                "best_time"
            ].label = "When is the best time to contact the reporter?"
            self.fields[
                "best_method"
            ].label = "What is the best method for contacting the reporter?"


class PostcodeForm(StepForm):
    title = "What is your address?"
    postcode = forms.CharField(max_length=8)
    addresses = forms.ChoiceField(
        required=False, widget=forms.HiddenInput, label="Address"
    )
    address_uprn = forms.CharField(required=False, widget=forms.HiddenInput)
    address_manual = forms.CharField(
        label="Your address", widget=forms.HiddenInput, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.radios_small = True

    def clean(self):
        if self.cleaned_data.get("addresses"):
            self.cleaned_data["address_uprn"] = self.cleaned_data["addresses"]
            del self.cleaned_data["addresses"]
        return self.cleaned_data

    def clean_addresses(self):
        uprn = self.cleaned_data["addresses"]
        if re.match("[0-9]+|missing$", uprn):
            return uprn
        if self.fields["addresses"].choices:
            raise forms.ValidationError("Please select one of the addresses below")
        return uprn

    def clean_postcode(self):
        pc = self.cleaned_data["postcode"]
        self.fields["addresses"].choices = self.address_choices(pc)
        self.fields["addresses"].widget = forms.RadioSelect()
        self.fields["address_manual"].widget = forms.Textarea()
        return pc

    def address_choices(self, pc):
        addresses = cobrand.api.addresses_for_postcode(pc)
        if "error" in addresses:
            raise forms.ValidationError("We could not recognise that postcode")
        choices = []
        for addr in addresses["addresses"]:
            choices.append((addr["value"], addr["label"]))
        choices[-1] = Choice(choices[-1][0], choices[-1][1], divider="or")
        choices.append(("missing", "I can’t find my address"))
        return choices


class ReportingKindForm(StepForm):
    title = "About the noise"
    kind = forms.ChoiceField(
        label="What kind of noise is it?",
        widget=forms.RadioSelect,
        help_text="Please see <a href='https://hackney.gov.uk/noise' target='_blank'>https://hackney.gov.uk/noise</a> for the kinds of noise we can and can’t deal with.",
        choices=Case.KIND_CHOICES,
    )
    kind_other = forms.CharField(label="Other", required=False)

    def clean(self):
        kind = self.cleaned_data.get("kind")
        other = self.cleaned_data.get("kind_other")
        if kind == "other" and not other:
            self.add_error(
                "kind_other", forms.ValidationError("Please specify the type of noise")
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.radios_small = True
        kind = self.fields["kind"]
        kind.choices[-2] = Choice(
            kind.choices[-2][0], kind.choices[-2][1], divider="or"
        )


class WhereForm(StepForm):
    title = "Where is the noise coming from?"
    where = forms.ChoiceField(
        label="Where is the noise coming from?",
        widget=forms.RadioSelect,
        choices=Case.WHERE_CHOICES,
    )
    estate = forms.ChoiceField(
        label="Is the residence a Hackney Estates property?",
        widget=forms.RadioSelect,
        required=False,
        help_text="Optional",
        choices=Case.ESTATE_CHOICES,
    )


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


class WhereLocationForm(StepForm):
    title = "Where is the noise coming from?"
    search = forms.CharField(
        label="Postcode, or street name and area of the source",
        help_text="If you know the postcode please use that",
    )

    def clean_search(self):
        search = self.cleaned_data["search"]

        canon_postcode = canonical_postcode(search)
        if canon_postcode:
            addresses = cobrand.api.addresses_for_postcode(canon_postcode)
            if "error" in addresses:
                raise forms.ValidationError("We could not recognise that postcode")
            choices = []
            for addr in addresses["addresses"]:
                choices.append((addr["value"], addr["label"]))
            self.to_store = {"postcode_results": choices}
        else:
            results = cobrand.api.geocode(search)
            if len(results) > 1:
                self.to_store = {"geocode_results": results}
            elif len(results) == 1:
                self.to_store = {"geocode_result": results[0]}
            else:
                raise forms.ValidationError("We could not find that location")
        return search


class WherePostcodeResultsForm(StepForm):
    title = "The source of the noise"
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


class WhereGeocodeResultsForm(StepForm):
    title = "The source of the noise"
    geocode_result = forms.ChoiceField(
        widget=forms.RadioSelect, label="Please pick a match"
    )

    def __init__(self, geocode_choices=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if geocode_choices:
            self.fields["geocode_result"].choices = geocode_choices


class WhereMapForm(StepForm):
    title = "The source of the noise"
    point = forms.PointField(
        srid=27700, widget=MapWidget, label="Click the map at the source of the noise"
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
        help_text="Adjust the area size to indicate roughly where you believe the noise source to be",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        zoom = self.data.get("where-map-zoom") or self.initial.get("zoom")
        radius = self.data.get("where-map-radius") or self.initial.get("radius")
        try:
            self.fields["point"].widget.zoom = int(zoom)
        except:
            pass
        self.fields["point"].widget.radius = radius
        self.helper.radios_small = True