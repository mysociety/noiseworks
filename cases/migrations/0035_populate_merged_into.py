# Generated by Django 3.2.15 on 2022-10-17 13:49
# Empty migration filled in manually.

from django.db import migrations
from django.db.models import Prefetch


def forwards_func(apps, schema_editor):
    Action = apps.get_model("cases", "Action")
    Case = apps.get_model("cases", "Case")
    cases = Case.objects.prefetch_related(
        Prefetch(
            "actions",
            queryset=(
                Action.objects.filter(case_old__isnull=False)
                .filter(case__isnull=False)
                .order_by("-time")
            ),
        )
    )
    # Set 'merged_into' based on the most recent
    # merging action on the case.
    for case in cases:
        for action in case.actions.all():
            case.merged_into_id = action.case_id
            case.save()
            continue


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0034_auto_20221017_1446"),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_code=migrations.RunPython.noop),
    ]