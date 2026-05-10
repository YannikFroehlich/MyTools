from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_alter_shortcut_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="AvatarCharacter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("nation", models.CharField(choices=[("Feuer", "Feuernation"), ("Wasser", "Wasserstamm"), ("Erde", "Erdkönigreich"), ("Luft", "Luftnomaden")], max_length=20)),
                ("link", models.URLField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("image", models.ImageField(upload_to="avatar_characters/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name", "created_at"],
            },
        ),
    ]
