from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from cases.models import ActionFile


class Command(BaseCommand):
    help = "Delete all files in local storage that don't correspond to an object in the database"

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str)

    def handle(self, *args, **options):
        if not options["path"]:
            raise CommandError("Please specify a path")

        storage = FileSystemStorage(location=options["path"])
        _, storage_filenames = storage.listdir("")
        action_filenames = [af.file.name for af in ActionFile.objects.all()]

        for fn in storage_filenames:
            if fn not in action_filenames:
                storage.delete(fn)
