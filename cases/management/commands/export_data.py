import csv
import logging
from pathlib import Path
import boto3
from smart_open import open
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from cases.models import Case, Complaint, Action, HistoricalCase
from accounts.models import User

Case_perpetrators = Case.perpetrators.through

s3_settings = settings.COBRAND_SETTINGS["data_export"]
session = boto3.Session(
    aws_access_key_id=s3_settings["ACCESS_KEY_ID"],
    aws_secret_access_key=s3_settings["SECRET_ACCESS_KEY"],
    region_name=s3_settings["REGION"],
)
client = session.client("s3")


class Command(BaseCommand):
    help = "Export the data as CSV files to an S3 bucket (locally for now)"

    fields = {
        Case: ["id", "created", "created_by_id", "kind", "kind_other", "uprn", "easting", "northing", "radius", "location_cache", "ward", "where", "estate", "assigned_id"],
        Complaint: ["id", "case_id", "created", "created_by_id", "complainant_id", "happening_now", "start", "end", "rooms", "description", "effect"],
        Action: ["id", "created", "created_by_id", "case_id", "type", "notes", "case_old_id"],
        User: ["id", "first_name", "last_name", "is_staff", "is_active", "email", "email_verified", "phone", "phone_verified", "address", "best_time", "best_method"],
        HistoricalCase: ["id", "created", "created_by_id", "kind", "kind_other", "uprn", "easting", "northing", "radius", "location_cache", "ward", "where", "estate", "assigned_id"],
        Case_perpetrators: ["case_id", "user_id"],
    }

    special = {
        "easting": lambda o: round(o.point.x) if o.point else "",
        "northing": lambda o: round(o.point.y) if o.point else "",
        "type": lambda o: o.type.name if o.type else "",
        "best_time": lambda o: ",".join(o.best_time or []),
        "created": lambda o: o.created.isoformat(timespec="seconds"),
        "start": lambda o: o.start.isoformat(timespec="seconds"),
        "end": lambda o: o.end.isoformat(timespec="seconds"),
    }

    def add_arguments(self, parser):
        parser.add_argument("--dir", help="Directory to output CSV files to")
        parser.add_argument("--s3", help="Export CSV files to S3 bucket", action="store_true")

    def _set_verbosity(self, options):
        verbosity = int(options['verbosity'])
        if verbosity > 2:
            boto3.set_stream_logger(name="smart_open", level=logging.DEBUG)
        elif verbosity > 1:
            boto3.set_stream_logger(name="smart_open", level=logging.INFO)

    def _set_method(self, options):
        if (options["dir"] and options["s3"]) or (not options["dir"] and not options["s3"]):
            raise CommandError("Please specify an out directory or to export to S3")
        if options["dir"]:
            self.dir = Path(options["dir"])
            self.method = "file"
        if options["s3"]:
            self.method = "s3"

    def handle(self, *args, **options):
        self._set_verbosity(options)
        self._set_method(options)
        self.compile_csv(Case.objects.all())
        self.compile_csv(HistoricalCase.objects.all())
        self.compile_csv(Complaint.objects.all())
        self.compile_csv(Action.objects.select_related("type"))
        self.compile_csv(User.objects.all())
        self.compile_csv(Case_perpetrators.objects.all())

    def compile_csv(self, queryset):
        model = queryset.model
        field_names = self.fields[model]
        basename = f"{model.__name__}.csv"

        if self.method == "s3":
            path = f"s3://{s3_settings['BUCKET_NAME']}/{basename}"
            path_kwargs = dict(mode="w", transport_params=dict(client=client))
        else:
            path = self.dir / basename
            path_kwargs = dict(mode="w")

        fp = open(path, **path_kwargs)
        writer = csv.writer(fp)
        writer.writerow(field_names)
        for row in queryset:
            values = []
            for field in field_names:
                if field in self.special:
                    value = self.special[field](row)
                else:
                    value = getattr(row, field)
                if value is None:
                    value = ''
                values.append(value)
            writer.writerow(values)
        fp.close()
