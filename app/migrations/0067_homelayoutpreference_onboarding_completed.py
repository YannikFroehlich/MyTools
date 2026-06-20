from django.db import migrations, models


def mark_existing_layouts_as_completed(apps, schema_editor):
    HomeLayoutPreference = apps.get_model("app", "HomeLayoutPreference")
    HomeLayoutPreference.objects.update(onboarding_completed=True)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0066_werewolflobby_werewolfinvite_werewolfmessage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="homelayoutpreference",
            name="onboarding_completed",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_layouts_as_completed, migrations.RunPython.noop),
    ]
