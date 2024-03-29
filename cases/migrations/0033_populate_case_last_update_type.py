# Generated by Django 3.2.15 on 2022-09-29 13:28
# Empty migration filled in manually.

from django.db import migrations
from django.db.models import Case, F, Max, OuterRef, Q, Subquery, Value, When

ACTION_TYPE = "AC"
COMPLAINT_TYPE = "CO"
NONE_TYPE = ""


def update_cases(cases):
    # Can't use joined field references in an update so doing the working
    # out in the subquery.
    cases.update(
        last_update_type=Subquery(
            cases.filter(id=OuterRef("id"))
            .annotate(
                last_complaint_time=Max("complaints__created"),
                last_action_time=Max("actions__time"),
            )
            .annotate(
                _last_update_type=Case(
                    When(
                        Q(
                            last_complaint_time__isnull=False,
                            last_action_time__isnull=True,
                        )
                        | Q(
                            last_complaint_time__gte=F("last_action_time"),
                        ),
                        then=Value(COMPLAINT_TYPE),
                    ),
                    When(
                        Q(
                            last_complaint_time__isnull=True,
                            last_action_time__isnull=False,
                        )
                        | Q(
                            last_action_time__gt=F("last_complaint_time"),
                        ),
                        then=Value(ACTION_TYPE),
                    ),
                    default=Value(NONE_TYPE),
                )
            )
            .values("_last_update_type")[:1]
        )
    )


def forwards_func(apps, schema_editor):
    CaseModel = apps.get_model("cases", "Case")
    update_cases(CaseModel.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0032_case_last_update_type"),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_code=migrations.RunPython.noop)
    ]
