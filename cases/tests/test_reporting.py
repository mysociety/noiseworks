import datetime
from functools import partial
import re
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from django.core import mail
from django.contrib.gis.geos import Point
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

POINT = Point(-0.05, 51, srid=4326)
POINT.transform(27700)


@pytest.fixture
def normal_user(db):
    return User.objects.create(
        username="normal@example.org",
        email="normal@example.org",
        email_verified=True,
        phone="+447900000000",
        address="1 High Street",
        first_name="Normal",
        last_name="User",
        best_time=["weekends"],
        best_method="phone",
    )


@pytest.fixture
def mocks(requests_mock, settings):
    settings.COBRAND_SETTINGS["staff_destination"] = {
        "outside": "outside@example.org",
        "business": "business@example.org",
        "hackney-housing": "hh@example.org,hh2@example.org",
        "housing": "housing@example.org",
    }

    requests_mock.get(
        re.compile(r"postcode=E8\+3DY"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile(r"postcode=BAD"), json={"error": "Error goes here"})
    requests_mock.get(re.compile(r"postcode=SW1A\+1AA"), json={"error": "Bad postcode"})
    requests_mock.get(re.compile(r"postcode=E1\+6GB"), json={"data": {"address": []}})
    requests_mock.get(
        re.compile(r"uprn=10008315925"), json={"data": {"address": [ADDRESS]}}
    )
    requests_mock.get(re.compile(r"q=Foobar0"), json=[])
    requests_mock.get(
        re.compile(r"q=Foobar1"),
        json=[
            {"lat": 51, "lon": -0.05, "display_name": "Result, Hackney, London"},
        ],
    )
    requests_mock.get(
        re.compile(r"q=Foobar2"),
        json=[
            {"lat": 51, "lon": -0.05, "display_name": "Result, Hackney, London"},
            {"lat": 52, "lon": -0.06, "display_name": "Another, Hackney, London"},
            {"lat": 90, "lon": 0, "display_name": "North Pole"},
        ],
    )
    requests_mock.get(
        re.compile("point/27700"),
        json={
            "2508": {"type": "LBO", "name": "Hackney"},
            "144391": {
                "type": "LBW",
                "codes": {"gss": "E05009378"},
                "name": "Hoxton West",
            },
        },
    )
    requests_mock.get(re.compile(r"typename=greenspaces"), json={"features": []})
    requests_mock.get(re.compile(r"typename=transport"), json={"features": []})


def test_new_existing_form(admin_client):
    admin_client.post("/cases/add/existing", {"get": "Start"})
    admin_client.get("/cases/add/existing")
    admin_client.post("/cases/add/existing", {"existing": "existing"})
    admin_client.post("/cases/add/existing", {"existing": "new"})


def test_user_new_existing_form(client, settings):
    settings.NON_STAFF_ACCESS = False
    resp = client.post("/cases/add/existing", {"get": "Start"})
    assert resp.status_code == 302


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
    resp = post_step("where-location", {"search": "E16GB"}, follow=True)
    assertContains(resp, "could not recognise that postcode")
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
    assertContains(resp, f"{today.strftime('%a, %-d %b %Y')}, 9 p.m.")
    post_step("summary", {"true_statement": 1}, follow=True)
    assert Case.objects.count() == 1
    case = Case.objects.all()[0]
    assert case.created_by_id and case.created_by_id == case.modified_by_id
    assert Complaint.objects.count() == 1
    normal_user.refresh_from_db()
    assert normal_user.first_name == "Normal"
    admin_client.get(f"/cases/add/summary")


def test_staff_case_creation_existing_user(admin_client, normal_user, mocks):
    post_step = partial(_post_step, admin_client)
    admin_client.get(f"/cases/add/begin")
    post_step("user_search", {"search": "Something with no results"})
    params = {
        "search": "Something with no results",
        "user": "0",
        "first_name": "Normal",
        "last_name": "User",
        "email": "normal@example.org",
    }
    post_step("user_pick", params)
    resp = post_step("user_pick", dict(params, user=normal_user.id), follow=True)
    assertNotContains(resp, 'Select a valid choice.')


def test_staff_case_creation_new_user_map(admin_client, admin_user, normal_user, mocks):
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
    resp = post_step("where", {"where": "residence"})
    assertContains(resp, "Please pick the type of residence")
    post_step("where", {"where": "residence", "estate": "y"})
    resp = post_step("where-location", {"search": "Foobar2"}, follow=True)
    assertContains(resp, "Another")
    assertNotContains(resp, "North Pole")
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
    assertContains(resp, "A house, flat, park or street")
    assertContains(resp, f"180m around ({POINT.x:.0f},{POINT.y:.0f})")
    assertContains(resp, "Wed, 17 Nov 2021, 2 a.m.")
    assertContains(resp, "Wed, 17 Nov 2021, 3 a.m.")
    post_step("summary", {"true_statement": 1}, follow=True)
    assert len(mail.outbox) == 1
    assert len(mail.outbox[0].to) == 2
    admin_user.refresh_from_db()
    assert admin_user.first_name == ""


def test_non_staff_user_case_creation(client, settings):
    settings.NON_STAFF_ACCESS = False
    resp = client.get(f"/cases/add/begin")
    assert resp.status_code == 302


@pytest.mark.parametrize(
    "logged_in,email_verified,phone_verified",
    [
        (False, True, True),
        (False, True, False),
        (False, False, True),
        (False, False, False),
        (True, True, False),
        (True, False, True),
    ],
)
def test_user_case_creation(
    logged_in, email_verified, phone_verified, normal_user, client, mocks, settings
):
    """Gives details, picks address, map-based case"""
    settings.NON_STAFF_ACCESS = True

    if logged_in:
        client.force_login(normal_user)
    normal_user.email_verified = email_verified
    normal_user.phone_verified = phone_verified
    normal_user.save()

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
    post_step("postcode", {"postcode": "E1 6GB"}, follow=True)
    post_step("postcode", {"postcode": "E8 3DY"})
    post_step("address", {"addresses": "missing"})
    post_step("address", {"address_uprn": "10008315925"})
    post_step("kind", {"kind": "other"})
    resp = post_step("kind", {"kind": "other", "kind_other": "Other " * 20})
    assertContains(resp, "at most 100 characters")
    post_step("kind", {"kind": "other", "kind_other": "Other"})
    post_step("where", {"where": "residence", "estate": "?"})
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
    assertContains(
        resp,
        "Normal User, Line 1, Line 2, Line 3, E8 1DY, normal@example.org, +447900000000",
    )
    assertContains(resp, "weekday, by email")
    assertContains(resp, "Other")
    assertContains(resp, "A house, flat, park or street")
    assertContains(resp, f"180m around ({POINT.x:.0f},{POINT.y:.0f})")
    today = datetime.date.today()
    assertContains(resp, f"{today.strftime('%a, %-d %b %Y')}, 9 p.m.")
    resp = post_step("summary", {"true_statement": 1}, follow=True)
    if not logged_in:
        m = re.search(r"confirmation token is (\d+)", mail.outbox[-1].body)
        mail.outbox = []
        code = int(m.group(1))
        resp = post_step("confirmation", {"code": code + 1})
        assertContains(resp, "Incorrect or expired code")
        resp = post_step("confirmation", {"code": str(code).zfill(6)}, follow=True)
    assertContains(resp, "Thank you for reporting")
    client.get(
        f"/cases/add/address"
    )  # Test fetching this page after submission does not error

    if not logged_in and (email_verified or phone_verified):
        assert Case.objects.count() == 1
        case = Case.objects.all()[0]
        assert case.created_by_id == normal_user.id

    assert len(mail.outbox) == 2
    assert len(mail.outbox[0].to) == 1
    for r in range(2):
        email = mail.outbox[r]
        assert "new noise report has been submitted" in email.body
        assert f"180m around ({POINT.x:.0f},{POINT.y:.0f})" in email.body
        assert "Hoxton West" in email.body
        assert "9 p.m." in email.body
        if r == 0:
            assert "Line 1, Line 2, Line 3" in email.body
            assert "weekday, by email" in email.body
        else:
            assert "weekday, by email" not in email.body
            assert "Line 1, Line 2, Line 3" not in email.body
    mail.outbox = []


def test_error_conditions(admin_client, mocks):
    form = WhereMapForm()
    assert re.search(r"L.LatLng\(, \)", str(form))

    admin_client.get("/cases/add/user_pick")
