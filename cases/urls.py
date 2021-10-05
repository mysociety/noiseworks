from django.urls import path
from . import views

urlpatterns = [
    path("", views.case_list, name="cases"),
    path("/<int:pk>", views.case, name="case-view"),
    path("/<int:pk>/complaint/<int:complaint>", views.complaint, name="complaint"),
    path("/<int:pk>/edit-kind", views.edit_kind, name="case-edit-kind"),
    path("/<int:pk>/reassign", views.reassign, name="case-reassign"),
    path("/<int:pk>/log", views.log_action, name="case-log-action"),
    path("/<int:pk>/merge", views.merge, name="case-merge"),
]
