# Generated by Django 3.2.15 on 2022-09-20 15:10
# Empty migration filled in manually.

from datetime import timedelta
from django.db import migrations

def forwards_func(apps, schema_editor):
    CaseSettingsSingleton = apps.get_model('cases', 'CaseSettingsSingleton')
    cs = CaseSettingsSingleton(logged_action_editing_window=timedelta(days=1))
    cs.save()

def reverse_func(apps, schema_editor):
    cs = CaseSettingsSingleton.objects.all()[0]
    cs.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0028_casesettingssingleton'),
    ]

    operations = [
            migrations.RunPython(forwards_func, reverse_code=reverse_func),
    ]

