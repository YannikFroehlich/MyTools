from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0063_siteaccesssettings_tool_access_rules"),
    ]

    operations = [
        migrations.AlterField(
            model_name="moderationauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("report_resolved", "Meldung erledigt"),
                    ("report_reopened", "Meldung wieder geoeffnet"),
                    ("feedback_status", "Feedback-Status geaendert"),
                    ("file_deleted", "Datei-Freigabe geloescht"),
                    ("user_suspended", "Nutzer gesperrt"),
                    ("user_unsuspended", "Nutzersperre aufgehoben"),
                    ("user_activated", "Nutzer aktiviert"),
                    ("user_deactivated", "Nutzer deaktiviert"),
                    ("access_locked", "Login und Registrierung gesperrt"),
                    ("access_unlocked", "Login und Registrierung entsperrt"),
                    ("tool_access_updated", "Tool-Zugriffe geaendert"),
                    ("media_optimized", "Medien komprimiert"),
                ],
                max_length=40,
            ),
        ),
    ]
