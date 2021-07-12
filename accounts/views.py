from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from sesame.tokens import create_token
from sesame.utils import get_user
from noiseworks.message import send_sms, send_email
from .forms import SignInForm

User = get_user_model()


def token(request, token):
    user = get_user(token)
    if user is None:
        raise PermissionDenied
    login(request, user)
    return redirect("/")


def show_form(request):
    form = SignInForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data["username"]
        username_type = form.cleaned_data["username_type"]
        user, _ = User.objects.get_or_create(username=username)
        if user.is_staff:
            raise PermissionDenied
        token = create_token(user)

        url = request.build_absolute_uri(
            reverse("accounts:token", kwargs={"token": token})
        )
        if username_type == "email":
            send_email(
                user.email,
                "Access your noise cases",
                "accounts/email_signin",
                {"url": url},
            )
        else:  # username_type will be "phone"
            send_sms(
                str(user.phone),
                f"Please click the following link to access your noise cases:\n\n{url}",
            )
        return render(request, "accounts/form_token.html", {})
    template = "accounts/form_signin.html"
    return render(request, template, {"form": form})
