from django.contrib.auth import login, get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from sesame.tokens import create_token
from sesame.utils import get_user
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
    template = "accounts/form_signin.html"
    if form.is_valid():
        username = form.cleaned_data["username"]
        user, _ = User.objects.get_or_create(username=username)
        if user.is_staff:
            raise PermissionDenied
        token = create_token(user)
        # Send token by email or phone, dependent on !
        reverse("accounts:token", kwargs={"token": token})
        return render(request, "accounts/form_token.html", {"token": token})
    return render(request, template, {"form": form})
