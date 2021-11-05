from django import forms
from django.db.models import Q
from accounts.models import User
from ..models import Action, ActionType
from phonenumber_field.formfields import PhoneNumberField
from noiseworks.forms import GDSForm


class PersonPickForm(GDSForm, forms.Form):
    submit_text = "Add"
    log_note = "Added perpetrator"

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
        search = search.lower()
        choices = User.objects.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(address__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
        )
        choices = list(map(lambda x: (x.id, str(x)), choices))
        choices.append((0, "None, details below"))
        self.fields["user"].choices = choices

    def clean(self):
        if "user" in self.cleaned_data and self.cleaned_data["user"] is None:
            if (
                not self.cleaned_data["first_name"]
                or not self.cleaned_data["last_name"]
                or not (self.cleaned_data["email"] or self.cleaned_data["phone"])
            ):
                raise forms.ValidationError(
                    "Please specify a name and at least one of email/phone"
                )

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user == "0":
            return None
        user = User.objects.get(id=user)
        return user

    def save(self, case):
        user = self.cleaned_data.pop("user")
        search = self.cleaned_data.pop("search")
        if not user:
            user = User(**self.cleaned_data)
            if user.phone:
                user.phone_verified = True
            if user.email:
                user.email_verified = True
            if user.phone:
                user.username = str(user.phone)
            else:  # user.email will be present
                user.username = User.objects.normalize_email(user.email)
            user.save()
        case.perpetrators.add(user)
        case.save()
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        Action.objects.create(case=case, type=typ, notes=self.log_note)


class PersonSearchForm(GDSForm, forms.Form):
    submit_text = "Search"

    search = forms.CharField()
