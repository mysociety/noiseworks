import csv
import random
import re
from email.utils import make_msgid
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import Point

from noiseworks.sass import inline_image_html

from ..hackney.cobrand import Cobrand as HackneyCobrand
from ..interface import (
    AddressCandidate,
    AddressDetail,
    LocationCandidate,
    LocationDetail,
)

hackney_cobrand = HackneyCobrand()

# See the 'generate_addresses' command.
ADDRESS_FILE = Path(__file__).resolve().parent / "addresses.csv"


@cache
def addresses() -> List[Dict[str, str]]:
    with ADDRESS_FILE.open() as f:
        return list(csv.DictReader(f))


def _normalize_pc(pc):
    return re.sub("[^A-Z0-9]", "", pc.upper())


class Cobrand:
    body_name = "Council"
    site_name = "EnviroWorks"
    page_title_suffix = "EnviroWorks"
    staff_email_domains = ["societyworks", "mysociety"]
    wards = hackney_cobrand.wards
    reporting_kind_form_help_text: Optional[str] = None
    map_tile_url: Optional[str] = None
    default_kind_group: Optional[str] = None

    form_labels = {
        "noise": {
            "source": "The source of the noise",
            "where": "Where is the noise coming from?",
            "details": "Details of the noise",
            "describe_help": "Please include as much detail as possible e.g. if the Noise is about a car alarm include the car’s colour, car registration etc",
            "describe": "Can you describe the noise?",
            "effect": "What effect has the noise had on you?",
        },
        "asb": {
            "source": "The source of the behaviour",
            "where": "Where is the behaviour occurring?",
            "details": "Details of the behaviour",
            "describe": "Can you describe the behaviour?",
            "effect": "What effect has the behaviour had on you?",
        },
        "light": {
            "source": "The source of the light",
            "where": "Where is the light coming from?",
            "details": "Details of the light",
            "describe": "Can you describe the light?",
            "effect": "What effect has the light had on you?",
        },
        "chimney": {
            "source": "The source of the smoke",
            "where": "Where is the smoke coming from?",
            "details": "Details of the smoke",
            "describe": "Can you describe the smoke?",
            "effect": "What effect has the smoke had on you?",
        },
        "dark": {
            "source": "The source of the smoke",
            "where": "Where is the smoke coming from?",
            "details": "Details of the smoke",
            "describe": "Can you describe the smoke?",
            "effect": "What effect has the smoke had on you?",
        },
        "fumes-vehicle": {
            "source": "The source of the fumes",
            "where": "Where are the fumes coming from?",
            "details": "Details of the fumes",
            "describe": "Can you describe the fumes?",
            "effect": "What effect has the fumes had on you?",
        },
        "fumes-heating": {
            "source": "The source of the fumes",
            "where": "Where are the fumes coming from?",
            "details": "Details of the fumes",
            "describe": "Can you describe the fumes?",
            "effect": "What effect has the fumes had on you?",
        },
        "dust": {
            "source": "The source of the dust",
            "where": "Where is the dust coming from?",
            "details": "Details of the dust",
            "describe": "Can you describe the dust?",
            "effect": "What effect has the dust had on you?",
        },
        "steam": {
            "source": "The source of the steam",
            "where": "Where is the steam coming from?",
            "details": "Details of the steam",
            "describe": "Can you describe the steam?",
            "effect": "What effect has the steam had on you?",
        },
        "smells": {
            "source": "The source of the smells/odours",
            "where": "Where are the smells/odours coming from?",
            "details": "Details of the smells",
            "describe": "Can you describe the smells?",
            "effect": "What effect has the smells had on you?",
        },
        "other-airborne": {
            "source": "The source of the emissions",
            "where": "Where are the emissions coming from?",
            "details": "Details of the emissions",
            "describe": "Can you describe the emissions?",
            "effect": "What effect have the emissions had on you?",
        },
        "rubbish": {
            "source": "The location of the rubbish",
            "where": "Where is the rubbish accumulation?",
            "details": "Details of the rubbish",
            "describe": "Can you describe the rubbish?",
            "effect": "What effect has the rubbish had on you?",
        },
        "waste": {
            "source": "The location of the waste",
            "where": "Where are the waste deposits?",
            "details": "Details of the waste",
            "describe": "Can you describe the waste?",
            "effect": "What effect has the waste had on you?",
        },
        "vermin-conditions": {
            "source": "The location of the rubbish",
            "where": "Where is the rubbish?",
            "details": "Details of the rubbish",
            "describe": "Can you describe the rubbish?",
            "effect": "What effect has the rubbish had on you?",
        },
        "needles": {
            "source": "The location of the needles",
            "where": "Where are the needles?",
            "details": "Details of the needles",
            "describe": "Can you describe the needles?",
            "effect": "What effect has the needles had on you?",
        },
        "overcrowding": {
            "where": "Where is the overcrowding?",
        },
        "bins": {
            "where": "Where are the bins?",
        },
        "foul-water": {
            "where": "Where is the water?",
        },
        "food": {
            "where": "Where is the food?",
        },
        "vegetation": {
            "where": "Where is the vegetation?",
        },
        "mould": {
            "where": "Where is the mould?",
        },
        "structural": {
            "where": "Where are the structural defects/disrepair?",
        },
        "animals": {
            "where": "Where are the animals?",
            "details": "Details of the animals",
            "describe": "Can you describe the animals?",
            "effect": "What effect have the animals had on you?",
        },
        "rodents": {
            "where": "Where are the rodents?",
            "details": "Details of the rodents",
            "describe": "Can you describe the rodents?",
            "effect": "What effect have the rodents had on you?",
        },
        "insects": {
            "where": "Where are the insects?",
            "details": "Details of the insects",
            "describe": "Can you describe the insects?",
            "effect": "What effect have the insects had on you?",
        },
    }

    kinds = [
        {
            "label": "Noise",
            "value": "noise",
            "kinds": {
                "animal": "Animal noise",
                "buskers": "Buskers",
                "car": "Car alarm",
                "construction": "Construction site noise",
                "deliveries": "Deliveries",
                "diy": "DIY",
                "alarm": "House / intruder alarm",
                "music-pub": "Music from pub",
                "music-club": "Music from club/bar",
                "music-other": "Music - other",
                "festival": "Noise caused by Religious Festivals",
                "roadworks": "Noise from roadworks",
                "road": "Noise on the road",
                "plant-machinery": "Plant noise - machinery",
                "plant-street": "Plant noise - machinery on street",
                "shouting": "Shouting",
                "tv": "TV",
                "other": "Other",
            },
        },
        {
            "value": "asb",
            "label": "Anti-social behaviour",
            "kinds": {
                "rowdy": "Rowdy or inconsiderate behaviour",
                "littering": "Littering and drug paraphernalia",
                "fireworks": "Misuse of fireworks",
                "drinking": "Street drinking",
                "trespassing": "Trespassing",
                "vehicle": "Vehicle nuisance",
            },
        },
        {
            "value": "light",
            "label": "Artificial light",
            "kinds": {
                "security-domestic": "Domestic security lights",
                "security-commercial": "Commercial security lights",
                "decorative": "Domestic decorative lighting",
                "exterior": "Exterior lighting of buildings and decorative lighting of landscapes",
                "laser": "Laser shows/sky beams/light art",
            },
        },
        {
            "value": "smoke",
            "label": "Smoke, fumes and gasses",
            "kinds": {
                "chimney": "Smoke from chimneys in a smoke control area",
                "dark": "Dark smoke from industrial and trade premises",
                "fumes-vehicle": "Fumes from poorly maintained vehicles or machinery",
                "fumes-heating": "Exhaust fumes from heating equipment or cooling systems",
            },
        },
        {
            "value": "dust",
            "label": "Dust, steam and odours",
            "kinds": {
                "dust": "Dust",
                "steam": "Steam",
                "smells": "Smells/odours",
                "other-airborne": "Other airborne emissions from industrial trade, or business premises",
            },
        },
        {
            "value": "deposits",
            "label": "Accumulations and deposits",
            "kinds": {
                "rubbish": "Rubbish accumulation",
                "waste": "Waste deposits",
                "vermin-conditions": "Conditions attracting vermin",
                "needles": "Discarded needles",
            },
        },
        {
            "value": "poor",
            "label": "Poor state of premises or land",
            "kinds": {
                "overcrowding": "Overcrowding",
                "bins": "Overflowing bins",
                "foul-water": "Foul, stagnant or obstructed water",
                "food": "Rotting food and other materials",
                "vegetation": "Dense, overgrown vegetation",
                "mould": "Mould infestation",
                "structural": "Structural defects and disrepair",
            },
        },
        {
            "value": "animals",
            "label": "Kept animals",
            "kinds": {
                "animals-dangerous": "Dangerous animals",
                "animals-nuisance": "Animals kept in a manner causing nuisance or health risks (excessive waste, noise, or smells)",
            },
        },
        {
            "value": "pest",
            "label": "Pest infestation",
            "kinds": {
                "rodents": "Rodents (rats or mice)",
                "insects": "Insects (e.g. bed bugs, clothes moths, carpet beetles, ants, cockroaches, fleas, booklice, wasps, or flies)",
            },
        },
    ]

    def address_candidates_for_postcode(self, postcode: str) -> List[AddressCandidate]:
        return [
            AddressCandidate(uprn=row["uprn"], label=row["label"])
            for row in addresses()
            if _normalize_pc(row["postcode"]) == (_normalize_pc(postcode))
        ]

    def address_detail_for_uprn(self, uprn: str) -> Optional[AddressDetail]:
        for row in addresses():
            if row["uprn"] == uprn:
                return AddressDetail(
                    uprn=uprn,
                    label=f"{row['label']}, {row['postcode']}",
                    point=Point(
                        float(row["easting"]), float(row["northing"]), srid=27700
                    ),
                    ward_gss=row["ward_gss"],
                    in_an_estate=None,
                )
        return None

    def location_candidates_for_string(self, string: str) -> List[LocationCandidate]:
        return hackney_cobrand.location_candidates_for_string(string)

    def location_detail_for_point(self, point: Point) -> Optional[LocationDetail]:
        ward = "outside"
        key = settings.MAPIT_API_KEY
        data = requests.get(
            f"https://mapit.mysociety.org/point/27700/{point.x},{point.y}?api_key={key}"
        ).json()
        if "2508" in data.keys():
            for area in data.values():
                if area["type"] == "LBW":
                    ward = area["codes"]["gss"]

        near_thing = random.choice(
            [
                "in Haggerston Park",
                "in Hackney Marshes",
                "in London Fields",
                "in Springfield Park",
                "near Bellfast Road",
                "near Clissold Crescent",
                "near Frampton Park Road",
                "near Grove Road",
                "near Glyn Road",
                "near Palatine Road",
                "near Stamford Hill",
                "near Wick Road",
            ]
        )
        return LocationDetail(
            point=point,
            description=f"a point {near_thing}",
            ward_gss=ward,
            in_an_estate=None,
        )

    def example_uprns(self) -> List[str]:
        return [row["uprn"] for row in addresses()]

    def staff_destination_email_addresses_for_case(self, case) -> List[str]:
        return ["staff-dest@example.org"]

    def override_email_colours(self) -> dict:
        color_black = "#000000"
        color_white = "#FFFFFF"
        color_purple = "#7B60B6"
        color_purple_dark = "#624D92"
        color_purple_pale = "#F4F1F9"

        body_background_color = color_purple_pale
        body_text_color = color_black
        header_background_color = color_purple
        header_text_color = color_white
        secondary_column_background_color = color_white
        button_background_color = color_purple_dark
        button_text_color = color_white

        logo_width = "200"  # pixel measurement, but without 'px' suffix
        logo_height = "45"  # pixel measurement, but without 'px' suffix
        logo_inline = {
            "id": make_msgid(domain="example.org")[1:-1],
            "data": inline_image_html("enviroworks-logo-white.png"),
        }
        header_padding = "20px 30px"

        return locals()

    def override_email_settings(self, settings: dict) -> dict:
        return {}
