import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from cases.models import Notification


class Command(BaseCommand):
    help = "Delete all notifications that are older than a given number of days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            help="Number of days after which to delete a notification",
            type=int,
        )

    def handle(self, *args, **options):
        if not options["days"]:
            raise CommandError("Please specify a number of days")
        cutoff = timezone.now() - datetime.timedelta(days=options["days"])
        Notification.objects.filter(time__lt=cutoff).delete()
