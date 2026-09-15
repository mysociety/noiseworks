from typing import List, Optional

from django.contrib.gis.geos import Point

from cases.models import Case

from .interface import (
    AddressCandidate,
    AddressDetail,
    LocationCandidate,
    LocationDetail,
    Ward,
)


class TestCobrand:
    body_name = "Body"
    site_name = "Site"
    staff_email_domains: List[str] = ["body"]
    wards: List[Ward] = [
        Ward(gss_code="GSS1", name="Ward 1", group="North"),
        Ward(gss_code="GSS2", name="Ward 2", group="North"),
        Ward(gss_code="GSS3", name="Ward 3", group="South"),
        Ward(gss_code="GSS4", name="Ward 4", group="South"),
    ]

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        return []

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        return None

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        return []

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        return None

    def override_email_colours(self) -> dict:
        return {}

    def override_email_settings(self, settings: dict) -> dict:
        return {}

    def staff_destination_email_addresses_for_case(self, case: Case) -> List[str]:
        return ["destination@body"]
