from typing import List, Optional

from django.conf import settings
from django.contrib.gis.geos import Point

from ..interface import (
    AddressCandidate,
    AddressDetail,
    LocationCandidate,
    LocationDetail,
    Ward,
)


class Cobrand:
    body_name = "Council"
    site_name = "EnviroWorks"
    page_title_suffix = "EnviroWorks"
    staff_email_domains = ["societyworks", "mysociety"]
    wards: List[Ward] = []
    reporting_kind_form_help_text: Optional[str] = None

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        return []

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        return None

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        return []

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        return None

    def staff_destination_email_addresses_for_case(self, case) -> List[str]:
        return ["staff-dest@example.org"]

    def override_email_colours(self) -> dict:
        return {}

    def override_email_settings(self, settings: dict) -> dict:
        return {}
