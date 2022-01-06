from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import include, path
import debug_toolbar
from cases.views import home

urlpatterns = [
    path("", home),
    path("cases", include("cases.urls")),
    path("oauth/", include("oauth.urls")),
    path("a", include("accounts.urls")),
    path("admin/", admin.site.urls),
    path("__debug__/", include(debug_toolbar.urls)),
]
