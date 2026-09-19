import json
import logging
import math
import sys
from email.utils import make_msgid
from typing import List, Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from requests.exceptions import RequestException
from requests_cache import CachedSession

from noiseworks.sass import inline_image_html

from ..interface import (
    AddressCandidate,
    AddressDetail,
    LocationCandidate,
    LocationDetail,
    PlaceLookupError,
    Ward,
)

logger = logging.getLogger("noiseworks")


address_api_settings = settings.COBRAND_SETTINGS["address_api"]
if "pytest" in sys.modules:
    session = requests.Session()
else:  # pragma: no cover
    session = CachedSession(expire_after=86400)
session.headers.update(
    {
        "Authorization": address_api_settings["key"],
        "User-Agent": address_api_settings["user_agent"],
    }
)


class Cobrand:
    body_name = "Hackney"
    site_name = "NoiseWorks"
    page_title_suffix = "Hackney Council"
    staff_email_domains = ["hackney.gov.uk"]
    wards = [
        Ward(gss_code="E05009367", name="Brownswood", group="North"),
        Ward(gss_code="E05009368", name="Cazenove", group="North"),
        Ward(gss_code="E05009369", name="Clissold", group="North"),
        Ward(gss_code="E05009370", name="Dalston", group="South"),
        Ward(gss_code="E05009371", name="De Beauvoir", group="South"),
        Ward(gss_code="E05009372", name="Hackney Central", group="South"),
        Ward(gss_code="E05009373", name="Hackney Downs", group="North"),
        Ward(gss_code="E05009374", name="Hackney Wick", group="South"),
        Ward(gss_code="E05009375", name="Haggerston", group="South"),
        Ward(gss_code="E05009376", name="Homerton", group="South"),
        Ward(gss_code="E05009377", name="Hoxton East & Shoreditch", group="South"),
        Ward(gss_code="E05009378", name="Hoxton West", group="South"),
        Ward(gss_code="E05009379", name="King's Park", group="South"),
        Ward(gss_code="E05009380", name="Lea Bridge", group="North"),
        Ward(gss_code="E05009381", name="London Fields", group="South"),
        Ward(gss_code="E05009382", name="Shacklewell", group="North"),
        Ward(gss_code="E05009383", name="Springfield", group="North"),
        Ward(gss_code="E05009384", name="Stamford Hill West", group="North"),
        Ward(gss_code="E05009385", name="Stoke Newington", group="North"),
        Ward(gss_code="E05009386", name="Victoria", group="South"),
        Ward(gss_code="E05009387", name="Woodberry Down", group="North"),
    ]
    reporting_kind_form_help_text: Optional[str] = (
        "Please see <a href='https://hackney.gov.uk/noise' target='_blank'>"
        "https://hackney.gov.uk/noise</a> "
        "for the kinds of noise we can and can’t deal with."
    )
    map_tile_url: Optional[str] = (
        "https://tilma.mysociety.org/os/hackney/Road_3857/{z}/{x}/{y}.png"
    )

    def _query_address_api(self, params: dict) -> Optional[dict]:
        """Queries the address API and returns the JSON under 'data' on
        success.

        Considers a 400 as 'no data for what was queried' i.e. endpoint doesn't
        consider the UPRN or postcode we've sent to be valid.
        Raises a PlaceLookupError for what are considered transient errors:
            * Any other error status codes.
            * Response is not JSON.
            * Response JSON has no top level 'data' field.
        """
        r = session.get(address_api_settings["url"], params=params)
        if r.status_code == 400:
            return None
        else:
            try:
                r.raise_for_status()
            except RequestException:
                raise PlaceLookupError
        try:
            data = r.json()
        except json.JSONDecodeError:
            raise PlaceLookupError()
        if "data" not in data:
            raise PlaceLookupError()
        return data["data"]

    def _construct_address_label(
        self, address: dict, include_postcode: bool = False
    ) -> str:
        lines = []
        for i in range(1, 4):
            line = address[f"line{i}"].title()
            if line and line != "Hackney":
                lines.append(line)
        if include_postcode:
            lines.append(address["postcode"])
        string = ", ".join(lines)
        return string

    def _wfs_lookup(
        self,
        url: str,
        typename: str,
        cql_filter: Optional[str] = None,
        bbox: Optional[str] = None,
    ) -> dict:
        params = {
            "SERVICE": "WFS",
            "VERSION": "1.1.0",
            "REQUEST": "GetFeature",
            "typename": typename,
            "outputformat": "json",
            "srsname": "urn:ogc:def:crs:EPSG::27700",
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        if bbox:
            params["BBOX"] = bbox
        url = f"https://map2.hackney.gov.uk/geoserver/{url}/ows"

        r = requests.get(url, params)
        logger.debug(
            f"Attempted WFS lookup at {url} with query parameters {params}\n Got: {r.text}\nStatus code: {r.status_code}."
        )
        try:
            return r.json()
        except json.JSONDecodeError:
            return {}

    def _linestring_parts(self, coordinates):
        for i in range(len(coordinates) - 1):
            yield (coordinates[i], coordinates[i + 1])

    def _distance_to_line(self, pt: Point, start, end) -> float:
        """Returns the cartesian distance of a point from a line.
        This is not a general-purpose distance function, it's intended for use with
        fairly nearby coordinates in EPSG:27700 where a spheroid doesn't need to be
        taken into account."""

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if dx == 0 and dy == 0:
            along = 0
        else:
            along = ((dx * (pt.x - start[0])) + (dy * (pt.y - start[1]))) / (
                dx**2 + dy**2
            )
        along = max(0, min(1, along))
        fx = start[0] + along * dx
        fy = start[1] + along * dy
        return math.sqrt(((pt.x - fx) ** 2) + ((pt.y - fy) ** 2))

    def _sorted_by_distance(self, pt: Point, features):
        """We have a list of features, and we want to sort them by distance to the location."""

        data = []
        for feature in features:
            nearest = None
            linestrings = feature["geometry"]["coordinates"]
            if feature["geometry"]["type"] == "LineString":
                linestrings = [linestrings]
            # If it is a point, upgrade it to a one-segment zero-length
            # MultiLineString so it can be compared by the distance function.
            if feature["geometry"]["type"] == "Point":
                linestrings = [[linestrings], [linestrings]]

            for coordinates in linestrings:
                for start, end in self._linestring_parts(coordinates):
                    distance = self._distance_to_line(pt, start, end)
                    if nearest is None or distance < nearest:
                        nearest = distance
            data.append((nearest or sys.maxsize, feature))

        data.sort(key=lambda x: x[0])
        data = list(map(lambda x: x[1], data))
        return data

    def _nearest_roads(self, pt: Point) -> str:
        pt = pt.transform(27700, clone=True)
        # NOTE: As is, will return no roads if the WFS server is having problems
        # and not returning JSON even if there are roads nearby.
        cql_filter = f"DWITHIN(geom, POINT({pt.x} {pt.y}), 50, meters)"
        data = self._wfs_lookup(
            "transport", "os_highways_street", cql_filter=cql_filter
        )
        data = self._sorted_by_distance(pt, data.get("features", []))
        data = data[:2]
        road_names = map(
            lambda x: x["properties"]["name"].title() or "Unknown road", data
        )
        return " / ".join(road_names)

    def _wfs_point_lookup(self, pt: Point, url: str, typename: str):
        pt = pt.transform(27700, clone=True)
        bbox = f"{pt.x},{pt.y},{pt.x},{pt.y},urn:ogc:def:crs:EPSG:27700"
        data = self._wfs_lookup(url, typename, bbox=bbox)
        if not data.get("features", []):
            return None
        feature = data["features"][0]
        return feature.get("properties", {})

    def _in_an_estate(self, pt: Point) -> bool:
        # NOTE: As is, will return 'false' if the WFS server is having problems.
        return True if self._wfs_point_lookup(pt, "housing", "lbh_estate") else False

    def _park_name_for_point(self, pt: Point) -> Optional[str]:
        # NOTE: As is, will return 'None' if the WFS server is having problems.
        properties = self._wfs_point_lookup(pt, "greenspaces", "hackney_park")
        if properties is None:
            return None
        return properties.get("name", None)

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        page = 1
        pages = 1
        candidates = []
        params = {"format": "detailed", "postcode": postcode}
        while page <= pages:
            params["page"] = str(page)
            page += 1
            data = self._query_address_api(params)
            if not data:
                continue
            pages = data.get(address_api_settings["pageAttr"], 0)
            for address in data["address"]:
                outofborough = address.get("outOfBoroughAddress")
                gazetteer = address.get("gazetteer")
                if gazetteer != "Hackney" or outofborough:
                    continue
                candidates.append(
                    AddressCandidate(
                        uprn=address["UPRN"],
                        label=self._construct_address_label(address),
                    )
                )

        return candidates

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        data = self._query_address_api({"uprn": uprn, "format": "detailed"})
        if not data or len(data.get("address", [])) < 1:
            return None
        address = data["address"][0]
        ward_mapping = {w.name: w.gss_code for w in self.wards}
        ward = ward_mapping.get(address["ward"], "outside")
        point = Point(address["longitude"], address["latitude"], srid=4326)
        estate = self._in_an_estate(point)
        return AddressDetail(
            uprn=uprn,
            label=self._construct_address_label(address, include_postcode=True),
            point=point,
            ward_gss=ward,
            in_an_estate=estate,
        )

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        url = "https://nominatim.openstreetmap.org/search"
        r = session.get(
            url,
            params={
                "q": string,
                "countrycodes": "gb",
                "viewbox": "51.519814,-0.104511,51.577784,-0.016527",
                "email": settings.CONTACT_EMAIL,
                "format": "jsonv2",
            },
        )
        logger.debug(f"Attempted {url}\nGot: {r.text}\nStatus code: {r.status_code}.")
        try:
            r.raise_for_status()
        except RequestException:
            raise PlaceLookupError()

        data = r.json()
        candidates = []
        for row in data:
            name = row["display_name"]
            if "London" not in name:
                continue
            name = name.replace(", United Kingdom", "")
            name = name.replace(", London, Greater London, England", "")
            name = name.replace(", London Borough of Hackney", "")
            candidates.append(
                LocationCandidate(
                    point=Point(float(row["lon"]), float(row["lat"]), srid=4326),
                    label=name,
                )
            )
        return candidates

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        point = point.transform(27700, clone=True)
        park_name = self._park_name_for_point(point)
        if park_name:
            desc = f"a point in {park_name}"
        else:
            roads = self._nearest_roads(point)
            if roads:
                desc = f"a point near {roads}"
            else:
                desc = f"({point.x:.0f},{point.y:.0f})"

        ward = "outside"
        key = settings.MAPIT_API_KEY
        data = requests.get(
            f"https://mapit.mysociety.org/point/27700/{point.x},{point.y}?api_key={key}"
        ).json()
        if "2508" in data.keys():
            for area in data.values():
                if area["type"] == "LBW":
                    ward = area["codes"]["gss"]

        estate = self._in_an_estate(point)
        return LocationDetail(
            point=point,
            description=desc,
            ward_gss=ward,
            in_an_estate=estate,
        )

    def example_uprns(self) -> List[str]:
        return []

    def staff_destination_email_addresses_for_case(self, case) -> List[str]:
        email_config = settings.COBRAND_SETTINGS["staff_destination"]
        if case.ward == "outside":
            emails = email_config["outside"]
        elif case.where == "business":
            emails = email_config["business"]
        elif case.estate == "y":
            emails = email_config["hackney-housing"]
        else:  # So no and don't know treated the same
            emails = email_config["housing"]
        return emails.split(",")

    def override_email_colours(self) -> dict:
        color_green = "#00b341"
        color_black = "#000000"
        color_white = "#FFFFFF"
        color_hackney_pale_green = "#f2f7f0"
        color_hackney_dark_green = "#00664f"

        body_background_color = color_hackney_pale_green
        body_text_color = color_black
        header_background_color = color_black
        header_text_color = color_white
        secondary_column_background_color = color_white
        button_background_color = color_hackney_dark_green
        button_text_color = color_white

        logo_width = "200"  # pixel measurement, but without 'px' suffix
        logo_height = "36"  # pixel measurement, but without 'px' suffix
        logo_inline = {
            "id": make_msgid(domain="hackney.gov.uk")[1:-1],
            "data": inline_image_html("hackney-logo-white.png"),
        }
        header_padding = "20px 30px"

        return locals()

    def override_email_settings(self, settings: dict) -> dict:
        only_column_style = "{only_column_style} border: 1px solid {column_divider_color}; border-top: none;".format(
            **settings
        )
        primary_column_style = "{primary_column_style} border: 1px solid {column_divider_color}; border-top: none;".format(
            **settings
        )
        secondary_column_style = "vertical-align: top; width: 50%; background-color: {secondary_column_background_color}; color: {secondary_column_text_color}; border: 1px solid {column_divider_color}; border-top: none; border-left: none;".format(
            **settings
        )
        return locals()
