from django.contrib.admin.apps import AdminConfig


class NWAdminConfig(AdminConfig):
    default_site = "noiseworks.admin.AdminSite"
