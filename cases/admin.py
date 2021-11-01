from django.contrib import admin
from django.contrib.gis.db import models
from django.contrib.gis import forms
from .models import Case, Complaint, Action, ActionType


admin.site.register(Complaint)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    formfield_overrides = {models.PointField: {"widget": forms.OSMWidget}}


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("type", "case", "created")


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "common")
    list_editable = ("common",)
