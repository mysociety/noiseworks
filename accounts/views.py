import base64
from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from sesame.tokens import create_token
from sesame.utils import get_user
from noiseworks.base32 import bytes_to_base32
from noiseworks.message import send_sms, send_email
from .forms import SignInForm, CodeForm

User = get_user_model()


def token_url(request, token):
    user = get_user(token)
    if user is None:
        raise PermissionDenied
    login(request, user)
    return redirect("/")


def code(request):
    form = CodeForm(request.POST or None)
    if form.is_valid():
        user = form.user
        login(request, user)
        return redirect("/")
    return render(request, "accounts/form_token.html", {"form": form})


def show_form(request):
    form = SignInForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data["username"]
        username_type = form.cleaned_data["username_type"]
        # XXX email/phone/verified
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User.objects.create_user(username=username)
        if user.is_staff:
            raise PermissionDenied

        token = create_token(user)

        # Immediately decode again to get out the timestamp/signature separately
        data = base64.urlsafe_b64decode(token.encode() + b"=" * (-len(token) % 4))
        timestamp = bytes_to_base32(data[4:8])
        signature = bytes_to_base32(data[8:])

        url = request.build_absolute_uri(
            reverse("accounts:token", kwargs={"token": token})
        )

        if username_type == "email":
            send_email(
                user.email,
                "Access your noise cases",
                "accounts/email_signin",
                {"url": url, "signature": signature},
            )
        else:  # username_type will be "phone"
            send_sms(
                str(user.phone),
                f"Please click the following link to access your noise cases:\n\n{url}\n\nOr enter this token: {signature}",
            )

        form = CodeForm(initial={"username": username, "timestamp": timestamp})
        return render(request, "accounts/form_token.html", {"form": form})

    template = "accounts/form_signin.html"
    return render(request, template, {"form": form})
