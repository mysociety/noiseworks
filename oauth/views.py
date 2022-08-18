from authlib.integrations.base_client import MismatchingStateError
from authlib.integrations.django_client import OAuth
from django.contrib.auth import get_user_model, login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=CONF_URL,
    client_kwargs={
        "scope": "openid email profile",
    },
)

User = get_user_model()


def authenticate(request):
    redirect_uri = request.build_absolute_uri(reverse("oauth:verify"))
    client = oauth.google
    redirect = client.authorize_redirect(request, redirect_uri)
    return redirect


def verify(request):
    client = oauth.google
    try:
        token = client.authorize_access_token(request)
    except MismatchingStateError:
        return render(request, "oauth/error.html", status=403)

    userinfo = token["userinfo"]
    if (
        userinfo["aud"] != client.client_id
        or userinfo["hd"] != client.authorize_params["hd"]
    ):
        raise PermissionDenied

    email = userinfo["email"].lower()
    try:
        user = User.objects.get(email=email, email_verified=True)
    except User.DoesNotExist:
        user = User.objects.create_user(email=email)
    user.first_name = userinfo["given_name"]
    user.last_name = userinfo["family_name"]
    user.save()

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(reverse("cases") + "?assigned=me")
