from crispy_forms_gds.choices import Choice
from django import forms
from django.db.models import Q
from django.utils.html import format_html, mark_safe
from phonenumber_field.formfields import PhoneNumberField

from accounts.models import User
from noiseworks import cobrand
from noiseworks.forms import StepForm


class PersonPickForm(StepForm):
    title = "Who are you submitting this report on behalf of?"

    user = forms.ChoiceField(widget=forms.RadioSelect)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)
    phone = PhoneNumberField(required=False)
    postcode = forms.CharField(max_length=8, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        search = self.initial.get("search")
        if search:
            search = search.lower()
            queries = (
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(address__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
            if " " in search:
                first, last = search.split(maxsplit=1)
                queries |= Q(first_name__icontains=first) & Q(last_name__icontains=last)
            choices = User.objects.filter(queries)
            choices = list(map(lambda x: (x.id, str(x)), choices))
        else:
            choices = []

        data = kwargs.get("data", {}) or {}
        email = data.get("user_pick-email")
        phone = data.get("user_pick-phone")
        existing_user = User.objects.check_existing(email, phone)
        if existing_user:
            choices.insert(0, (existing_user.id, str(existing_user)))

        choices.append((0, "None, details below"))
        self.fields["user"].choices = choices
        if len(choices) == 1:
            self.initial["user"] = 0

    def clean(self):
        if "user" in self.cleaned_data and self.cleaned_data["user"] is None:
            email = self.cleaned_data.get("email")
            phone = self.cleaned_data.get("phone")
            if (
                not self.cleaned_data["first_name"]
                or not self.cleaned_data["last_name"]
                or not (email or phone or self.cleaned_data.get("postcode"))
            ):
                raise forms.ValidationError(
                    "Please specify a name and at least one of email/phone/postcode"
                )
            existing_user = User.objects.check_existing(email, phone)
            if existing_user:
                ch = self.fields["user"].choices
                found = False
                for i, c in enumerate(list(ch)):
                    if c[0] == existing_user.id:
                        found = True
                        ch.pop(i)
                        ch.insert(
                            0,
                            (c[0], mark_safe(format_html(f"<strong>{c[1]}</strong>"))),
                        )
                if not found:  # pragma: no cover - it will be there from init
                    ch.insert(0, (existing_user.id, str(existing_user)))
                raise forms.ValidationError(
                    "There is an existing user with those details (highlighted first below), please pick or change the details you entered"
                )

    def clean_postcode(self):
        pc = self.cleaned_data["postcode"]
        if not pc:
            return pc
        addresses = cobrand.api.addresses_for_postcode(pc)
        if "error" in addresses or not len(addresses.get("addresses", [])):
            raise forms.ValidationError("We could not recognise that postcode")
        choices = []
        for addr in addresses["addresses"]:
            choices.append((addr["value"], addr["label"]))
        self.to_store = {"postcode_results": choices}
        return pc

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user == "0":
            return None
        user = User.objects.get(id=user)
        return user.id

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class PersonAddressForm(StepForm):
    title = "What is their address?"
    address_uprn = forms.ChoiceField(widget=forms.RadioSelect, label="Address")
    address_manual = forms.CharField(
        label="Their address", widget=forms.Textarea, required=False
    )

    def __init__(self, address_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.radios_small = True
        choices = []
        for choice in address_choices:
            choices.append(choice)
        choices[-1] = Choice(*choices[-1], divider="or")
        choices.append(("missing", "Can’t find their address"))
        self.fields["address_uprn"].choices = choices


class PersonSearchForm(StepForm):
    submit_text = "Search"

    search = forms.CharField(label="Search for person")


class RecurrencePersonSearchForm(PersonSearchForm):
    title = "Who are you submitting this report on behalf of?"


class PerpetratorSearchForm(PersonSearchForm):
    title = "Add perpetrator"


class PerpetratorPickForm(PersonPickForm):
    title = "Add perpetrator"


class PerpetratorAddressForm(PersonAddressForm):
    title = "Add perpetrator"
