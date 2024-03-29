from django.contrib import admin
from django.contrib.gis import forms
from django.contrib.gis.db import models

from .models import (
    Action,
    ActionFile,
    ActionType,
    Case,
    CaseSettingsSingleton,
    Complaint,
)

admin.site.register(Complaint)


@admin.register(CaseSettingsSingleton)
class CaseSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    formfield_overrides = {models.PointField: {"widget": forms.OSMWidget}}


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("type", "case", "time", "created")


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "common")
    list_editable = ("common",)


@admin.register(ActionFile)
class ActionFileAdmin(admin.ModelAdmin):
    pass
