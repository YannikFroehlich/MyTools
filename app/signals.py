from django.db import transaction
from django.db.backends.signals import connection_created
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete

from .models import (
    BattleshipInvite,
    ConnectFourInvite,
    DrawingGameInvite,
    FileShare,
    Friendship,
    HangmanInvite,
    InboxItem,
    KniffelInvite,
    PongInvite,
    StadtLandFlussInvite,
    TicTacToeInvite,
    UnoInvite,
    UserProfile,
)
from .notification_utils import invalidate_notification_cache_for_user_id


INVITE_MODELS = (
    DrawingGameInvite,
    TicTacToeInvite,
    ConnectFourInvite,
    BattleshipInvite,
    StadtLandFlussInvite,
    UnoInvite,
    KniffelInvite,
    HangmanInvite,
    PongInvite,
)


def _configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout = 20000")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")


def _invalidate_users_on_commit(user_ids):
    normalized_ids = sorted({int(user_id) for user_id in user_ids if user_id})
    if not normalized_ids:
        return

    def invalidate_users():
        for user_id in normalized_ids:
            invalidate_notification_cache_for_user_id(user_id)

    transaction.on_commit(invalidate_users)


INVITE_PUSH_META = {
    "DrawingGameInvite": ("Skribble-Einladung", "skribble_lobby", "lobby"),
    "TicTacToeInvite": ("Tic-Tac-Toe-Einladung", "tictactoe_lobby", "game"),
    "ConnectFourInvite": ("Vier-gewinnt-Einladung", "connectfour_lobby", "game"),
    "BattleshipInvite": ("Schiffe-versenken-Einladung", "battleship_lobby", "game"),
    "StadtLandFlussInvite": ("Stadt-Land-Fluss-Einladung", "stadtlandfluss_lobby", "lobby"),
    "UnoInvite": ("Uno-Einladung", "uno_lobby", "game"),
    "KniffelInvite": ("Kniffel-Einladung", "kniffel_lobby", "game"),
    "HangmanInvite": ("Hangman-Einladung", "hangman_lobby", "lobby"),
    "PongInvite": ("Pong-Einladung", "pong_lobby", "game"),
}


def _send_invite_push_on_commit(instance, title, url_name, object_attr):
    invite_id = instance.pk
    sender_name = getattr(instance.from_user, "username", "Jemand")
    target_user = instance.to_user

    def send_push():
        from django.urls import reverse
        from .push_utils import send_web_push_to_user

        target = getattr(instance, object_attr, None)
        code = getattr(target, "code", "")
        url = reverse(url_name, args=[code]) if code else reverse("home")
        send_web_push_to_user(
            target_user,
            title=title,
            body=f"{sender_name} hat dich eingeladen.",
            url=url,
            tag=f"invite:{invite_id}",
        )

    transaction.on_commit(send_push)


def _invite_changed(sender, instance, created=False, **kwargs):
    _invalidate_users_on_commit([instance.from_user_id, instance.to_user_id])
    if not created or getattr(instance, "status", "") != getattr(instance, "STATUS_PENDING", "pending"):
        return

    meta = INVITE_PUSH_META.get(sender.__name__)
    if meta:
        _send_invite_push_on_commit(instance, *meta)


def _friendship_changed(sender, instance, **kwargs):
    _invalidate_users_on_commit([instance.from_user_id, instance.to_user_id])


def _profile_changed(sender, instance, **kwargs):
    _invalidate_users_on_commit([instance.user_id])


def _file_share_recipients_changed(sender, instance, action, pk_set=None, **kwargs):
    if action == "pre_clear":
        instance._live_status_recipient_ids = list(instance.recipients.values_list("id", flat=True))
        return

    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    if action == "post_clear":
        user_ids = getattr(instance, "_live_status_recipient_ids", [])
    else:
        user_ids = pk_set or []

    _invalidate_users_on_commit(user_ids)


def _file_share_deleted(sender, instance, **kwargs):
    user_ids = list(instance.recipients.values_list("id", flat=True))
    _invalidate_users_on_commit(user_ids)


def _send_inbox_push_on_commit(inbox_item_id):
    def send_push():
        from .models import InboxItem
        from .push_utils import send_web_push_to_user

        try:
            item = InboxItem.objects.select_related("user").get(pk=inbox_item_id, is_read=False)
        except InboxItem.DoesNotExist:
            return

        send_web_push_to_user(
            item.user,
            title=item.title,
            body=item.message,
            url=item.target_url,
            tag=f"inbox:{item.pk}",
        )

    transaction.on_commit(send_push)


def _inbox_item_created(sender, instance, created, **kwargs):
    if created:
        _send_inbox_push_on_commit(instance.pk)


for model in INVITE_MODELS:
    post_save.connect(
        _invite_changed,
        sender=model,
        dispatch_uid=f"app.live_status.{model.__name__}.post_save",
    )
    post_delete.connect(
        _invite_changed,
        sender=model,
        dispatch_uid=f"app.live_status.{model.__name__}.post_delete",
    )

post_save.connect(
    _friendship_changed,
    sender=Friendship,
    dispatch_uid="app.live_status.friendship.post_save",
)
post_delete.connect(
    _friendship_changed,
    sender=Friendship,
    dispatch_uid="app.live_status.friendship.post_delete",
)
post_save.connect(
    _profile_changed,
    sender=UserProfile,
    dispatch_uid="app.live_status.user_profile.post_save",
)
post_save.connect(
    _inbox_item_created,
    sender=InboxItem,
    dispatch_uid="app.web_push.inbox_item.post_save",
)
m2m_changed.connect(
    _file_share_recipients_changed,
    sender=FileShare.recipients.through,
    dispatch_uid="app.live_status.file_share.recipients",
)
pre_delete.connect(
    _file_share_deleted,
    sender=FileShare,
    dispatch_uid="app.live_status.file_share.pre_delete",
)
connection_created.connect(
    _configure_sqlite_connection,
    dispatch_uid="app.sqlite.configure_connection",
)
