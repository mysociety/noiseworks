import re
from django import forms
from django.db.models import Q
import django_filters
from phonenumber_field.phonenumber import to_python
from .models import Case
from .forms import FilterForm
from .widgets import SearchWidget
from noiseworks import cobrand
from accounts.models import User


def get_wards():
    wards = cobrand.api.wards()
    wards = {ward["gss"]: ward["name"] for ward in wards}
    wards["outside"] = "Outside Hackney"
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
        label="Area",
        widget=forms.CheckboxSelectMultiple,
    )
    created = django_filters.DateRangeFilter(label="Created")
    modified = django_filters.DateRangeFilter(label="Last updated")

    class Meta:
        model = Case
        form = FilterForm
        fields = ["kind", "where", "estate"]

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
        self.filters.move_to_end("search", last=False)
        self.filters["kind"].label = "Noise type"
        self.filters["where"].label = "Noise location type"
        self.filters["estate"].label = "Hackney Estates property?"
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
        elif value == "following":
            return queryset.filter(followers=self.request.user)
        elif value == "others":
            return queryset.exclude(assigned=self.request.user).exclude(assigned=None)
        elif value == "none":
            return queryset.filter(assigned=None)
        else:
            return queryset.filter(assigned=value)

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

        # Reporters with matching name/address/contact details
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
            f, l = value.split(maxsplit=2)
            queries |= (
                Q(complaints__complainant__first_name__icontains=f)
                & Q(complaints__complainant__last_name__icontains=l)
            ) | (
                Q(perpetrators__first_name__icontains=f)
                & Q(perpetrators__last_name__icontains=l)
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
