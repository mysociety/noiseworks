# Generated by Django 3.2.15 on 2022-11-22 10:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_user_contact_warning'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'ordering': ('first_name', 'last_name'), 'permissions': [('edit_contact_warning', 'Can add, remove or edit a contact warning.')]},
        ),
    ]
