from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .filters import CaseFilter
from .models import Case, Action
from .forms import ReassignForm, ActionForm


@staff_member_required
def case_list(request):
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


@staff_member_required
def case(request, **kwargs):
    case = get_object_or_404(Case.objects.select_related("assigned"), pk=kwargs["pk"])

    # redirect = case.merged_into
    # if redirect:
    #    return HttpResponseRedirect(redirect.get_absolute_url())

    return render(request, "cases/case_detail_staff.html", context={"case": case})


@staff_member_required
def reassign(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = ReassignForm(request.POST or None, instance=case)
    if form.is_valid():
        form.save()
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
        form.save(case=case)
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
        if "merging_case" in request.session:
            del request.session["merging_case"]
            messages.success(request, "We have forgotten your current merging.")
        return HttpResponseRedirect(case.get_absolute_url())

    if request.POST.get("dupe") and request.session.get("merging_case"):
        other_id = request.session["merging_case"]["id"]
        other = Case.objects.get(pk=other_id)
        Action.objects.create(
            case=case,
            case_old=other,
        )
        del request.session["merging_case"]
        return render(
            request,
            "cases/merged_thanks.html",
            {
                "case": case,
                "other": other,
            },
        )

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
