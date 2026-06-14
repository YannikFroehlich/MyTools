from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete

from .models import (
    BattleshipInvite,
    ConnectFourInvite,
    DrawingGameInvite,
    FileShare,
    Friendship,
    HangmanInvite,
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


def _invalidate_users_on_commit(user_ids):
    normalized_ids = sorted({int(user_id) for user_id in user_ids if user_id})
    if not normalized_ids:
        return

    def invalidate_users():
        for user_id in normalized_ids:
            invalidate_notification_cache_for_user_id(user_id)

    transaction.on_commit(invalidate_users)


def _invite_changed(sender, instance, **kwargs):
    _invalidate_users_on_commit([instance.from_user_id, instance.to_user_id])


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
