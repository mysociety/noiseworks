from django import forms
import django_filters
from .models import Case
from .forms import FilterForm
from noiseworks import cobrand
from accounts.models import User


def get_wards():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    wards["outside"] = "Outside Hackney"
    return wards


class CaseFilter(django_filters.FilterSet):
    assigned = django_filters.ChoiceFilter(
        choices=[
            ("me", "Assigned to me"),
            ("others", "Assigned to others"),
            ("none", "Unassigned"),
        ],
        method="assigned_filter",
    )
    uprn = django_filters.CharFilter()
    ward = django_filters.MultipleChoiceFilter(
        choices=list(get_wards().items()),
        label="Area",
        widget=forms.CheckboxSelectMultiple,
    )
    created = django_filters.DateRangeFilter(label="Created")
    modified = django_filters.DateRangeFilter(label="Last updated")

    class Meta:
        model = Case
        form = FilterForm
        fields = ["kind"]

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        user = kwargs["request"].user
        submitted = data.get("kind") is not None
        # If the user has associated wards, and we've been asked for all/unassigned/others
        # (but not via a filter form submission), use those wards by default
        if (
            user.wards
            and not submitted
            and data.get("assigned") in ("", "none", "others")
        ):
            data.setlistdefault("ward", user.wards)
        # Default to showing cases assigned to the user
        data.setdefault("assigned", "me")
        super().__init__(data, *args, **kwargs)
        self.filters["kind"].label = "Noise type"
        try:
            user = User.objects.get(id=data["assigned"])
            self.filters["assigned"].extra["choices"].append((user.id, user))
        except (User.DoesNotExist, ValueError):
            pass
        uprn = data.get("uprn")
        if not uprn:
            self.filters["uprn"].extra["widget"] = forms.HiddenInput

    def assigned_filter(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assigned=self.request.user)
        elif value == "others":
            return queryset.exclude(assigned=self.request.user).exclude(assigned=None)
        elif value == "none":
            return queryset.filter(assigned=None)
        else:
            return queryset.filter(assigned=value)
