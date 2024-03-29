# Generated by Django 3.2.15 on 2022-09-20 15:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0027_populate_action_time_from_created_time'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseSettingsSingleton',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('_singleton', models.BooleanField(default=True, editable=False, unique=True)),
                ('logged_action_editing_window', models.DurationField()),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_casesettingssingleton_set', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_casesettingssingleton_set', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Case settings',
                'verbose_name_plural': 'Case settings',
            },
        ),
    ]
