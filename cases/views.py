from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from .models import Case


@staff_member_required
def case_list(request):
    qs = Case.objects.all()
    return render(
        request,
        "cases/case_list_staff.html",
        {
            "object_list": qs,
        },
    )


@staff_member_required
def case(request, **kwargs):
    case = get_object_or_404(Case.objects.select_related("assigned"), pk=kwargs["pk"])
    return render(request, "cases/case_detail_staff.html", context={"case": case})
