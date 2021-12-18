from django import forms
from django.db.models import Q
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
            choices = User.objects.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(address__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
            choices = list(map(lambda x: (x.id, str(x)), choices))
        else:
            choices = []
        choices.append((0, "None, details below"))
        self.fields["user"].choices = choices
        if len(choices) == 1:
            self.initial["user"] = 0

    def clean(self):
        if "user" in self.cleaned_data and self.cleaned_data["user"] is None:
            if (
                not self.cleaned_data["first_name"]
                or not self.cleaned_data["last_name"]
                or not (
                    self.cleaned_data.get("email")
                    or self.cleaned_data.get("phone")
                    or self.cleaned_data["address"]
                )
            ):
                raise forms.ValidationError(
                    "Please specify a name and at least one of email/phone/address"
                )

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user == "0":
            return None
        user = User.objects.get(id=user)
        return user.id

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
