# Generated by Django 3.2.3 on 2021-11-03 14:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0012_auto_20211101_1346'),
    ]

    operations = [
        migrations.RenameField(
            model_name='case',
            old_name='uprn_cache',
            new_name='location_cache',
        ),
    ]