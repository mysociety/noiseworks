# Generated by Django 3.2.15 on 2022-10-18 18:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0041_delete_all_merge_actions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='case_old',
        ),
    ]
