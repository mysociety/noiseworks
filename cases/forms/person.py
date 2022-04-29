from django import forms
from django.db.models import Q
from django.utils.html import format_html, mark_safe
from accounts.models import User
from ..models import Action, ActionType
from phonenumber_field.formfields import PhoneNumberField
from noiseworks.forms import GDSForm


class PersonPickForm(GDSForm, forms.Form):
    title = "Who are you submitting this report on behalf of?"
    submit_text = "Next"

    search = forms.CharField(widget=forms.HiddenInput)
    user = forms.ChoiceField(widget=forms.RadioSelect)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)
    phone = PhoneNumberField(required=False)
    address = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        search = self.data.get("search") or self.initial.get("search")
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
                f, l = search.split(maxsplit=1)
                queries |= Q(first_name__icontains=f) & Q(last_name__icontains=l)
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
                or not (email or phone or self.cleaned_data["address"])
            ):
                raise forms.ValidationError(
                    "Please specify a name and at least one of email/phone/address"
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
                if not found:
                    ch.insert(0, (existing_user.id, str(existing_user)))
                raise forms.ValidationError(
                    "There is an existing user with those details (highlighted first below), please pick or change the details you entered"
                )

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user == "0":
            return None
        user = User.objects.get(id=user)
        return user.id

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def save(self):
        user = self.cleaned_data.pop("user")
        search = self.cleaned_data.pop("search")
        if not user:
            user = User.objects.create_user(**self.cleaned_data)
            return user.id
        return user


class PersonSearchForm(GDSForm, forms.Form):
    submit_text = "Search"

    search = forms.CharField(label="Search for person")


class RecurrencePersonSearchForm(PersonSearchForm):
    title = "Who are you submitting this report on behalf of?"


class PerpetratorPickForm(PersonPickForm):
    submit_text = "Add"
    log_note = "Added perpetrator"

    def save(self, case):
        user_id = super().save()
        case.perpetrators.add(user_id)
        case.save()
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        Action.objects.create(case=case, type=typ, notes=self.log_note)
