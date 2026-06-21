from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0068_fileshare_deleted_at_homewidget_deleted_at_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="profile_banner",
        ),
    ]
