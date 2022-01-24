from django.contrib import admin


class AdminSite(admin.AdminSite):
    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser
