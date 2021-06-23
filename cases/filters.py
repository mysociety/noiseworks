import django_filters
from .models import Case
from .forms import FilterForm


class CaseFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(label="Search")
    status = django_filters.ChoiceFilter(
        label="Status", choices=(("active", "Active"), ("inactive", "Inactive"))
    )
    actions_taken = django_filters.ChoiceFilter(label="Actions taken")
    ward = django_filters.ChoiceFilter(
        choices=(
            ("Ward 1", "Ward 1"),
            ("Ward 2", "Ward 2"),
            ("Ward 3", "Ward 3"),
        ),
        label="Ward",
    )
    assigned = django_filters.ChoiceFilter(
        choices=(
            ("me", "Assigned to me"),
            ("others", "Assigned to others"),
            ("none", "Unassigned"),
        ),
        method="assigned_filter",
    )
    created = django_filters.DateFromToRangeFilter(
        label="Created",
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )
    modified = django_filters.DateFromToRangeFilter(
        label="Last updated",
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )

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
