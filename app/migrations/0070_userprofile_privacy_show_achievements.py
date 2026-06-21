from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0069_remove_userprofile_profile_banner"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="privacy_show_achievements",
            field=models.BooleanField(default=True),
        ),
    ]
