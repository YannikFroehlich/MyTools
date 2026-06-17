from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0062_cookiecosmosv2save"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteaccesssettings",
            name="tool_access_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
