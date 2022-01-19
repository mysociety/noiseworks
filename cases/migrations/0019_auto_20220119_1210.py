# Generated by Django 3.2.11 on 2022-01-19 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0018_case_followers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='kind',
            field=models.CharField(choices=[('animal', 'Animal noise'), ('buskers', 'Buskers'), ('car', 'Car alarm'), ('construction', 'Construction site noise'), ('deliveries', 'Deliveries'), ('diy', 'DIY'), ('alarm', 'House / intruder alarm'), ('music-pub', 'Music from pub'), ('music-club', 'Music from club/bar'), ('music-other', 'Music - other'), ('roadworks', 'Noise from roadworks'), ('road', 'Noise on the road'), ('plant-machinery', 'Plant noise - machinery'), ('plant-street', 'Plant noise - machinery on street'), ('shouting', 'Shouting'), ('tv', 'TV'), ('other', 'Other')], max_length=15, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='historicalcase',
            name='kind',
            field=models.CharField(choices=[('animal', 'Animal noise'), ('buskers', 'Buskers'), ('car', 'Car alarm'), ('construction', 'Construction site noise'), ('deliveries', 'Deliveries'), ('diy', 'DIY'), ('alarm', 'House / intruder alarm'), ('music-pub', 'Music from pub'), ('music-club', 'Music from club/bar'), ('music-other', 'Music - other'), ('roadworks', 'Noise from roadworks'), ('road', 'Noise on the road'), ('plant-machinery', 'Plant noise - machinery'), ('plant-street', 'Plant noise - machinery on street'), ('shouting', 'Shouting'), ('tv', 'TV'), ('other', 'Other')], max_length=15, verbose_name='Type'),
        ),
    ]
