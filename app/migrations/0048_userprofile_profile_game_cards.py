from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0047_chatroom_pinned_message_chatroom_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_game_cards",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
