from django.contrib.auth import get_user_model, login
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from authlib.integrations.django_client import OAuth

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
    token = client.authorize_access_token(request)
    userinfo = token["userinfo"]
    if (
        userinfo["aud"] != client.client_id
        or userinfo["hd"] != client.authorize_params["hd"]
    ):
        return HttpResponseForbidden()

    email = userinfo["email"]
    try:
        user = User.objects.get(username=email)
    except User.DoesNotExist:
        user = User.objects.create_user(username=email, is_staff=True)
    user.first_name = userinfo["given_name"]
    user.last_name = userinfo["family_name"]
    user.save()

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("/")  # XXX
