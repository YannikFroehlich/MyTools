from django.db import migrations, models


def populate_avatar_order(apps, schema_editor):
    AvatarCharacter = apps.get_model("app", "AvatarCharacter")

    for index, character in enumerate(AvatarCharacter.objects.order_by("name", "created_at")):
        character.order = index
        character.save(update_fields=["order"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0006_avatar_character"),
    ]

    operations = [
        migrations.AddField(
            model_name="avatarcharacter",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(populate_avatar_order, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="avatarcharacter",
            options={"ordering": ["order", "created_at"]},
        ),
    ]
