from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from app.models import AvatarCharacter, Note, Shortcut, ShortcutSection, WeatherLocation


class Command(BaseCommand):
    help = "Assign user-less legacy app data to a specific user."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"]
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'User "{username}" does not exist.')

        models = (AvatarCharacter, Note, ShortcutSection, WeatherLocation, Shortcut)
        total = 0

        for model in models:
            updated = model.objects.filter(user__isnull=True).update(user=user)
            total += updated
            self.stdout.write(f"{model.__name__}: {updated}")

        self.stdout.write(self.style.SUCCESS(f"Assigned {total} legacy objects to {username}."))
