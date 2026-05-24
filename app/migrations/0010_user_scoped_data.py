from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_data_to_first_user(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    user = User.objects.filter(is_superuser=True).order_by("id").first()
    if user is None:
        user = User.objects.order_by("id").first()
    if user is None:
        return

    for model_name in ("AvatarCharacter", "Note", "ShortcutSection", "WeatherLocation"):
        model = apps.get_model("app", model_name)
        model.objects.filter(user__isnull=True).update(user=user)

    Shortcut = apps.get_model("app", "Shortcut")
    Shortcut.objects.filter(user__isnull=True).update(user=user)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0009_weatherlocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="avatarcharacter",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="avatar_characters",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="note",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="shortcut",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shortcuts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="shortcutsection",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shortcut_sections",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="weatherlocation",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="weather_locations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_existing_data_to_first_user, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="weatherlocation",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AddConstraint(
            model_name="weatherlocation",
            constraint=models.UniqueConstraint(
                fields=("user", "name"),
                name="unique_weather_location_per_user",
            ),
        ),
    ]
