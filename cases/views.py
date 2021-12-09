import datetime
import random
import re
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from formtools.wizard.views import NamedUrlSessionWizardView
from noiseworks.decorators import staff_member_required
from noiseworks.message import send_sms, send_email
from .filters import CaseFilter
from .models import Case, Complaint, Action, ActionType
from . import forms
from accounts.models import User
from . import map_utils


@login_required
def case_list(request):
    if request.user.is_staff:
        return case_list_staff(request)
    elif settings.NON_STAFF_ACCESS:
        return case_list_user(request)
    else:
        return redirect("/")


@login_required
def case_list_user(request):
    cases = Case.objects.by_complainant(request.user)
    out = []
    for case in cases:
        out.append(case.original_entry())
    return render(
        request,
        "cases/case_list_user.html",
        {"cases": out},
    )


@staff_member_required
def case_list_staff(request):
    qs = Case.objects.unmerged()
    f = CaseFilter(request.GET, queryset=qs, request=request)

    paginator = Paginator(f.qs, 20)
    page_number = request.GET.get("page")
    qs = paginator.get_page(page_number)

    merge_map = Action.objects.get_merged_cases(qs)
    actions_by_case = Action.objects.get_reversed(merge_map)

    # Set the actions for each result to the right ones
    for case in qs:
        case.actions_reversed = actions_by_case.get(case.id, [])

    return render(
        request,
        "cases/case_list_staff.html",
        {
            "filter": f,
            "qs": qs,
            "user_wards": request.user.wards or [],
        },
    )


@login_required
def case(request, pk):
    if request.user.is_staff:
        return case_staff(request, pk)
    elif settings.NON_STAFF_ACCESS:
        return case_user(request, pk)
    else:
        return redirect("/")


@login_required
def case_user(request, pk):
    qs = Case.objects.by_complainant(request.user)
    qs = qs.select_related("assigned")
    case = get_object_or_404(qs, pk=pk)
    case = case.original_entry()
    return render(request, "cases/case_detail_user.html", context={"case": case})


@staff_member_required
def case_staff(request, pk):
    qs = Case.objects.select_related("assigned").prefetch_related("perpetrators")
    case = get_object_or_404(qs, pk=pk)

    # redirect = case.merged_into
    # if redirect:
    #    return redirect(redirect)

    is_follower = case.followers.filter(pk=request.user.id)

    return render(
        request,
        "cases/case_detail_staff.html",
        context={"case": case, "is_follower": is_follower},
    )


@staff_member_required
def reassign(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.ReassignForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
        user = form.cleaned_data["assigned"]
        case.followers.add(user)
        if user.id != request.user.id:
            url = request.build_absolute_uri(case.get_absolute_url())
            send_email(
                user.email,
                "You have been assigned",
                "cases/email_assigned",
                {"case": case, "url": url, "user": user, "by": request.user},
            )
        return redirect(case)
    return render(
        request,
        "cases/reassign.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def followers(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.FollowersForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
        return redirect(case)
    return render(
        request,
        "cases/followers.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def follower_state(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if not request.POST:
        raise PermissionDenied
    user = request.user
    if request.POST.get("add"):
        case.followers.add(user)
    else:
        case.followers.remove(user)
    return redirect(case)


@staff_member_required
def edit_kind(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.KindForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
        return redirect(case)
    return render(
        request,
        "cases/edit-kind.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def edit_location(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.LocationForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
        return redirect(case)
    return render(
        request,
        "cases/edit-location.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def search_perpetrator(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.PersonSearchForm(request.POST or None)
    if form.is_valid():
        form = forms.PerpetratorPickForm(
            initial={"search": form.cleaned_data["search"]}
        )
        form.helper.form_action = reverse("case-add-perpetrator", args=[case.id])
    return render(
        request,
        "cases/add-perpetrator.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def add_perpetrator(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if not request.POST:
        raise PermissionDenied
    form = forms.PerpetratorPickForm(request.POST)
    if form.is_valid():
        form.save(case=case)
        return redirect(case)
    return render(
        request,
        "cases/add-perpetrator.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def remove_perpetrator(request, pk, perpetrator):
    case = get_object_or_404(Case, pk=pk)
    user = get_object_or_404(User, pk=perpetrator)
    case.perpetrators.remove(user)
    # TODO Centralise this action creation somewhere?
    typ, _ = ActionType.objects.get_or_create(
        name="Edit case", defaults={"visibility": "internal"}
    )
    Action.objects.create(case=case, type=typ, notes="Removed perpetrator")
    return redirect(case)


@staff_member_required
def log_action(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.ActionForm(request.POST or None)
    if form.is_valid():
        form.save(case=case)
        return redirect(case)
    return render(
        request,
        "cases/action_form.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def merge(request, pk):
    case = get_object_or_404(Case, pk=pk)

    if request.POST.get("stop"):
        return merge_stop(request, case)
    elif request.POST.get("dupe") and request.session.get("merging_case"):
        return merge_action(request, case)
    else:
        return merge_start(request, case)


def merge_stop(request, case):
    if "merging_case" in request.session:
        del request.session["merging_case"]
        messages.success(request, "We have forgotten your current merging.")
    return redirect(case)


def merge_action(request, case):
    other_id = request.session["merging_case"]["id"]
    other = Case.objects.get(pk=other_id)
    other.merge_into(case)
    del request.session["merging_case"]
    messages.success(request, f"Case #{other_id} has been merged into this case.")
    return redirect(case)


def merge_start(request, case):
    request.session["merging_case"] = {
        "id": case.id,
        "name": f"#{case.id}",
    }

    cases_same_uprn = Case.objects.filter(uprn=case.uprn).exclude(id=case.id)
    cases_nearby = Case.objects.filter(point__dwithin=(case.point, D(m=500))).exclude(
        id=case.id
    )

    return render(
        request,
        "cases/merged_start.html",
        {
            "case": case,
            "cases_same_uprn": cases_same_uprn,
            "cases_nearby": cases_nearby,
        },
    )


@login_required
def complaint(request, pk, complaint):
    if not request.user.is_staff and not settings.NON_STAFF_ACCESS:
        return redirect("/")

    case = get_object_or_404(Case, pk=pk)
    complaint = get_object_or_404(
        Complaint.objects.select_related("case"), pk=complaint
    )
    merge_map = case.action_merge_map
    case_ids = merge_map.keys()
    if complaint.case.id not in case_ids:
        return redirect(case)
    return render(
        request,
        "cases/complaint_detail.html",
        context={"case": case, "complaint": complaint},
    )


# Conditionals for form step display


def show_postcode_results_form(wizard):
    data = wizard.storage.get_step_data("where-location") or {}
    return data.get("postcode_results")


def show_geocode_results_form(wizard):
    data = wizard.storage.get_step_data("where-location") or {}
    return data.get("geocode_results")


def show_map_form(wizard):
    data1 = wizard.storage.get_step_data("where-location") or {}
    data2 = wizard.get_cleaned_data_for_step("where-geocode-results") or {}
    return data1.get("geocode_result") or data2.get("geocode_result")


def show_happening_now_form(wizard):
    data = wizard.get_cleaned_data_for_step("isitnow") or {}
    return data.get("happening_now")


def show_not_happening_now_form(wizard):
    return not show_happening_now_form(wizard)


def show_user_form(wizard):
    user = wizard.request.user
    return user.is_active and user.is_staff


def show_about_form(wizard):
    return not show_user_form(wizard)


def show_confirmation_step(wizard):
    user = wizard.request.user
    return not user.is_authenticated


class RecurrenceWizard(LoginRequiredMixin, NamedUrlSessionWizardView):
    template_name = "cases/complaint_add.html"
    context_object_name = "case"
    model = Case

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_staff:
            qs = Case.objects.all()
        elif settings.NON_STAFF_ACCESS and user.is_authenticated:
            qs = Case.objects.by_complainant(user)
        else:
            return redirect("/")
        self.object = get_object_or_404(qs, pk=kwargs["pk"])

        return super().dispatch(request, *args, **kwargs)

    def get(self, *args, **kwargs):
        """Always reset if begin page visited."""
        step_url = kwargs.get("step", None)
        if step_url is None:
            self.storage.reset()
            # self.storage.current_step = self.steps.first
            return redirect(self.get_step_url(self.steps.current))
        return super().get(*args, **kwargs)

    def get_prefix(self, request, *args, **kwargs):
        """To make sure we have separate stored wizard data per case per session"""
        prefix = super().get_prefix(request, *args, **kwargs)
        prefix = f"{prefix}_{self.object.id}"
        return prefix

    def get_step_url(self, step):
        """As we additionally have the case ID in the url"""
        return reverse(self.url_name, kwargs={"pk": self.object.id, "step": step})

    def get_context_data(self, **kwargs):
        kwargs["case"] = self.object
        data = kwargs["data"] = self.get_all_cleaned_data()

        if data.get("user"):
            user = User.objects.get(id=data["user"])
            kwargs["reporting_user"] = user
        elif data.get("last_name"):
            kwargs[
                "reporting_user"
            ] = f"{data['first_name']} {data['last_name']}, {data['address']}, {data['email']}, {data['phone']}"

        return super().get_context_data(**kwargs)

    def get_form_initial(self, step):
        """The user pick form needs the search query passed to it"""
        if step == "user_pick":
            data = self.get_cleaned_data_for_step("user_search")
            if data:
                return {"search": data["search"]}
        return super().get_form_initial(step)

    form_list = [
        ("isitnow", forms.IsItHappeningNowForm),
        ("isnow", forms.HappeningNowForm),
        ("notnow", forms.NotHappeningNowForm),
        ("rooms", forms.RoomsAffectedForm),
        ("describe", forms.DescribeNoiseForm),
        ("effect", forms.EffectForm),
        ("user_search", forms.RecurrencePersonSearchForm),
        ("user_pick", forms.PersonPickForm),
        ("summary", forms.SummaryForm),
    ]

    condition_dict = {
        "isnow": show_happening_now_form,
        "notnow": show_not_happening_now_form,
        "user_search": show_user_form,
        "user_pick": show_user_form,
    }

    def done(self, form_list, form_dict, **kwargs):
        # Save a new user if need be
        if "user_pick" in form_dict:
            picker = form_dict["user_pick"]
            user = picker.save()
        else:
            user = self.request.user.id

        data = self.get_all_cleaned_data()
        start = datetime.datetime.combine(
            data["start_date"],
            data["start_time"],
            tzinfo=timezone.get_current_timezone(),
        )
        if data["happening_now"]:
            end = timezone.now()
        else:
            end = datetime.datetime.combine(
                data["start_date"],
                data["end_time"],
                tzinfo=timezone.get_current_timezone(),
            )
        complaint = Complaint(
            case=self.object,
            complainant_id=user,
            happening_now=data["happening_now"],
            start=start,
            end=end,
            rooms=data["rooms"],
            description=data["description"],
            effect=data["effect"],
        )
        complaint.save()
        return render(
            self.request,
            "cases/complaint_add_done.html",
            {"data": data, "case": self.object},
        )


def report_existing_qn(request):
    if not request.user.is_staff and not settings.NON_STAFF_ACCESS:
        return redirect("/")

    data = request.POST or None
    if "get" in request.POST:
        data = None
    form = forms.ExistingForm(data)
    if form.is_valid():
        flow = form.cleaned_data["existing"]
        if flow == "new":
            return redirect("case-add")
        else:  # existing
            return redirect("cases")
    return render(request, "cases/add/existing.html", {"form": form})


class ReportingWizard(NamedUrlSessionWizardView):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_staff and not settings.NON_STAFF_ACCESS:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get(self, *args, **kwargs):
        """Always reset if begin page visited."""
        step_url = kwargs.get("step", None)
        if step_url is None:
            self.storage.reset()
            # self.storage.current_step = self.steps.first
            return redirect(self.get_step_url(self.steps.current))
        return super().get(*args, **kwargs)

    def _deal_with_no_js_map_click(self):
        """If we have clicked the map or no-JS zoom buttons, deal with that
        first off to convert to it being as if we'd come to the map page anew
        with this data"""
        coords = {}
        x = y = None
        zoom = self.request.POST.get("where-map-zoom")
        point = self.request.POST.get("where-map-point")
        radius = self.request.POST.get("where-map-radius")
        for key in self.request.POST:
            m = re.match("tile_(\d+)\.(\d+)\.([xy])", key)
            if m:
                x, y, d = m.groups()
                coords[d] = int(self.request.POST[key])
        if x and y and "x" in coords and "y" in coords:
            lat, lon = map_utils.click_to_wgs84(
                int(zoom), int(x), coords["x"], int(y), coords["y"]
            )
            self.initial_dict = {
                "where-map": {
                    "point": f"POINT ({lon} {lat})",
                    "radius": radius,
                    "zoom": zoom,
                }
            }
            return True
        if "change-zoom" in self.request.POST:
            self.initial_dict = {
                "where-map": {
                    "point": point,
                    "radius": radius,
                    "zoom": self.request.POST["change-zoom"],
                }
            }
            return True
        return False

    def post(self, *args, **kwargs):
        if self._deal_with_no_js_map_click():
            return self.render()
        return super().post(*args, **kwargs)

    def get_template_names(self):
        """Template to use is stored on the form"""
        form = self.form_list[self.steps.current]
        return getattr(form, "template", "cases/add/index.html")

    def get_context_data(self, **kwargs):
        if self.steps.current == "summary":
            data = kwargs["data"] = self.get_all_cleaned_data()
            case = kwargs["case"] = Case(
                kind=data["kind"],
                kind_other=data["kind_other"],
                point=data.get("point"),
                radius=data.get("radius"),
                uprn=data.get("source_uprn"),
                where=data["where"],
                estate=data["estate"],
            )
            case.update_location_cache()

            if data.get("user"):
                user = User.objects.get(id=data["user"])
                kwargs["reporting_user"] = user
            else:  # Must have name
                address = data.get("address_manual") or data.get("address")
                user = User(uprn=data.get("address_uprn"), address=address)
                user.update_address()
                address = user.address_display
                email = data.get("email") or "No email"
                phone = data.get("phone") or "No phone"
                kwargs[
                    "reporting_user"
                ] = f"{data['first_name']} {data['last_name']}, {address}, {email}, {phone}"

        return super().get_context_data(**kwargs)

    def get_form_kwargs(self, step):
        if step == "where-postcode-results":
            data = self.storage.get_step_data("where-location") or {}
            return {"address_choices": data["postcode_results"]}
        elif step == "where-geocode-results":
            data = self.storage.get_step_data("where-location") or {}
            if data.get("geocode_results"):
                return {"geocode_choices": data["geocode_results"]}
        elif step == "best_time":
            return {"staff": self.request.user.is_active and self.request.user.is_staff}
        elif step == "about":
            return {"user": self.request.user.is_authenticated and self.request.user}
        elif step == "confirmation":
            data = self.storage.get_step_data("summary") or {}
            return {"token": data.get("token")}
        return super().get_form_kwargs(step)

    def get_form_initial(self, step):
        """The user pick form needs the search query passed to it"""
        if step == "user_pick":
            data = self.get_cleaned_data_for_step("user_search")
            if data:
                return {"search": data["search"]}
        elif step == "about" and self.request.user.is_authenticated:
            return {
                "first_name": self.request.user.first_name,
                "last_name": self.request.user.last_name,
                "email": self.request.user.email,
                "phone": self.request.user.phone,
            }
        elif step == "where-map":
            if "where-map" in self.initial_dict:  # no-JS map click
                return self.initial_dict["where-map"]
            data1 = self.storage.get_step_data("where-location") or {}
            data2 = self.get_cleaned_data_for_step("where-geocode-results") or {}
            initial = {
                "radius": 30,
                "zoom": 16,
            }
            if data1.get("geocode_result"):
                lon, lat = data1["geocode_result"][0].split(",")
                initial["point"] = Point(float(lon), float(lat))
            else:  # Must have data2.get("geocode_result")
                lon, lat = data2["geocode_result"].split(",")
                initial["point"] = Point(float(lon), float(lat))
            return initial
        else:
            return super().get_form_initial(step)

    def process_step(self, form):
        """If a form has given us some extra information to store, store it."""
        data = super().process_step(form)
        if hasattr(form, "to_store"):
            data = data.copy()
            data.update(form.to_store)
        if self.steps.current == "summary" and not self.request.user.is_authenticated:
            data = data.copy()
            token = str(random.randint(0, 999999)).zfill(6)
            data["token"] = token
            about_data = self.get_cleaned_data_for_step("about")
            if about_data["email"]:
                send_email(
                    about_data["email"],
                    "Confirm your noise case",
                    "cases/add/email_confirm",
                    {"token": token},
                )
            else:  # pragma: no cover # email or phone must both be present at present
                send_sms(
                    str(about_data["phone"]),
                    f"Your confirmation token is {token}",
                )

        return data

    form_list = [
        ("user_search", forms.RecurrencePersonSearchForm),
        ("user_pick", forms.PersonPickForm),
        ("about", forms.AboutYouForm),
        ("best_time", forms.BestTimeForm),
        ("postcode", forms.PostcodeForm),
        ("kind", forms.ReportingKindForm),
        ("where", forms.WhereForm),
        ("where-location", forms.WhereLocationForm),
        ("where-postcode-results", forms.WherePostcodeResultsForm),
        ("where-geocode-results", forms.WhereGeocodeResultsForm),
        ("where-map", forms.WhereMapForm),
        ("isitnow", forms.IsItHappeningNowForm),
        ("isnow", forms.HappeningNowForm),
        ("notnow", forms.NotHappeningNowForm),
        ("rooms", forms.RoomsAffectedForm),
        ("describe", forms.DescribeNoiseForm),
        ("effect", forms.EffectForm),
        ("summary", forms.SummaryForm),
        ("confirmation", forms.ConfirmationForm),
    ]

    condition_dict = {
        "user_search": show_user_form,
        "user_pick": show_user_form,
        "about": show_about_form,
        "postcode": show_about_form,
        "where-postcode-results": show_postcode_results_form,
        "where-geocode-results": show_geocode_results_form,
        "where-map": show_map_form,
        "isnow": show_happening_now_form,
        "notnow": show_not_happening_now_form,
        "confirmation": show_confirmation_step,
    }

    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        data = self.get_all_cleaned_data()

        # Save a new user if need be
        if data.get("user"):
            user = User.objects.get(pk=data["user"])
        elif self.request.user.is_authenticated:
            user = self.request.user
        else:
            try:
                user = User.objects.get(email=data["email"], email_verified=True)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(phone=data["phone"], phone_verified=True)
                except User.DoesNotExist:
                    user = User.objects.create_user(
                        email=data["email"],
                        phone=data["phone"],
                    )

        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        if not user.email_verified:
            user.email = data["email"]
        if not user.phone_verified:
            user.phone = data["phone"]
        user.uprn = data.get("address_uprn", "")
        address = data.get("address") or data.get("address_manual")
        if address:
            user.address = address
        user.best_time = data["best_time"]
        user.best_method = data["best_method"]
        user.save()

        case = Case(
            kind=data["kind"],
            kind_other=data["kind_other"],
            point=data.get("point"),
            radius=data.get("radius"),
            uprn=data.get("source_uprn", ""),
            where=data["where"],
            estate=data["estate"],
        )
        case.save()

        start = datetime.datetime.combine(
            data["start_date"],
            data["start_time"],
            tzinfo=timezone.get_current_timezone(),
        )
        if data["happening_now"]:
            end = timezone.now()
        else:
            end = datetime.datetime.combine(
                data["start_date"],
                data["end_time"],
                tzinfo=timezone.get_current_timezone(),
            )
        complaint = Complaint(
            case=case,
            complainant=user,
            happening_now=data["happening_now"],
            start=start,
            end=end,
            rooms=data["rooms"],
            description=data["description"],
            effect=data["effect"],
        )
        complaint.save()
        return render(
            self.request,
            "cases/add/done.html",
            {"data": data, "case": case},
        )
