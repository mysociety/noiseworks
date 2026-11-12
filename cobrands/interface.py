from dataclasses import dataclass
from typing import List, Optional, Protocol

from django.contrib.gis.geos import Point


@dataclass(frozen=True)
class AddressCandidate:
    uprn: str
    label: str


@dataclass(frozen=True)
class AddressDetail:
    uprn: str
    label: str
    point: Optional[Point]
    ward_gss: str  # Supports special 'outside' GSS.
    in_an_estate: Optional[bool]


@dataclass(frozen=True)
class LocationCandidate:
    point: Point
    label: str


@dataclass(frozen=True)
class LocationDetail:
    point: Point
    description: str
    ward_gss: str  # Supports special 'outside' GSS.
    in_an_estate: Optional[bool]


@dataclass(frozen=True)
class Ward:
    gss_code: str
    name: str
    group: str  # For things like filtering on 'north' and 'south'.


class PlaceLookupError(Exception):
    """Something went wrong with the lookup itself."""

    pass


class Cobrand(Protocol):
    body_name: str
    site_name: str
    page_title_suffix: str
    staff_email_domains: List[str]
    wards: List[Ward]
    reporting_kind_form_help_text: Optional[str]
    map_tile_url: Optional[str]  # None means OpenStreetMap.

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        """Raises PlaceLookupError on lookup issues."""
        ...

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        """Raises PlaceLookupError on lookup issues."""
        ...

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        """Raises PlaceLookupError on lookup issues."""
        ...

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        """Raises PlaceLookupError on lookup issues."""
        ...

    def override_email_colours(self) -> dict:
        """Returns a dict of email colour settings to override the base ones."""
        ...

    def override_email_settings(self, settings: dict) -> dict:
        """Takes a the email settings after colours have been set up and returns
        the settings to override."""
        ...

    def example_uprns(self) -> List[str]:
        """UPRNs to use for test data."""
        ...

    def staff_destination_email_addresses_for_case(self, case) -> List[str]:
        """Returns one or more email addresses to send new case and reoccurence emails to."""
        ...
