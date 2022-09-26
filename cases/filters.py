import re

import django_filters
from django import forms
from django.db.models import Q
from phonenumber_field.phonenumber import to_python

from accounts.models import User
from noiseworks import cobrand

from .forms import FilterForm
from .models import Case
from .widgets import SearchWidget


def get_wards():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    wards["outside"] = "Outside Hackney"
    for group in cobrand.api.ward_groups():
        wards[group["id"]] = group["name"]
    return wards


class CaseFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        label="", method="search_filter", widget=SearchWidget
    )
    assigned = django_filters.ChoiceFilter(
        choices=[
            ("me", "Assigned to me"),
            ("following", "Cases I am following"),
            ("others", "Assigned to others"),
            ("none", "Unassigned"),
        ],
        method="assigned_filter",
    )
    uprn = django_filters.CharFilter()
    ward = django_filters.MultipleChoiceFilter(
        choices=list(get_wards().items()),
        label="Case location",
        widget=forms.CheckboxSelectMultiple,
        method="ward_filter",
    )
    created = django_filters.DateRangeFilter(label="Created")
    modified = django_filters.DateRangeFilter(label="Last updated")
    closed = django_filters.ChoiceFilter(
        label="Closed cases",
        # Don't display an option for an empty selection.
        empty_label=None,
        choices=[
            ("none", "Not included"),
            ("include", "Included"),
            ("only", "Only"),
        ],
        method="closed_filter",
        initial="none",
    )
    priority_only = django_filters.Filter(
        label="Priority only", widget=forms.CheckboxInput, method="priority_only_filter"
    )
    last_update_was_complaint = django_filters.Filter(
        label="Only show cases where the last update was a complaint",
        widget=forms.CheckboxInput,
        method="last_update_was_complaint_filter",
    )

    class Meta:
        model = Case
        form = FilterForm
        fields = ["kind", "where", "estate"]

    def __init__(self, data, *args, **kwargs):

        # Allows using initial values as defaults for filters.
        # See https://django-filter.readthedocs.io/en/stable/guide/tips.html#using-initial-values-as-defaults
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get("initial")
                if not data.get(name) and initial:
                    data[name] = initial

        user = kwargs["request"].user
        super().__init__(data, *args, **kwargs)

        self.filters.move_to_end("search", last=False)
        self.filters["kind"].label = "Noise type"
        self.filters["where"].label = "Noise location type"
        self.filters["estate"].label = "Hackney Estates property?"

        assignees = (
            Case.objects.filter(assigned__isnull=False)
            .values("assigned__first_name", "assigned__last_name", "assigned")
            .distinct()
            .order_by("assigned__first_name", "assigned__last_name")
        )
        ids = set()
        for assignee in assignees:
            id = assignee["assigned"]
            name = (
                f"{assignee['assigned__first_name']} {assignee['assigned__last_name']}"
            )
            self.filters["assigned"].extra["choices"].append((id, name))
            ids.add(id)
        try:
            user = User.objects.get(id=data.get("assigned", ""))
            if user.id not in ids:
                self.filters["assigned"].extra["choices"].append((user.id, user))
        except (User.DoesNotExist, ValueError):
            pass
        uprn = data.get("uprn")
        if not uprn:
            self.filters["uprn"].extra["widget"] = forms.HiddenInput

    def priority_only_filter(self, queryset, name, value):
        if value:
            return queryset.filter(priority=True)
        return queryset

    def closed_filter(self, queryset, name, value):
        if value == "none":
            return queryset.filter(closed=False)
        elif value == "include":
            return queryset
        elif value == "only":
            return queryset.filter(closed=True)
        return queryset  # pragma: no cover - should not be reachable.

    def last_update_was_complaint_filter(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(last_update_type=Case.LastUpdateTypes.COMPLAINT)

    def assigned_filter(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assigned=self.request.user)
        elif value == "following":
            return queryset.filter(followers=self.request.user)
        elif value == "others":
            return queryset.exclude(assigned=self.request.user).exclude(assigned=None)
        elif value == "none":
            return queryset.filter(assigned=None)
        else:
            return queryset.filter(assigned=value)

    def ward_filter(self, queryset, name, value):
        for i, v in list(enumerate(value)):
            for group in cobrand.api.ward_groups():
                if group["id"] == v:
                    value[i : i + 1] = group["wards"]
        return queryset.filter(ward__in=value)

    def search_filter(self, queryset, name, value):
        queries = Q()

        # postcode_lookup = cobrand.api.addresses_for_postcode(value)
        # addresses = postcode_lookup.get("addresses", [])
        # street_lookup = cobrand.api.addresses_for_string(value)
        # addresses.extend(street_lookup.get("addresses", []))
        # addresses = list(map(lambda x: x["value"], addresses))
        # roads = cobrand.api.matching_roads(value)
        # URPN cases in any of the addresses found by postcode/street lookup above
        # uprn_search = Q(uprn__in=addresses)

        # If the search term is a phone number, canonicalise it for search
        phone_parsed = to_python(value)
        if phone_parsed and phone_parsed.is_valid():
            value = str(phone_parsed)

        # Complainants with matching name/address/contact details
        queries |= (
            Q(complaints__complainant__first_name__icontains=value)
            | Q(complaints__complainant__last_name__icontains=value)
            | Q(complaints__complainant__address__icontains=value)
            | Q(complaints__complainant__email__icontains=value)
            | Q(complaints__complainant__phone__icontains=value)
        )

        # Perpetrators with matching name/address/contact details
        queries |= (
            Q(perpetrators__first_name__icontains=value)
            | Q(perpetrators__last_name__icontains=value)
            | Q(perpetrators__address__icontains=value)
            | Q(perpetrators__email__icontains=value)
            | Q(perpetrators__phone__icontains=value)
        )

        if " " in value:
            first, last = value.split(maxsplit=1)
            queries |= (
                Q(complaints__complainant__first_name__icontains=first)
                & Q(complaints__complainant__last_name__icontains=last)
            ) | (
                Q(perpetrators__first_name__icontains=first)
                & Q(perpetrators__last_name__icontains=last)
            )

        # Actions with matching notes
        queries |= Q(actions__notes__icontains=value)

        # Cases with matching UPRN, location or other kind, or ID
        queries |= (
            Q(location_cache__icontains=value)
            | Q(uprn=value)
            | Q(kind_other__icontains=value)
        )
        if re.match("[0-9]+$", value):
            queries |= Q(pk=value)

        # Complaints with matching descriptions/details
        queries |= (
            Q(complaints__rooms__icontains=value)
            | Q(complaints__description__icontains=value)
            | Q(complaints__effect__icontains=value)
        )

        return queryset.filter(queries).distinct()
