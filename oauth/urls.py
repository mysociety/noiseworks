from django.urls import path
from . import views

app_name = "oauth"
urlpatterns = [
    path("authenticate", views.authenticate, name="authenticate"),
    path("verify", views.verify, name="verify"),
]
