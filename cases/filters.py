from django import forms
import django_filters
from .models import Case
from .forms import FilterForm
from noiseworks import cobrand


def get_wards():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    return wards


class CaseFilter(django_filters.FilterSet):
    # search = django_filters.CharFilter(label="Search")
    # status = django_filters.ChoiceFilter(
    #    label="Status", choices=(("active", "Active"), ("inactive", "Inactive"))
    # )
    # actions_taken = django_filters.ChoiceFilter(label="Actions taken")
    ward = django_filters.MultipleChoiceFilter(
        choices=list(get_wards().items()),
        label="Ward",
        widget=forms.CheckboxSelectMultiple,
    )
    assigned = django_filters.ChoiceFilter(
        choices=(
            ("me", "Assigned to me"),
            ("others", "Assigned to others"),
            ("none", "Unassigned"),
        ),
        method="assigned_filter",
    )
    created = django_filters.DateRangeFilter(label="Created")
    modified = django_filters.DateRangeFilter(label="Last updated")

    class Meta:
        model = Case
        form = FilterForm
        fields = ["kind"]

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("assigned", "me")
        super().__init__(data, *args, **kwargs)
        self.filters["kind"].label = "Noise type"

    def assigned_filter(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assigned=self.request.user)
        elif value == "others":
            return queryset.exclude(assigned=self.request.user).exclude(assigned=None)
        else:
            return queryset.filter(assigned=None)
