from django.urls import path
from . import views

urlpatterns = [
    path("", views.case_list, name="cases"),
    path("/<int:pk>", views.case, name="case-view"),
    path("/<int:pk>/reassign", views.reassign, name="case-reassign"),
]
