import datetime
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.gis.measure import D
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from formtools.wizard.views import NamedUrlSessionWizardView
from noiseworks.decorators import staff_member_required
from .filters import CaseFilter
from .models import Case, Complaint, Action, ActionType
from . import forms
from accounts.models import User


@login_required(redirect_field_name="nxt")
def case_list(request):
    if request.user.is_staff:
        return case_list_staff(request)
    else:
        return case_list_user(request)


@login_required
def case_list_user(request):
    cases = Case.objects.by_complainant(request.user)
    return render(
        request,
        "cases/case_list_user.html",
        {"cases": cases},
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
        },
    )


@login_required(redirect_field_name="nxt")
def case(request, pk):
    if request.user.is_staff:
        return case_staff(request, pk)
    else:
        return case_user(request, pk)


@login_required
def case_user(request, pk):
    qs = Case.objects.by_complainant(request.user)
    qs = qs.select_related("assigned")
    case = get_object_or_404(qs, pk=pk)
    return render(request, "cases/case_detail_user.html", context={"case": case})


@staff_member_required
def case_staff(request, pk):
    qs = Case.objects.select_related("assigned")
    case = get_object_or_404(qs, pk=pk)

    # redirect = case.merged_into
    # if redirect:
    #    return redirect(redirect)

    return render(request, "cases/case_detail_staff.html", context={"case": case})


@staff_member_required
def reassign(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = forms.ReassignForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
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
        return HttpResponseForbidden()
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
    return render(
        request,
        "cases/merged_thanks.html",
        {
            "case": case,
            "other": other,
        },
    )


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


class RecurrenceWizard(LoginRequiredMixin, NamedUrlSessionWizardView):
    template_name = "cases/complaint_add.html"
    context_object_name = "case"
    model = Case

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_staff:
            qs = Case.objects.all()
        else:
            qs = Case.objects.by_complainant(user)
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

    # Conditionals for form step display

    def show_happening_now_form(wizard):
        data = wizard.get_cleaned_data_for_step("isitnow") or {}
        return data.get("happening_now")

    def show_not_happening_now_form(wizard):
        data = wizard.get_cleaned_data_for_step("isitnow") or {}
        return not data.get("happening_now")

    def show_user_form(wizard):
        user = wizard.request.user
        return user.is_active and user.is_staff

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
        picker = form_dict["user_pick"]
        user = picker.save()

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
