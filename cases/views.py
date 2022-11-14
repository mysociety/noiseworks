import datetime
import random
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http.response import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from formtools.wizard.views import NamedUrlSessionWizardView
from humanize import naturalsize


from accounts.models import User
from noiseworks import cobrand
from noiseworks.decorators import staff_member_required
from noiseworks.message import send_email, send_sms

from . import forms, map_utils
from .filters import CaseFilter
from .models import Action, ActionFile, ActionType, Case, Complaint, Notification


def home(request):
    if request.user.is_staff:
        return redirect("cases")
    elif request.user.is_authenticated:
        if "hackney.gov.uk" in request.user.email:
            return render(request, "home_unapproved.html")
        else:
            return redirect("cases")
    else:
        return redirect("case-add-intro")


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
    qs = Case.objects.all()
    f = CaseFilter(request.GET, queryset=qs, request=request)

    paginator = Paginator(f.qs, 20)
    page_number = request.GET.get("page")
    qs = paginator.get_page(page_number)

    Case.objects.prefetch_timeline(qs)

    template = "cases/case_list_staff.html"
    if request.GET.get("ajax"):
        template = "cases/_case_list_staff_list.html"
    return render(
        request,
        template,
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

    is_follower = case.followers.filter(pk=request.user.id)
    timeline = case.timeline_staff_with_operation_flags(request.user)
    priority_change_form = forms.PriorityForm(initial={"priority": not case.priority})

    return render(
        request,
        "cases/case_detail_staff.html",
        context={
            "case": case,
            "is_follower": is_follower,
            "timeline": timeline,
            "priority_change_form": priority_change_form,
        },
    )


@permission_required("cases.assign")
def reassign(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.ReassignForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
        user = form.cleaned_data["assigned"]
        case.followers.add(user)
        case.notify_followers(f"Assigned {user}.", triggered_by=request.user)
        if user.id != request.user.id:
            url = request.build_absolute_uri(case.get_absolute_url())
            send_email(
                user.email,
                "You have been assigned",
                "cases/email/assigned",
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


@permission_required("cases.follow")
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
        if not user.has_perm("cases.follow"):
            raise PermissionDenied
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
        case.notify_followers(
            f"Set kind to {form.cleaned_data['kind']}.", triggered_by=request.user
        )
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
        case.notify_followers("Changed location.", triggered_by=request.user)
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
def edit_review_date(request, pk):
    case = get_object_or_404(Case, pk=pk)
    has_review_date = case.review_date != None
    form = forms.ReviewDateForm(
        request.POST or None,
        instance=case,
        initial={"has_review_date": has_review_date},
    )
    if form.is_valid():
        form.save()
        description = ""
        if form.cleaned_data["has_review_date"]:
            description = f"Set review date to {form.cleaned_data['review_date']}."
        else:
            description = "Set no review date."
        case.notify_followers(description, triggered_by=request.user)
        return redirect(case)
    return render(
        request,
        "cases/edit-review-date.html",
        {
            "case": case,
            "form": form,
        },
    )


@permission_required("cases.edit_perpetrators")
def remove_perpetrator(request, pk, perpetrator):
    case = get_object_or_404(Case, pk=pk)
    user = get_object_or_404(User, pk=perpetrator)
    case.perpetrators.remove(user)
    Action.objects.create(
        case=case, type=ActionType.edit_case, notes="Removed perpetrator"
    )
    case.notify_followers("Removed perpetrator.", triggered_by=request.user)
    return redirect(case)


@staff_member_required
def log_action(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.LogActionForm(request.POST or None, request.FILES or None, case=case)
    if form.is_valid():
        type_ = form.cleaned_data["type"]
        description = ""
        if type_ == ActionType.case_closed:
            case.closed = True
            description = "Closed case."
        elif type_ == ActionType.case_reopened:
            case.closed = False
            description = "Opened case."
        else:
            description = f"Added '{type_}'."
        form.save()
        case.notify_followers(description, triggered_by=request.user)
        for f in request.FILES.getlist("files"):
            ActionFile.objects.create(
                action=form.instance,
                file=f,
                original_name=f.name,
            )
        return redirect(case)
    bytes_remaining = case.file_storage_remaining_bytes
    return render(
        request,
        "cases/action_form.html",
        {
            "case": case,
            "form": form,
            "close_type_id": ActionType.case_closed.id,
            "form_title": "Log an action",
            "can_upload_files": bytes_remaining > 0,
            "remaining_file_storage_bytes": bytes_remaining,
            "remaining_file_storage_human_readable": naturalsize(bytes_remaining),
        },
    )


@staff_member_required
def edit_logged_action(request, case_pk, action_pk):
    case = get_object_or_404(Case, pk=case_pk)
    action = get_object_or_404(Action, pk=action_pk)

    if not action.can_edit(request.user):
        raise PermissionDenied

    form = forms.EditActionForm(
        request.POST or None,
        instance=action,
    )
    if form.is_valid():
        form.save()
        return redirect(case)
    return render(
        request,
        "cases/action_form.html",
        {
            "case": case,
            "form": form,
            "form_title": "Edit a logged action",
        },
    )


@staff_member_required
def action_file_delete(request, case_pk, action_pk, file_pk):
    case = get_object_or_404(Case, pk=case_pk)
    get_object_or_404(Action, pk=action_pk)
    _file = get_object_or_404(ActionFile, pk=file_pk)

    if not _file.can_delete(request.user):
        raise PermissionDenied

    if request.method == "POST":
        _file.delete()
        return redirect(case)

    return render(
        request,
        "cases/delete_action_file_form.html",
        {
            "case": case,
            "file": _file,
        },
    )


@staff_member_required
def action_file(request, case_pk, action_pk, file_pk):
    get_object_or_404(Case, pk=case_pk)
    get_object_or_404(Action, pk=action_pk)
    action_file = get_object_or_404(ActionFile, pk=file_pk).file
    return FileResponse(action_file)


@permission_required("cases.merge")
def unmerge(request, pk):
    case = get_object_or_404(Case, pk=pk)
    other = case.merged_into
    case.unmerge()
    case.save()
    notification = f"Unmerged case #{case.id} from case #{other.id}."
    other.notify_followers(notification, triggered_by=request.user)
    case.notify_followers(notification, triggered_by=request.user)
    return redirect(case)


@permission_required("cases.merge")
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
    other.save()
    del request.session["merging_case"]
    messages.success(request, f"Case #{other_id} has been merged into this case.")
    notification = f"Merged case #{other.id} into case #{case.id}."
    other.notify_followers(notification, triggered_by=request.user)
    case.notify_followers(notification, triggered_by=request.user)
    return redirect(case)


def merge_start(request, case):
    request.session["merging_case"] = {
        "id": case.id,
        "name": f"{case.kind_display} at {case.location_display}",
    }

    qs = Case.objects.unmerged()
    cases_same_uprn = []
    cases_nearby = []
    if case.uprn:
        cases_same_uprn = qs.filter(uprn=case.uprn).exclude(id=case.id)
    if case.point:
        cases_nearby = qs.filter(point__dwithin=(case.point, D(m=500))).exclude(
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


@staff_member_required
def priority(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.PriorityForm(request.POST or None, instance=case)
    if form.is_valid():
        message = (
            "Marked as priority."
            if form.cleaned_data["priority"]
            else "Marked as not priority."
        )
        case.notify_followers(message, triggered_by=request.user)
        form.save()
    return redirect(case)


@login_required
def complaint(request, pk, complaint):
    if not request.user.is_staff and not settings.NON_STAFF_ACCESS:
        return redirect("/")

    case = get_object_or_404(Case, pk=pk)
    complaint = get_object_or_404(
        Complaint.objects.select_related("case"), pk=complaint
    )
    merge_map = case.merge_map
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


def show_user_address_form(wizard):
    data = wizard.get_cleaned_data_for_step("user_pick") or {}
    return show_user_form(wizard) and data.get("postcode")


def show_about_form(wizard):
    return not show_user_form(wizard)


def show_internal_flags_form(wizard):
    user = wizard.request.user
    return user.is_active and user.is_staff


def show_confirmation_step(wizard):
    user = wizard.request.user
    return not user.is_authenticated


def compile_dates(data):
    start = datetime.datetime.combine(data["start_date"], data["start_time"])
    start = timezone.make_aware(start)

    if data["happening_now"]:
        end = timezone.now()
    else:
        end = datetime.datetime.combine(data["start_date"], data["end_time"])
        end = timezone.make_aware(end)
        if end < start:
            end += datetime.timedelta(days=1)
    return start, end


class CaseWizard(NamedUrlSessionWizardView):
    def get(self, *args, **kwargs):
        """Always reset if begin page visited."""
        step_url = kwargs.get("step", None)
        if step_url is None:
            self.storage.reset()
            # self.storage.current_step = self.steps.first
            return redirect(self.get_step_url(self.steps.current))

        data = self.storage.get_step_data(self.summary_check_page)
        if step_url == "summary" and not data:
            return redirect(self.get_step_url(self.steps.first))
        data = self.storage.get_step_data("postcode")
        if step_url == "address" and not data:
            return redirect(self.get_step_url(self.steps.first))

        return super().get(*args, **kwargs)

    def person_save(self, data):
        if data["user"]:
            return data["user"]
        user = User.objects.create_user(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone=data["phone"],
            address=data.get("address_manual", ""),
            uprn=data.get("address_uprn", ""),
        )
        return user.id

    def process_step(self, form):
        """If a form has given us some extra information to store, store it."""
        data = super().process_step(form)
        if hasattr(form, "to_store"):
            data = data.copy()
            data.update(form.to_store)
        return data


class PerCaseWizard(CaseWizard):
    context_object_name = "case"
    model = Case

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
        return super().get_context_data(**kwargs)


class RecurrenceWizard(LoginRequiredMixin, PerCaseWizard):
    template_name = "cases/complaint_add.html"
    summary_check_page = "isitnow"

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

    def get_context_data(self, **kwargs):
        data = kwargs["data"] = self.get_all_cleaned_data()

        if data.get("user"):
            user = User.objects.get(id=data["user"])
            kwargs["reporting_user"] = user
        elif data.get("last_name"):
            user = User(
                uprn=data.get("address_uprn"), address=data.get("address_manual")
            )
            user.update_address_and_estate()
            address = user.address_display
            kwargs[
                "reporting_user"
            ] = f"{data['first_name']} {data['last_name']}, {address}, {data['email']}, {data['phone']}"

        if self.steps.current == "summary":
            start, end = compile_dates(data)
            kwargs["end_time"] = end

        return super().get_context_data(**kwargs)

    def get_form_kwargs(self, step):
        if step == "user_address":
            data = self.storage.get_step_data("user_pick") or {}
            return {"address_choices": data["postcode_results"]}
        return super().get_form_kwargs(step)

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
        ("user_address", forms.PersonAddressForm),
        ("summary", forms.SummaryForm),
    ]

    condition_dict = {
        "isnow": show_happening_now_form,
        "notnow": show_not_happening_now_form,
        "user_search": show_user_form,
        "user_pick": show_user_form,
        "user_address": show_user_address_form,
    }

    def done(self, form_list, form_dict, **kwargs):
        data = self.get_all_cleaned_data()

        # Save a new user if need be
        if "user_pick" in form_dict:
            user = self.person_save(data)
        else:
            user = self.request.user.id

        start, end = compile_dates(data)
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
        send_emails(self.request, complaint, "reoccurrence")
        self.object.notify_followers(
            "Recurrence added.", triggered_by=self.request.user
        )
        # Reopen a case if it was closed - do this after email so email can know if it was closed
        if self.object.closed:
            self.object.closed = False
            self.object.save()
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


class ReportingWizard(CaseWizard):
    summary_check_page = "kind"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_staff and not settings.NON_STAFF_ACCESS:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

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
            m = re.match(r"tile_(\d+)\.(\d+)\.([xy])", key)
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
            )
            case.update_location_cache()

            start, end = compile_dates(data)
            kwargs["end_time"] = end

            if data.get("user"):
                user = User.objects.get(id=data["user"])
                kwargs["reporting_user"] = user
            else:  # Must have name
                user = User(
                    uprn=data.get("address_uprn"), address=data.get("address_manual")
                )
                user.update_address_and_estate()
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
        elif step == "address":
            data = self.storage.get_step_data("postcode") or {}
            return {"address_choices": data["postcode_results"]}
        elif step == "user_address":
            data = self.storage.get_step_data("user_pick") or {}
            return {"address_choices": data["postcode_results"]}
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
        elif step == "best_time" and self.request.user.is_authenticated:
            return {
                "best_time": self.request.user.best_time,
                "best_method": self.request.user.best_method,
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
        data = super().process_step(form)
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
        ("user_address", forms.PersonAddressForm),
        ("about", forms.AboutYouForm),
        ("best_time", forms.BestTimeForm),
        ("postcode", forms.PostcodeForm),
        ("address", forms.AddressForm),
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
        ("internal-flags", forms.InternalFlagsForm),
        ("summary", forms.SummaryForm),
        ("confirmation", forms.ConfirmationForm),
    ]

    condition_dict = {
        "user_search": show_user_form,
        "user_pick": show_user_form,
        "user_address": show_user_address_form,
        "about": show_about_form,
        "postcode": show_about_form,
        "address": show_about_form,
        "where-postcode-results": show_postcode_results_form,
        "where-geocode-results": show_geocode_results_form,
        "where-map": show_map_form,
        "isnow": show_happening_now_form,
        "notnow": show_not_happening_now_form,
        "internal-flags": show_internal_flags_form,
        "confirmation": show_confirmation_step,
    }

    def create_data(self, form_dict, data):
        # Save a new user if need be
        if "user_pick" in form_dict:
            user = self.person_save(data)
            user = User.objects.get(id=user)
        else:
            # Make sure these emails always create new unverified users.
            staff_only = settings.COBRAND_SETTINGS["staff_only_domains_re"]
            if staff_only and re.search(staff_only, data["email"]):
                user = User.objects.create_user()
            elif self.request.user.is_authenticated:
                user = self.request.user
            else:
                user = User.objects.check_existing(data["email"])
                if not user:
                    user = User.objects.create_user(
                        email=data["email"],
                    )

            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            if not user.email_verified:
                user.email = data["email"]
            if not user.phone_verified:
                user.phone = data["phone"]
            user.uprn = data.get("address_uprn", "")
            user.address = data.get("address_manual")

        user.best_time = data["best_time"]
        user.best_method = data["best_method"]
        user.save()

        if not self.request.user.is_authenticated:
            login(
                self.request, user, backend="django.contrib.auth.backends.ModelBackend"
            )

        # Include created_by/modified_by below in case only
        # just logged in above, so middleware won't catch it
        case = Case(
            created_by=self.request.user,
            modified_by=self.request.user,
            kind=data["kind"],
            kind_other=data["kind_other"],
            point=data.get("point"),
            radius=data.get("radius"),
            uprn=data.get("source_uprn", ""),
            where=data["where"],
            priority=data.get("priority", False),
        )
        if data.get("has_review_date", False):
            case.review_date = data.get("review_date", None)
        case.save()

        start, end = compile_dates(data)
        complaint = Complaint(
            created_by=self.request.user,
            modified_by=self.request.user,
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
        return complaint

    def done(self, form_list, form_dict, **kwargs):
        data = self.get_all_cleaned_data()

        with transaction.atomic():
            complaint = self.create_data(form_dict, data)
        send_emails(self.request, complaint, "report")
        return render(
            self.request,
            "cases/add/done.html",
            {"data": data, "case": complaint.case},
        )


@method_decorator(permission_required("cases.edit_perpetrators"), name="dispatch")
class PerpetratorWizard(LoginRequiredMixin, PerCaseWizard):
    template_name = "cases/complaint_add.html"
    summary_check_page = "user_search"

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(Case, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, step):
        if step == "user_address":
            data = self.storage.get_step_data("user_pick") or {}
            return {"address_choices": data["postcode_results"]}
        return super().get_form_kwargs(step)

    def get_form_initial(self, step):
        """The user pick form needs the search query passed to it"""
        if step == "user_pick":
            data = self.get_cleaned_data_for_step("user_search")
            if data:
                return {"search": data["search"]}
        return super().get_form_initial(step)

    form_list = [
        ("user_search", forms.PerpetratorSearchForm),
        ("user_pick", forms.PerpetratorPickForm),
        ("user_address", forms.PerpetratorAddressForm),
    ]

    condition_dict = {
        "user_address": show_user_address_form,
    }

    def done(self, form_list, form_dict, **kwargs):
        data = self.get_all_cleaned_data()
        user = self.person_save(data)
        self.object.perpetrators.add(user)
        typ, _ = ActionType.objects.get_or_create(
            name="Edit case", defaults={"visibility": "internal"}
        )
        Action.objects.create(case=self.object, type=typ, notes="Added perpetrator")
        self.object.notify_followers(
            "Added perpetrator.", triggered_by=self.request.user
        )
        return redirect(self.object)


def send_emails(request, complaint, template):
    case = complaint.case
    subject = f"Noise {template}: {case.location_display}"
    staff_dest = cobrand.email.case_destination(case)
    url = request.build_absolute_uri(case.get_absolute_url())
    complainant = complaint.complainant
    send_email(
        staff_dest,
        subject,
        f"cases/email/submit_{template}",
        {"complaint": complaint, "case": case, "complainant": complainant, "url": url},
    )
    if complainant.email:
        params = {"complaint": complaint, "url": url}
        if template == "report":
            params["case"] = case
        send_email(complainant.email, subject, f"cases/email/logged_{template}", params)


@staff_member_required
def delete_notifications(request):
    notification_ids = request.POST.getlist("notification_ids")
    Notification.objects.filter(
        id__in=notification_ids, recipient=request.user
    ).delete()
    return redirect("notifications")


@staff_member_required
def mark_notifications_as_read(request):
    notification_ids = request.POST.getlist("notification_ids")
    Notification.objects.filter(
        id__in=notification_ids, recipient=request.user, read=False
    ).update(read=True)
    return redirect("notifications")


@staff_member_required
def consume_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    if notification.recipient != request.user:
        raise PermissionDenied
    if not notification.read:
        notification.read = True
        notification.save()
    return redirect(notification.case)


@staff_member_required
def notifications_list(request):
    notifications = request.user.notifications.order_by("read", "-time").all()
    return render(
        request,
        "cases/notifications/notification_list.html",
        {"notifications": notifications},
    )
