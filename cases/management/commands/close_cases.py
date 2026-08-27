import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cases.models import Action, ActionType, Case


class Command(BaseCommand):
    help = "Close cases that have had no recurrences after a period of time"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", help="Number of days after which to close cases", type=int
        )
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        if not options["days"]:
            raise CommandError("Please specify a number of days")

        type = ActionType.objects.get(name="Case closed")
        notes = "Automatically closed"
        cutoff = timezone.now() - datetime.timedelta(days=options["days"])

        query = Case.objects.open_last_modified_including_mergees_before(cutoff)
        for entry in query:
            case = Case.objects.get(id=entry.id)
            if case.where != "business":
                continue
            with transaction.atomic():
                case.closed = True
                # Creating the action will save the case via a signal
                Action.objects.create(case=case, type=type, notes=notes)
                if not options["commit"]:
                    transaction.set_rollback(True)
                if options["verbosity"]:
                    self.stdout.write(f"Automatically closing case #{case.id}")
