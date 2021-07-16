from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .filters import CaseFilter
from .models import Case, Complaint, Action
from .forms import ReassignForm, ActionForm


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
    merge_map = Action.objects.get_merged_cases(f.qs)
    actions_by_case = Action.objects.get_reversed(merge_map)

    # Set the actions for each result to the right ones
    for case in f.qs:
        case.actions_reversed = actions_by_case.get(case.id, [])

    return render(
        request,
        "cases/case_list_staff.html",
        {
            "filter": f,
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
    #    return HttpResponseRedirect(redirect.get_absolute_url())

    return render(request, "cases/case_detail_staff.html", context={"case": case})


@staff_member_required
def reassign(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = ReassignForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save(case=case, user=request.user)
        return HttpResponseRedirect(case.get_absolute_url())
    return render(
        request,
        "cases/reassign.html",
        {
            "case": case,
            "form": form,
        },
    )


@staff_member_required
def log_action(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = ActionForm(request.POST or None)
    if form.is_valid():
        form.save(case=case, user=request.user)
        return HttpResponseRedirect(case.get_absolute_url())
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
    return HttpResponseRedirect(case.get_absolute_url())


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

    return render(
        request,
        "cases/merged_start.html",
        {
            "case": case,
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
        return HttpResponseRedirect(case.get_absolute_url())
    return render(
        request,
        "cases/complaint_detail.html",
        context={"case": case, "complaint": complaint},
    )
