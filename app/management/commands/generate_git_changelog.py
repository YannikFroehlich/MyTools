from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from scripts.generate_git_changelog import DEFAULT_OUTPUT, generate_git_changelog


class Command(BaseCommand):
    help = "Generate the JSON file used by the Was-ist-neu Git changelog section."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Number of non-merge commits to include.")
        parser.add_argument(
            "--output",
            type=Path,
            default=DEFAULT_OUTPUT,
            help="Output JSON path. Relative paths are resolved from BASE_DIR.",
        )

    def handle(self, *args, **options):
        payload = generate_git_changelog(settings.BASE_DIR, options["output"], options["limit"])
        entries = payload.get("entries", [])
        if payload.get("available"):
            self.stdout.write(self.style.SUCCESS(f"Git changelog generated with {len(entries)} commits."))
        else:
            self.stdout.write(self.style.WARNING(f"Git changelog unavailable: {payload.get('reason', 'unknown error')}"))
