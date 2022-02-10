import math
import sys
import requests
from requests_cache import CachedSession
from django.conf import settings

api = settings.COBRAND_SETTINGS["address_api"]
if "pytest" in sys.modules:
    session = requests.Session()
else:  # pragma: no cover
    session = CachedSession(expire_after=86400)
session.headers.update({"Authorization": api["key"]})


def construct_address(address, include_postcode=False):
    lines = []
    for i in range(1, 4):
        line = address[f"line{i}"].title()
        if line and line != "Hackney":
            lines.append(line)
    if include_postcode:
        lines.append(address["postcode"])
    string = ", ".join(lines)
    return string


def address_for_uprn(uprn):
    r = session.get(api["url"], params={"uprn": uprn, "format": "detailed"})
    data = r.json()
    addresses = data["data"]["address"]
    if not addresses:
        return {"string": "", "ward": ""}

    address = addresses[0]
    address["string"] = construct_address(address, include_postcode=True)
    return address


def addresses_for_postcode(postcode):
    params = {"format": "detailed", "postcode": postcode}
    return _addresses_api(params)


def addresses_for_string(string):
    params = {"format": "detailed", "gazetteer": "local", "street": string}
    return _addresses_api(params)


def _addresses_api(params):
    page = 1
    pages = 1
    addresses = []
    outside = False
    while page <= pages:
        params["page"] = page
        r = session.get(api["url"], params=params)
        data = r.json()
        if "data" not in data:
            return {"error": "Sorry, did not recognise that postcode"}
        pages = data["data"].get(api["pageAttr"], 0)
        for address in data["data"]["address"]:
            if address["locality"] != "HACKNEY":
                outside = True
                continue
            addresses.append(
                {
                    "value": address["UPRN"],
                    "latitude": round(address["latitude"], 6),
                    "longitude": round(address["longitude"], 6),
                    "label": construct_address(address),
                }
            )
        page += 1

    if not addresses and outside:
        return {"error": "Sorry, that postcode appears to lie outside Hackney"}

    return {"addresses": addresses}


def ward_groups():
    return (
        {
            "id": "north",
            "name": "North",
            "wards": [
                "E05009367",
                "E05009368",
                "E05009369",
                "E05009373",
                "E05009380",
                "E05009382",
                "E05009383",
                "E05009384",
                "E05009385",
                "E05009387",
            ],
        },
        {
            "id": "south",
            "name": "South",
            "wards": [
                "E05009370",
                "E05009371",
                "E05009372",
                "E05009374",
                "E05009375",
                "E05009376",
                "E05009377",
                "E05009378",
                "E05009379",
                "E05009381",
                "E05009386",
            ],
        },
    )


def wards():
    return (
        {"id": 144390, "gss": "E05009367", "name": "Brownswood"},
        {"id": 144387, "gss": "E05009368", "name": "Cazenove"},
        {"id": 144384, "gss": "E05009369", "name": "Clissold"},
        {"id": 144392, "gss": "E05009370", "name": "Dalston"},
        {"id": 144381, "gss": "E05009371", "name": "De Beauvoir"},
        {"id": 144394, "gss": "E05009372", "name": "Hackney Central"},
        {"id": 144385, "gss": "E05009373", "name": "Hackney Downs"},
        {"id": 144383, "gss": "E05009374", "name": "Hackney Wick"},
        {"id": 144380, "gss": "E05009375", "name": "Haggerston"},
        {"id": 144395, "gss": "E05009376", "name": "Homerton"},
        {"id": 144379, "gss": "E05009377", "name": "Hoxton East & Shoreditch"},
        {"id": 144391, "gss": "E05009378", "name": "Hoxton West"},
        {"id": 144389, "gss": "E05009379", "name": "King's Park"},
        {"id": 144386, "gss": "E05009380", "name": "Lea Bridge"},
        {"id": 144382, "gss": "E05009381", "name": "London Fields"},
        {"id": 144396, "gss": "E05009382", "name": "Shacklewell"},
        {"id": 144388, "gss": "E05009383", "name": "Springfield"},
        {"id": 144399, "gss": "E05009384", "name": "Stamford Hill West"},
        {"id": 144397, "gss": "E05009385", "name": "Stoke Newington"},
        {"id": 144393, "gss": "E05009386", "name": "Victoria"},
        {"id": 144398, "gss": "E05009387", "name": "Woodberry Down"},
    )


def in_a_park(pt):
    filter = f'<Filter xmlns:gml="http://www.opengis.net/gml"><Intersects><PropertyName>geom</PropertyName><gml:Point srsName="27700"><gml:coordinates>{pt.x},{pt.y}</gml:coordinates></gml:Point></Intersects></Filter>'
    r = requests.get(
        "https://map2.hackney.gov.uk/geoserver/greenspaces/ows",
        params={
            "SERVICE": "WFS",
            "VERSION": "1.1.0",
            "REQUEST": "GetFeature",
            "typename": "greenspaces:hackney_park",
            "outputformat": "json",
            "srsname": "urn:ogc:def:crs:EPSG::27700",
            "filter": filter,
        },
    )
    data = r.json()
    name = False
    if data["features"]:
        name = data["features"][0]["properties"]
    return name


def nearest_roads(pt):
    filter = (
        f"<Filter xmlns:gml=\"http://www.opengis.net/gml\"><DWithin><PropertyName>geom</PropertyName><gml:Point><gml:coordinates>{pt.x},{pt.y}</gml:coordinates></gml:Point><Distance units='m'>50</Distance></DWithin></Filter>",
    )
    r = requests.get(
        "https://map2.hackney.gov.uk/geoserver/transport/ows",
        params={
            "SERVICE": "WFS",
            "VERSION": "1.1.0",
            "REQUEST": "GetFeature",
            "typename": "transport:os_highways_street",
            "outputformat": "json",
            "srsname": "urn:ogc:def:crs:EPSG::27700",
            "filter": filter,
        },
    )
    data = r.json()
    data = _sorted_by_distance(pt, data["features"])
    data = data[:2]
    data = map(lambda x: x["properties"]["name"].title() or "Unknown road", data)
    return " / ".join(data)


# def matching_roads(s):
#     filter = (
#         f"<Filter xmlns:gml=\"http://www.opengis.net/gml\"><PropertyIsLike wildCard='*' singleChar='.' escape='!'><PropertyName>name</PropertyName><Literal>*{s}*</Literal></PropertyIsLike></Filter>",
#     )
#     r = requests.get(
#         "https://map2.hackney.gov.uk/geoserver/transport/ows",
#         params={
#             "SERVICE": "WFS",
#             "VERSION": "1.1.0",
#             "REQUEST": "GetFeature",
#             "typename": "transport:os_highways_street",
#             "outputformat": "json",
#             "srsname": "urn:ogc:def:crs:EPSG::27700",
#             "filter": filter,
#         },
#     )
#     data = r.json()
#     return data


def _sorted_by_distance(pt, features):
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
            for start, end in linestring_parts(coordinates):
                distance = _distanceToLine(pt, start, end)
                if nearest is None or distance < nearest:
                    nearest = distance
        data.append((nearest or sys.maxsize, feature))

    data.sort(key=lambda x: x[0])
    data = list(map(lambda x: x[1], data))
    return data


def linestring_parts(coordinates):
    for i in range(len(coordinates) - 1):
        yield (coordinates[i], coordinates[i + 1])


def _distanceToLine(pt, start, end):
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


def geocode(q):
    url = "https://nominatim.openstreetmap.org/search"
    r = session.get(
        url,
        params={
            "q": q,
            "countrycodes": "gb",
            "viewbox": "51.519814,-0.104511,51.577784,-0.016527",
            "email": settings.CONTACT_EMAIL,
            "format": "jsonv2",
        },
    )
    data = r.json()
    out = []
    for row in data:
        name = row["display_name"]
        if "London" not in name:
            continue
        name = name.replace(", United Kingdom", "")
        name = name.replace(", London, Greater London, England", "")
        name = name.replace(", London Borough of Hackney", "")
        out.append((f"{row['lon']},{row['lat']}", name))
    return out
