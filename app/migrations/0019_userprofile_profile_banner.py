from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0018_homewidget_clock_design_homewidget_clock_style_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_banner",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_banners/",
                verbose_name="Profilbanner",
            ),
        ),
    ]
