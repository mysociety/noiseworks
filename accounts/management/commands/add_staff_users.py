import csv

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from noiseworks import cobrand


def ward_name_to_id(ward):
    wards = cobrand.api.wards()
    wards = {ward["name"]: ward["gss"] for ward in wards}
    try:
        return wards[ward]
    except KeyError:
        raise CommandError(f"Could not find ward {ward}")


class Command(BaseCommand):
    help = "Add staff users from CSV file"
    ward_mapping = {}

    def add_arguments(self, parser):
        parser.add_argument("--csv-file")
        parser.add_argument("--ward-mapping")
        parser.add_argument("--case-workers", action="store_true")
        parser.add_argument("--commit", action="store_true")

    def handle(self, **options):
        self.commit = options["commit"]
        if not options["csv_file"]:
            raise CommandError("Please specify a CSV file")
        if options["ward_mapping"]:
            self.read_mapping(options["ward_mapping"])

        case_workers = Group.objects.get(name="case_workers")
        group = case_workers if options["case_workers"] else None

        for line in csv.DictReader(open(options["csv_file"])):
            self.add_staff_user(line, group)

    def read_mapping(self, filename):
        for line in csv.DictReader(open(filename)):
            ward = ward_name_to_id(line["Ward"])
            self.ward_mapping.setdefault(line["Name"], []).append(ward)

    def add_staff_user(self, line, group):
        email = line["Email"].lower()
        users = User.objects.filter(email=email, email_verified=True)
        if users.count():
            self.stdout.write(f"User {email} already exists, skipping")
            return

        first, last = line["Name"].rsplit(maxsplit=1)
        if line["Wards"]:
            names = line["Wards"].split("|")
            wards = []
            for name in names:
                if name in self.ward_mapping:
                    wards.extend(self.ward_mapping[name])
                else:
                    wards.append(ward_name_to_id(name))
        else:
            wards = []
        self.stdout.write(f"User {first} {last}, {email}, {wards}")
        if self.commit:
            u = User.objects.create_user(
                first_name=first,
                last_name=last,
                email=email,
                wards=wards,
                is_staff=True,
            )
            if group:
                group.user_set.add(u)
