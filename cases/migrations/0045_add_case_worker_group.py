# Generated by Django 3.2.15 on 2022-11-07 10:46
# Empty migration filled in manually.

from django.db import migrations
from django.contrib.auth.management import create_permissions


case_worker_perm_codenames = [
    "edit_perpetrators",
    "follow",
    "get_assigned",
    "assign",
    "change_priority",
    "change_review_date",
    "merge",
]


def forwards_func(apps, schema_editor):
    # Custom permissions created in a previous migration won't
    # be gettable in subsequent migrations in the same migrate call.
    # This is because the permissions aren't actually created until the
    # 'post_migrate' signal.
    # To workaround this we manually create the permissions here instead.
    # See: https://sleepy.yaks.industries/posts/set-permissions-django-migrations/
    cases_config = apps.get_app_config("cases")
    cases_config.models_module = True
    create_permissions(cases_config, verbosity=0)

    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Case = apps.get_model("cases", "Case")

    content_type = ContentType.objects.get_for_model(Case)
    case_worker_perms = [
        Permission.objects.get(codename=c, content_type=content_type)
        for c in case_worker_perm_codenames
    ]

    case_workers, _ = Group.objects.get_or_create(name="case_workers")
    case_workers.permissions.set(case_worker_perms)


def backwards_func(apps, schema_editor):
    Group.objects.filter(name="case_workers").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "__latest__"),
        ("cases", "0044_alter_case_options"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
