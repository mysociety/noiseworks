import requests
from django.conf import settings


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
    api = settings.COBRAND_SETTINGS["address_api"]
    url = api["url"]
    key = api["key"]

    s = requests.Session()
    s.headers.update({"Authorization": key})
    r = s.get(url, params={"uprn": uprn, "format": "detailed"})
    data = r.json()
    addresses = data["data"]["address"]
    if not addresses:
        return {"string": "", "ward": ""}

    address = addresses[0]
    address["string"] = construct_address(address, include_postcode=True)
    return address


def addresses_for_postcode(postcode):
    api = settings.COBRAND_SETTINGS["address_api"]
    url = api["url"]
    key = api["key"]
    pageAttr = api["pageAttr"]

    params = {
        "format": "detailed",
        "postcode": postcode,
    }

    s = requests.Session()
    s.headers.update({"Authorization": key})

    page = 1
    pages = 1
    addresses = []
    outside = False
    while page <= pages:
        params["page"] = page
        r = s.get(url, params=params)
        data = r.json()
        if "data" not in data:
            return {"error": "Sorry, did not recognise that postcode"}
        pages = data["data"].get(pageAttr, 0)
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
