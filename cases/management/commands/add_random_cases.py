import random
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from cases.models import Action, ActionType, Case, Complaint
from noiseworks import cobrand


class Command(BaseCommand):
    help = "Create a number of random cases in the database"
    _uprns = None

    def add_arguments(self, parser):
        parser.add_argument("--number", type=int)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--fixed", action="store_true")
        parser.add_argument("--uprns", help="File containing list of UPRNs to use")

    def handle(self, *args, **options):
        if not options["uprns"]:
            raise CommandError("Please specify a filename to a list of UPRNs")
        self.load_uprns(options["uprns"])
        N = options["number"]
        if not N:
            raise CommandError("Please specify a number of cases to create")
        self.commit = options["commit"]
        if options["fixed"]:  # pragma: no cover
            random.seed(44)

        for model in (Case, Complaint, Action):
            field = model._meta.get_field("created")
            field.auto_now_add = False
            field = model._meta.get_field("modified")
            field.auto_now = False

        self.set_up_staff_users()

        dates = []
        date = self.now = timezone.now()
        for i in range(N):
            dates.insert(0, date)
            date -= timedelta(minutes=random.randint(1, 360))

        user = None
        id = User.objects.count()
        for i in range(N):
            case = Case(
                kind=self._pick_kind(),
                where=self._pick_where(),
                created=dates[i],
                modified=dates[i],
            )
            if case.where == "residence":
                case.estate = self._pick_estate()
            if case.kind == "other":
                case.kind_other = "Other type of noise"

            if random.randint(0, 2) == 0:
                # Location
                case.point, case.ward = self._pick_location()
                case.radius = self._pick_radius()
                case.location_display
            else:
                self._pick_uprn(case)

            if options["commit"]:
                case.save()

            # Assign all cases created apart from most recent 10
            if i < N - 10:
                case.assigned = self.staff_for_ward[case.ward]
                case.modified = dates[i] + timedelta(hours=random.randint(1, 4))
                case.modified_by = case.assigned
                if options["commit"]:
                    case.save()

            # Actions
            self.add_actions(case, case.modified, i < N - 10, i < N - 20)

            if random.randint(1, 5) == 1:
                # Add a perpetrator
                id += 1
                user = User(
                    username=f"user-{id}",
                    first_name="Perpetrator",
                    last_name=f"{id}",
                    address="1 High Street",
                )
                if options["commit"]:
                    user.save()
                    case.perpetrators.add(user)

            complaints = self._num_complaints()

            self.stdout.write(
                f"Creating case #{case.id}, {case.kind}, {case.where}, {case.location_display}, with {complaints} occurrences"
            )

            if not user or random.randint(1, 4) != 1:
                id += 1
                user = User(
                    email=f"madeup-{id}@noiseworks",
                    username=f"user-{id}",
                    first_name="User",
                    last_name=f"{id}",
                    email_verified=1,
                    best_time=self._pick_best_time(),
                    best_method=self._pick_best_method(),
                )
                self._pick_user_uprn(user)
                if options["commit"]:
                    user.save()

            complaint_date = dates[i]
            for c in range(complaints):
                complaint = Complaint(
                    case=case,
                    complainant=user,
                    happening_now=self._pick_happening_now(),
                    rooms="[rooms affected]",
                    description="[description of noise]",
                    effect="[effect of noise]",
                    start=complaint_date - timedelta(minutes=random.randint(30, 120)),
                    end=complaint_date,
                    created=complaint_date,
                    modified=complaint_date,
                )
                complaint_date += timedelta(minutes=random.randint(1, 10080))

                if options["commit"]:
                    complaint.save()

        # Reinstate auto fields (in case called with call_command)
        for model in (Case, Complaint, Action):
            field = model._meta.get_field("created")
            field.auto_now_add = True
            field = model._meta.get_field("modified")
            field.auto_now = True

    # Case

    def _pick_uprn(self, case):
        while True:
            case.uprn = random.choice(self.uprns)
            case.update_location_cache()
            if case.location_cache:
                break

    def _pick_kind(self):
        r = random.randint(1, 20)
        if r <= 10:
            return "music"
        elif r <= 15:
            return "other"
        elif r <= 17:
            return "shouting"
        else:
            choices = [
                c[0]
                for c in Case.KIND_CHOICES
                if c[0] not in ("music", "other", "shouting")
            ]
            return random.choice(choices)

    def _pick_where(self):
        if random.randint(1, 6) == 1:
            return "business"
        else:
            return "residence"

    def _pick_estate(self):
        r = random.randint(1, 5)
        if r in (1, 2):
            return "y"
        elif r in (3, 4):
            return "?"
        else:
            return "n"

    def _pick_location(self):
        while True:
            e = random.randint(531480, 537642)
            n = random.randint(181839, 188327)
            p = Point(e, n, srid=27700)
            data = self._mapit_call(e, n)
            if "error" in data.keys():
                raise Exception("Error calling MapIt")
            if "2508" in data.keys():
                ward = None
                for area in data.values():
                    if area["type"] == "LBW":
                        ward = area["codes"]["gss"]
                return p, ward
            if random.randint(1, 99) == 1:  # pragma: no cover
                return p, "outside"

    def _pick_radius(self):
        r = random.randint(1, 10)
        if r <= 5:
            return 30
        elif r <= 9:
            return 180
        else:
            return 800

    def _num_complaints(self):
        r = random.randint(1, 100)
        if r in (3, 4, 5, 6):
            return r
        elif r == 2:
            return 3
        elif r <= 10:
            return 2
        else:
            return 1

    # Complaint

    def _pick_happening_now(self):
        return random.randint(1, 10) != 1

    # User

    def set_up_staff_users(self):
        user = self.create(
            User,
            username="auto-staff-outside@noiseworks",
            defaults={
                "email": "auto-staff-outside@noiseworks",
                "first_name": "Staff User",
                "last_name": "Outside",
                "email_verified": 1,
                "is_staff": True,
            },
        )
        staff_for_ward = {"outside": user}
        wards = list(map(lambda x: x["gss"], cobrand.api.wards()))
        wards.append(None)  # This is so if wards uneven, last is included
        for pair in zip(wards[::2], wards[1::2]):
            pair = list(filter(None, pair))
            last_name = "".join(map(lambda x: x[-2:], pair))
            user = self.create(
                User,
                username=f"auto-staff-{pair[0]}@noiseworks",
                defaults={
                    "email": f"auto-staff-{pair[0]}@noiseworks",
                    "first_name": "Staff User",
                    "last_name": last_name,
                    "email_verified": 1,
                    "wards": pair,
                    "is_staff": True,
                },
            )
            for ward in pair:
                staff_for_ward[ward] = user
        self.staff_for_ward = staff_for_ward

    def _pick_best_method(self):
        if random.randint(1, 2) == 1:
            return "email"
        else:
            return "phone"

    def _pick_best_time(self):
        r = random.randint(1, 20)
        if r == 1:
            return ["weekday", "evening"]
        elif r == 2:
            return ["weekday", "weekend"]
        elif r == 3:
            return ["weekend"]
        elif r == 4:
            return ["weekend", "evening"]
        elif r in (5, 6):
            return ["evening"]
        elif r in (7, 8, 9, 10):
            return ["weekday"]
        else:
            return ["weekday", "weekend", "evening"]

    def _pick_user_uprn(self, user):
        while True:
            user.uprn = random.choice(self.uprns)
            user.update_address()
            if user.address:
                break

    # Actions

    def add_actions(self, case, date, one_action, two_actions):
        if one_action:
            action_date = date + timedelta(hours=random.randint(1, 4))
            type = ActionType.objects.get(name="Contacted complainant")
            self.create_action(case, action_date, type)
        if two_actions:
            action_date += timedelta(hours=random.randint(24, 168))
            type = ActionType.objects.exclude(
                name__in=("Contacted complainant", "Edit case")
            ).order_by("?")[0]
            self.create_action(case, action_date, type)

    def create_action(self, case, date, type):
        if date > self.now:
            date = self.now
        action = Action(
            case=case, created_by=case.assigned, created=date, modified=date
        )
        action.type = type
        action.notes = "Internal notes about this action would be here"
        if self.commit:
            action.save()

    # Helpers

    @property
    def uprns(self):
        return self._uprns

    def load_uprns(self, uprns_file=None):
        uprns = []
        for line in open(uprns_file):
            uprns.append(int(line))
        self._uprns = uprns

    def _mapit_call(self, e, n):
        key = settings.MAPIT_API_KEY
        d = requests.get(
            f"https://mapit.mysociety.org/point/27700/{e},{n}?api_key={key}"
        ).json()
        return d

    def create(self, model, defaults=None, **kwargs):
        if self.commit:
            obj, _ = model.objects.get_or_create(**kwargs, defaults=defaults)
        else:
            obj = model(**kwargs, **defaults)
        return obj
