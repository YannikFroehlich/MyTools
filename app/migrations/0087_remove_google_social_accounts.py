from django.db import migrations


def remove_google_accounts(apps, schema_editor):
    # Google login moved to Keycloak; drop the old links and their stored tokens.
    for model in ("SocialAccount", "SocialApp"):
        apps.get_model("socialaccount", model).objects.filter(provider="google").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0086_siteaccesssettings_tool_device_rules"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]

    operations = [migrations.RunPython(remove_google_accounts, migrations.RunPython.noop)]
