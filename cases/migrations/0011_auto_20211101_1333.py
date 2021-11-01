from django.db import migrations

migrate_forwards = "UPDATE cases_case SET point = ST_Transform(ST_SetSRID(ST_Point(longitude, latitude), 4326), 27700)"
migrate_backwards = "UPDATE cases_case SET longitude = ST_X(ST_Transform(point, 4326)), latitude = ST_Y(ST_Transform(point, 4326))"


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0010_case_point'),
    ]

    operations = [
        migrations.RunSQL(migrate_forwards, migrate_backwards),
    ]
