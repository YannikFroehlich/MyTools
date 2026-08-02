from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0085_shoppinglist_category_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteaccesssettings",
            name="tool_device_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
