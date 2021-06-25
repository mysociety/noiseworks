from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .filters import CaseFilter
from .models import Case, Action
from .forms import ReassignForm, ActionForm


@staff_member_required
def case_list(request):
    qs = Case.objects.prefetch_related(
        Prefetch(
            "actions",
            queryset=Action.objects.select_related("created_by").order_by("-created"),
            to_attr="_actions_reversed",
        ),
    ).select_related("assigned")
    f = CaseFilter(request.GET, queryset=qs, request=request)
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
