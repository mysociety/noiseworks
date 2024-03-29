import base64
from math import ceil

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from sesame.tokens import create_token
from sesame.utils import get_user

from noiseworks.base32 import bytes_to_base32
from noiseworks.decorators import staff_member_required
from noiseworks.message import send_email, send_sms

from .forms import CodeForm, EditStaffForm, EditUserForm, StaffSettingsForm, SignInForm

User = get_user_model()


def token_url(request, token):
    token_length = ceil((settings.SESAME_SIGNATURE_SIZE + 8) * 4 / 3)
    token = "A" * (token_length - len(token)) + token
    user = get_user(token)
    if user is None:
        raise PermissionDenied
    login(request, user)
    return redirect("cases")


def code(request):
    form = CodeForm(request.POST or None)
    if form.is_valid():
        user = form.user
        login(request, user)
        return redirect("cases")
    return render(request, "accounts/form_token.html", {"form": form})


def signout(request):
    logout(request)
    return render(request, "accounts/signout.html")


def show_form(request):
    if not settings.NON_STAFF_ACCESS:
        return redirect("/")
    form = SignInForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data["username"]
        username_type = form.cleaned_data["username_type"]
        try:
            if username_type == "email":
                user = User.objects.get(email=username, email_verified=True)
            else:
                user = User.objects.get(phone=username, phone_verified=True)
        except User.DoesNotExist:
            if username_type == "email":
                user = User.objects.create_user(email=username)
            else:
                user = User.objects.create_user(phone=username)
        if user.is_staff:
            raise PermissionDenied

        token = create_token(user)

        # Immediately decode again to get out the timestamp/signature separately
        data = base64.urlsafe_b64decode(token.encode() + b"=" * (-len(token) % 4))
        timestamp = bytes_to_base32(data[4:8])
        signature = bytes_to_base32(data[8:])

        url = request.build_absolute_uri(
            reverse("accounts:token", kwargs={"token": token.lstrip("A")})
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
                f"Your Hackney NoiseWorks sign in token is {signature}\n\nAlternatively, you can sign in on this device by following this link:\n\n{url}",
            )

        form = CodeForm(initial={"user_id": user.id, "timestamp": timestamp})
        return render(
            request,
            "accounts/form_token.html",
            {"form": form, "username_type": username_type},
        )

    template = "accounts/form_signin.html"
    return render(request, template, {"form": form})


@staff_member_required
def add(request):
    if not request.user.has_perm("accounts.add_user"):
        raise PermissionDenied
    form = EditStaffForm(True, request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "That user has been added")
        return redirect("accounts:list")
    return render(request, "accounts/edit.html", {"form": form})


@staff_member_required
def edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    perm = request.user.has_perm("accounts.change_user")
    if user.is_staff:
        if not perm:
            raise PermissionDenied
        form = EditStaffForm(True, request.POST or None, instance=user)
    else:
        can_edit_contact_warning = request.user.has_perm(
            "accounts.edit_contact_warning"
        )
        form = EditUserForm(
            perm,
            request.POST or None,
            instance=user,
            can_edit_contact_warning=can_edit_contact_warning,
        )
    if form.is_valid():
        form.save()
        if request.GET.get("case"):
            return redirect("case-view", request.GET.get("case"))
        messages.success(request, "That user has been edited")
        return redirect("accounts:list")
    return render(request, "accounts/edit.html", {"form": form})


@staff_member_required
def list(request):
    users = User.objects.filter(is_staff=True)
    return render(request, "accounts/list.html", {"users": users})


@staff_member_required
def staff_settings(request):
    form = StaffSettingsForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect("cases")
    return render(request, "accounts/staff_settings.html", {"form": form})
