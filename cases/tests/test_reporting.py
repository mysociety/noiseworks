import datetime
from functools import partial
import re
import pytest
from pytest_django.asserts import assertContains
from accounts.models import User
from ..models import Case, Complaint
from ..forms import WhereMapForm

pytestmark = pytest.mark.django_db

ADDRESS = {
    "line1": "LINE 1",
    "line2": "LINE 2",
    "line3": "LINE 3",
    "line4": "",
    "town": "LONDON",
    "postcode": "E8 1DY",
    "UPRN": 10008315925,
    "locality": "HACKNEY",
    "ward": "Hackney Central",
    "longitude": -0.0575203934113829,
    "latitude": 51.5449668465297,
}


@pytest.fixture
def normal_user(db):
    return User.objects.create(
        username="normal@example.org",
        email="normal@example.org",
        email_verified=True,
        phone="+447700900123",
        address="1 High Street",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def mocks(requests_mock):
    requests_mock.get(
        re.compile(r"postcode=E8\+3DY"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile(r"postcode=BAD"), json={"error": "Error goes here"})
    requests_mock.get(re.compile(r"postcode=SW1A\+1AA"), json={"error": "Bad postcode"})
    requests_mock.get(
        re.compile(r"uprn=10008315925"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile(r"q=Foobar0"), json=[])
    requests_mock.get(
        re.compile(r"q=Foobar1"),
        json=[
            {"lat": 51, "lon": -0.05, "display_name": "Result"},
        ],
    )
    requests_mock.get(
        re.compile(r"q=Foobar2"),
        json=[
            {"lat": 51, "lon": -0.05, "display_name": "Result"},
            {"lat": 52, "lon": -0.06, "display_name": "Another"},
        ],
    )
    requests_mock.get(re.compile(r"typename=greenspaces"), json={"features": []})
    requests_mock.get(re.compile(r"typename=transport"), json={"features": []})


def test_new_existing_form(admin_client):
    admin_client.post("/cases/add/existing", {"get": "Start"})
    admin_client.get("/cases/add/existing")
    admin_client.post("/cases/add/existing", {"existing": "existing"})
    admin_client.post("/cases/add/existing", {"existing": "new"})


def _post_step(client, step, data, **kwargs):
    data = {f"{step}-{k}": v for k, v in data.items()}
    as_is = kwargs.pop("asis", {})
    data.update(as_is)
    return client.post(
        f"/cases/add/{step}",
        {f"reporting_wizard-current_step": step, **data},
        **kwargs,
    )


def test_staff_case_creation(admin_client, normal_user, mocks):
    """Picks existing user, UPRN based source"""
    post_step = partial(_post_step, admin_client)
    admin_client.get(f"/cases/add/begin")
    post_step("user_search", {"search": "Normal"})
    post_step("user_pick", {"search": "Normal", "user": normal_user.id})
    post_step("best_time", {"best_time": "weekday", "best_method": "email"})
    post_step("kind", {"kind": "diy"}, follow=True)
    post_step("where", {"where": "business"})
    post_step("where-location", {"search": "SW1A 1AA"})
    post_step("where-location", {"search": "Foobar0"})
    post_step("where-location", {"search": "E8 3DY"})
    post_step("where-postcode-results", {"source_uprn": "10008315925"})
    post_step("isitnow", {"happening_now": "1"})
    post_step("isnow", {"start_date": "today", "start_time": "9pm"})
    post_step("rooms", {"rooms": "Room"})
    post_step("describe", {"description": "Desc"})
    resp = post_step("effect", {"effect": "Effect"}, follow=True)
    assertContains(resp, "Normal User, 1 High Street")
    assertContains(resp, "weekday, by email")
    assertContains(resp, "DIY")
    assertContains(resp, "A shop, bar, nightclub")
    assertContains(resp, "Line 1, Line 2, Line 3")
    today = datetime.date.today()
    assertContains(resp, f"{today.strftime('%a, %d %b %Y')}, 9 p.m.")
    post_step("summary", {"true_statement": 1}, follow=True)
    assert Case.objects.count() == 1
    assert Complaint.objects.count() == 1


def test_staff_case_creation_new_user_map(admin_client, normal_user, mocks):
    """Picks new user, map based source"""
    post_step = partial(_post_step, admin_client)
    admin_client.get(f"/cases/add/begin")
    post_step("user_search", {"search": "Different"})
    post_step(
        "user_pick",
        {
            "search": "Different",
            "user": "0",
            "first_name": "Different",
            "last_name": "User",
            "address": "Address",
        },
    )
    post_step("best_time", {"best_time": "weekday", "best_method": "email"})
    post_step("kind", {"kind": "diy"})
    post_step("where", {"where": "business"})
    post_step("where-location", {"search": "Foobar2"})
    post_step("where-geocode-results", {"geocode_result": "-0.05,51"})
    post_step("where-map", {"point": "POINT (-0.05 51)", "radius": 180, "zoom": 16})
    post_step("isitnow", {"happening_now": "0"})
    post_step(
        "notnow",
        {
            "start_date_0": "17",
            "start_date_1": "11",
            "start_date_2": "2021",
            "start_time": "2am",
            "end_time": "3am",
        },
    )
    post_step("rooms", {"rooms": "Room"})
    post_step("describe", {"description": "Desc"})
    resp = post_step("effect", {"effect": "Effect"}, follow=True)
    assertContains(resp, "Different User, Address")
    assertContains(resp, "weekday, by email")
    assertContains(resp, "DIY")
    assertContains(resp, "A shop, bar, nightclub")
    assertContains(resp, "180m around (536926,124099)")
    assertContains(resp, "Wed, 17 Nov 2021, 2 a.m.")
    assertContains(resp, "Wed, 17 Nov 2021, 3 a.m.")
    post_step("summary", {"true_statement": 1}, follow=True)


def test_user_case_creation(client, normal_user, mocks):
    """Gives details, picks address, map-based case"""
    client.force_login(normal_user)
    post_step = partial(_post_step, client)
    client.get(f"/cases/add/begin")
    resp = post_step(
        "about",
        {
            "first_name": "Normal",
            "last_name": "User",
            "email": "normal@example.org",
            "phone": "+447900000000",
        },
    )
    post_step("best_time", {"best_time": "weekday", "best_method": "email"})
    post_step("postcode", {"postcode": "BAD"})
    post_step("postcode", {"postcode": "E8 3DY"})
    post_step("postcode", {"postcode": "E8 3DY", "addresses": "missing"})
    post_step("postcode", {"postcode": "E8 3DY", "addresses": "10008315925"})
    post_step("kind", {"kind": "other"})
    post_step("kind", {"kind": "other", "kind_other": "Other"})
    post_step("where", {"where": "business"})
    post_step("where-location", {"search": "Foobar1"})

    # Couple of non-JS requests in here to test that
    post_step(
        "where-map",
        {"zoom": 16, "radius": 180},
        asis={"tile_32757.21781.x": 200 + 512, "tile_32757.21781.y": 100 - 512},
    )
    post_step(
        "where-map",
        {"point": "POINT (-0.0568638 51.5453904)", "radius": 180},
        asis={"change-zoom": 17},
    )

    post_step("where-map", {"point": "POINT (-0.05 51)", "radius": 180, "zoom": 16})
    post_step("isitnow", {"happening_now": "1"})
    post_step("isnow", {"start_date": "today", "start_time": "9pm"})
    post_step("rooms", {"rooms": "Room"})
    post_step("describe", {"description": "Desc"})
    resp = post_step("effect", {"effect": "Effect"}, follow=True)
    assertContains(resp, "Normal User, No address, normal@example.org, +447900000000")
    assertContains(resp, "weekday, by email")
    assertContains(resp, "Other")
    assertContains(resp, "A shop, bar, nightclub")
    assertContains(resp, "180m around (536926,124099)")
    today = datetime.date.today()
    assertContains(resp, f"{today.strftime('%a, %d %b %Y')}, 9 p.m.")
    post_step("summary", {"true_statement": 1}, follow=True)


def test_error_conditions(admin_client, mocks):
    form = WhereMapForm()
    assert re.search(r"L.LatLng\(, \)", str(form))

    admin_client.get("/cases/add/user_pick")