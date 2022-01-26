from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("", views.show_form, name="token-signin-form"),
    path("/code", views.code, name="code_form"),
    path("/list", views.list, name="list"),
    path("/sign-out", views.signout, name="sign-out"),
    path("/add", views.add, name="add"),
    path("/<int:user_id>/edit", views.edit, name="edit"),
    path("/<str:token>", views.token_url, name="token"),
]
