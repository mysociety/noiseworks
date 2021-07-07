from urllib.parse import urlparse, parse_qs
import pytest
from authlib.jose import jwk
from authlib.oidc.core.grants.util import generate_id_token
import requests
from django.contrib.auth import get_user_model
from oauth.views import oauth

# Replace the oauth value in views.py (XXX Do this a better way?)
key = jwk.dumps("secret", "oct")
del oauth._clients["google"]
oauth.register(
    "google",
    jwks={"keys": [key]},
    client_id="cid",
    access_token_url="https://i.b/token",
    authorize_url="https://i.b/authorize",
    authorize_params={
        "hd": "example.org",
    },
    client_kwargs={
        "scope": "openid email profile",
    },
)

pytestmark = pytest.mark.django_db


def test_authenticate(client):
    response = client.get("/oauth/authenticate")
    assert response.status_code == 302
    qs = parse_qs(urlparse(response.url).query)
    assert qs["response_type"][0] == "code"
    assert qs["scope"][0] == "openid email profile"
    assert urlparse(qs["redirect_uri"][0]).path == "/oauth/verify"


def test_oauth_bad_domain(client, requests_mock):
    response = client.get("/oauth/authenticate")
    qs = parse_qs(urlparse(response.url).query)
    token = _gen_token(qs["nonce"][0], "different.example.org")
    requests_mock.post("https://i.b/token", json=token)
    response = client.post("/oauth/verify", {"state": qs["state"][0], "code": "foo"})
    assert response.status_code == 403

    User = get_user_model()
    assert User.objects.count() == 0


def test_oauth_success(client, requests_mock):
    response = client.get("/oauth/authenticate")
    qs = parse_qs(urlparse(response.url).query)
    token = _gen_token(qs["nonce"][0], "example.org")
    requests_mock.post("https://i.b/token", json=token)
    response = client.post("/oauth/verify", {"state": qs["state"][0], "code": "foo"})
    assert response.status_code == 302

    User = get_user_model()
    u = User.objects.get(username="matthew@example.org")
    assert u.first_name == "Matthew"


def _gen_token(nonce, domain):
    token = {"token_type": "Bearer", "access_token": "at", "expires_in": 3600}
    token["id_token"] = generate_id_token(
        token,
        {
            "email": f"matthew@{domain}",
            "name": "Matthew Smith",
            "given_name": "Matthew",
            "family_name": "Smith",
            "sub": "123",
            "hd": domain,
        },
        key,
        alg="HS256",
        iss="iss",
        aud="cid",
        nonce=nonce,
    )
    return token