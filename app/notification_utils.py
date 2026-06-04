from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    BattleshipInvite,
    ChatMessage,
    ChatRoomMember,
    ConnectFourInvite,
    DrawingGameInvite,
    Friendship,
    HangmanInvite,
    NotificationDismissal,
    StadtLandFlussInvite,
    TicTacToeInvite,
    UnoInvite,
    UserProfile,
)

COUNT_KEYS = (
    "unread_chat_messages",
    "incoming_friend_requests",
    "skribble_invites",
    "tictactoe_invites",
    "connectfour_invites",
    "battleship_invites",
    "stadtlandfluss_invites",
    "uno_invites",
    "hangman_invites",
)

TYPE_COUNT_KEY = {
    "chat": "unread_chat_messages",
    "friend": "incoming_friend_requests",
    "skribble": "skribble_invites",
    "tictactoe": "tictactoe_invites",
    "connectfour": "connectfour_invites",
    "battleship": "battleship_invites",
    "stadtlandfluss": "stadtlandfluss_invites",
    "uno": "uno_invites",
    "hangman": "hangman_invites",
}


def empty_notification_counts():
    counts = {key: 0 for key in COUNT_KEYS}
    counts["total_notifications"] = 0
    return counts


def dismissed_notification_keys(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(NotificationDismissal.objects.filter(user=user).values_list("key", flat=True))


def _is_visible(item, dismissed_keys):
    return item.get("key") not in dismissed_keys


def _add_invite_items(items, qs, *, item_type, icon, title, text_template, url_name, object_attr, dismissed_keys, limit):
    added = 0
    for invite in qs:
        game_object = getattr(invite, object_attr)
        key = f"{item_type}:{invite.pk}"
        if key in dismissed_keys:
            continue
        items.append({
            "key": key,
            "type": item_type,
            "icon": icon,
            "title": title,
            "text": text_template % {"user": invite.from_user.username, "name": game_object.name},
            "url": reverse(url_name, args=[game_object.code]),
            "action_label": _("Beitreten"),
            "created_at": invite.created_at,
            "badge": 1,
        })
        added += 1
        if added >= limit:
            break


def _collect_notification_items(user, *, limit=10, include_dismissed=False):
    if not getattr(user, "is_authenticated", False):
        return []

    profile, _created = UserProfile.objects.get_or_create(user=user)
    muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications
    dismissed_keys = set() if include_dismissed else dismissed_notification_keys(user)
    items = []

    if profile.notify_chat and not muted_by_dnd:
        for membership in ChatRoomMember.objects.filter(user=user).select_related("room"):
            qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user).select_related("sender").order_by("-created_at")
            if membership.last_read_at:
                qs = qs.filter(created_at__gt=membership.last_read_at)
            unread_count = qs.count()
            latest = qs.first()
            if unread_count and latest:
                key = f"chat:{membership.room_id}:{latest.pk}"
                if key in dismissed_keys:
                    continue
                room_title = membership.room.title_for(user)
                items.append({
                    "key": key,
                    "type": "chat",
                    "icon": "fa-solid fa-comments",
                    "title": room_title,
                    "text": _("%(count)s ungelesene Nachricht(en) von %(user)s") % {"count": unread_count, "user": latest.sender.username},
                    "url": reverse("chat_room", args=[membership.room_id]),
                    "action_label": _("Zum Chat"),
                    "created_at": latest.created_at,
                    "badge": unread_count,
                })

    if profile.notify_friend_requests and not muted_by_dnd:
        added = 0
        friendships = Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).select_related("from_user").order_by("-created_at")
        for friendship in friendships:
            key = f"friend:{friendship.pk}"
            if key in dismissed_keys:
                continue
            items.append({
                "key": key,
                "type": "friend",
                "icon": "fa-solid fa-user-plus",
                "title": _("Freundschaftsanfrage"),
                "text": _("%(user)s möchte mit dir befreundet sein") % {"user": friendship.from_user.username},
                "url": reverse("profile") + "#friend-requests",
                "action_label": _("Ansehen"),
                "created_at": friendship.created_at,
                "badge": 1,
            })
            added += 1
            if added >= limit:
                break

    if profile.notify_skribble and not muted_by_dnd:
        _add_invite_items(
            items,
            DrawingGameInvite.objects.filter(to_user=user, status=DrawingGameInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="skribble",
            icon="fa-solid fa-pencil",
            title=_("Skribble-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="skribble_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            TicTacToeInvite.objects.filter(to_user=user, status=TicTacToeInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="tictactoe",
            icon="fa-solid fa-table-cells",
            title=_("Tic-Tac-Toe-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="tictactoe_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            ConnectFourInvite.objects.filter(to_user=user, status=ConnectFourInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="connectfour",
            icon="fa-solid fa-grip",
            title=_("Vier-gewinnt-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="connectfour_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            BattleshipInvite.objects.filter(to_user=user, status=BattleshipInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="battleship",
            icon="fa-solid fa-anchor",
            title=_("Schiffe-versenken-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="battleship_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            StadtLandFlussInvite.objects.filter(to_user=user, status=StadtLandFlussInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="stadtlandfluss",
            icon="fa-solid fa-pen-to-square",
            title=_("Stadt-Land-Fluss-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="stadtlandfluss_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            UnoInvite.objects.filter(to_user=user, status=UnoInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="uno",
            icon="fa-solid fa-layer-group",
            title=_("Uno-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="uno_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            HangmanInvite.objects.filter(to_user=user, status=HangmanInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="hangman",
            icon="fa-solid fa-user-secret",
            title=_("Hangman-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="hangman_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )

    items.sort(key=lambda item: item.get("created_at") or timezone.now(), reverse=True)
    return items


def get_notification_counts(user):
    """Return all small header notification counters for the current user."""
    counts = empty_notification_counts()

    for item in _collect_notification_items(user, limit=1000):
        count_key = TYPE_COUNT_KEY.get(item.get("type"))
        if count_key:
            counts[count_key] += int(item.get("badge") or 1)

    counts["total_notifications"] = sum(counts[key] for key in COUNT_KEYS)
    return counts


def get_notification_items(user, limit=10):
    return _collect_notification_items(user, limit=limit)[:limit]
