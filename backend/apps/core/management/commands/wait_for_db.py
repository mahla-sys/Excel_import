import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Block until the default database is accepting connections."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60)

    def handle(self, *args, **options):
        timeout = options["timeout"]
        start = time.time()
        while True:
            try:
                connections["default"].cursor()
                self.stdout.write(self.style.SUCCESS("Database is available."))
                return
            except OperationalError:
                if time.time() - start > timeout:
                    self.stderr.write(self.style.ERROR("Database wait timed out."))
                    raise
                self.stdout.write("Waiting for database...")
                time.sleep(1)
