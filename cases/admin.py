from django.contrib import admin
from django.contrib.gis import forms
from django.contrib.gis.db import models

from .models import Action, ActionType, Case, Complaint

admin.site.register(Complaint)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    formfield_overrides = {models.PointField: {"widget": forms.OSMWidget}}


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("type", "case", "time", "created")

    def has_change_permission(self, request, obj):
        return obj and request.user == obj.created_by


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "common")
    list_editable = ("common",)
