from django.core.management.base import BaseCommand

from app.trash_utils import TRASH_RETENTION_DAYS, purge_expired_trash


class Command(BaseCommand):
    help = f"Löscht Papierkorb-Einträge, die älter als {TRASH_RETENTION_DAYS} Tage sind."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Nur die Anzahl anzeigen.")

    def handle(self, *args, **options):
        count = purge_expired_trash(dry_run=options["dry_run"])
        if options["dry_run"]:
            self.stdout.write(f"{count} Einträge würden gelöscht.")
        else:
            self.stdout.write(self.style.SUCCESS(f"{count} abgelaufene Einträge gelöscht."))
