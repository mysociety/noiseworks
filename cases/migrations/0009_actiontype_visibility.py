# Generated by Django 3.2.3 on 2021-10-06 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0008_auto_20211005_1422'),
    ]

    operations = [
        migrations.AddField(
            model_name='actiontype',
            name='visibility',
            field=models.CharField(choices=[('public', 'Public'), ('staff', 'Staff'), ('internal', 'Internal')], default='staff', max_length=10),
        ),
    ]
