from django.contrib import admin
from .models import Case, Complaint, Action, ActionType


admin.site.register(Case)
admin.site.register(Complaint)


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("type", "case", "created")


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "common")
    list_editable = ("common",)
