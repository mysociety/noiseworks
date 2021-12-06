from django.urls import path
from django.views.generic import TemplateView
from . import views

reporting_wizard = views.ReportingWizard.as_view(url_name="case-add-step")
recurrence_wizard = views.RecurrenceWizard.as_view(url_name="complaint-add-step")


urlpatterns = [
    path("", views.case_list, name="cases"),
    path("/<int:pk>", views.case, name="case-view"),
    path(
        "/add",
        TemplateView.as_view(template_name="cases/add/intro.html"),
        name="case-add-intro",
    ),
    path("/add/existing", views.report_existing_qn, name="case-report-existing-qn"),
    path("/add/begin", reporting_wizard, name="case-add"),
    path("/add/<step>", reporting_wizard, name="case-add-step"),
    path("/<int:pk>/complaint/add", recurrence_wizard, name="complaint-add"),
    path(
        "/<int:pk>/complaint/add/<step>", recurrence_wizard, name="complaint-add-step"
    ),
    path("/<int:pk>/complaint/<int:complaint>", views.complaint, name="complaint"),
    path("/<int:pk>/edit-kind", views.edit_kind, name="case-edit-kind"),
    path("/<int:pk>/edit-location", views.edit_location, name="case-edit-location"),
    path(
        "/<int:pk>/search-perpetrator",
        views.search_perpetrator,
        name="case-search-perpetrator",
    ),
    path(
        "/<int:pk>/add-perpetrator", views.add_perpetrator, name="case-add-perpetrator"
    ),
    path(
        "/<int:pk>/remove-perpetrator/<int:perpetrator>",
        views.remove_perpetrator,
        name="case-remove-perpetrator",
    ),
    path("/<int:pk>/reassign", views.reassign, name="case-reassign"),
    path("/<int:pk>/followers", views.followers, name="case-followers"),
    path("/<int:pk>/follower-state", views.follower_state, name="case-follower-state"),
    path("/<int:pk>/log", views.log_action, name="case-log-action"),
    path("/<int:pk>/merge", views.merge, name="case-merge"),
]
