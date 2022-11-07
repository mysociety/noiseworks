# Generated by Django 3.2.15 on 2022-10-18 17:57
# Empty migration filled in manually.

from django.db import migrations


def forwards_func(apps, schema_editor):
    Action = apps.get_model("cases", "Action")
    Action.objects.filter(case_old__isnull=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0040_alter_case_last_update_type"),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_code=migrations.RunPython.noop),
    ]