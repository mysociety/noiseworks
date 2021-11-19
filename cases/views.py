from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.gis.measure import D
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
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
        form = forms.PersonPickForm(initial={"search": form.cleaned_data["search"]})
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
    form = forms.PersonPickForm(request.POST)
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
