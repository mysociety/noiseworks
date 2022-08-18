import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
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

        cases = Case.objects.annotate(Count("complaints"))
        # Ignore any that have been merged into another case
        cases = cases.exclude(merge_action__id__isnull=False)
        # Ignore any that have had cases merged into them
        cases = cases.exclude(actions__case_old_id__isnull=False)
        cases = cases.filter(complaints__count__lte=1, created__lt=cutoff, closed=False)
        for case in cases:
            with transaction.atomic():
                case.closed = True
                # Creating the action will save the case via a signal
                Action.objects.create(case=case, type=type, notes=notes)
                if not options["commit"]:
                    transaction.set_rollback(True)
                if options["verbosity"]:
                    self.stdout.write(f"Automatically closing case #{case.id}")
