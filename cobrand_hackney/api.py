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
    r = s.get(url, params={"uprn": uprn})
    data = r.json()
    addresses = data["data"]["address"]
    if not addresses:
        return ""

    address = construct_address(addresses[0], include_postcode=True)
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
