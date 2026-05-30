from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import ChatMessage, ChatRoomMember, DrawingGameInvite, Friendship, UserProfile


def get_notification_counts(user):
    """Return all small header notification counters for the current user."""
    counts = {
        "unread_chat_messages": 0,
        "incoming_friend_requests": 0,
        "skribble_invites": 0,
        "total_notifications": 0,
    }

    if not getattr(user, "is_authenticated", False):
        return counts

    profile, _created = UserProfile.objects.get_or_create(user=user)
    muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications

    try:
        if profile.notify_friend_requests and not muted_by_dnd:
            counts["incoming_friend_requests"] = Friendship.objects.filter(
            to_user=user,
                status=Friendship.STATUS_PENDING,
            ).count()
    except Exception:
        counts["incoming_friend_requests"] = 0

    try:
        if profile.notify_skribble and not muted_by_dnd:
            counts["skribble_invites"] = DrawingGameInvite.objects.filter(
            to_user=user,
                status=DrawingGameInvite.STATUS_PENDING,
            ).count()
    except Exception:
        counts["skribble_invites"] = 0

    try:
        if not profile.notify_chat or muted_by_dnd:
            raise StopIteration
        unread_count = 0
        memberships = ChatRoomMember.objects.filter(user=user).select_related("room")

        for membership in memberships:
            unread_qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user)

            if membership.last_read_at:
                unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)

            unread_count += unread_qs.count()

        counts["unread_chat_messages"] = unread_count
    except StopIteration:
        counts["unread_chat_messages"] = 0
    except Exception:
        counts["unread_chat_messages"] = 0

    counts["total_notifications"] = (
        counts["unread_chat_messages"]
        + counts["incoming_friend_requests"]
        + counts["skribble_invites"]
    )

    return counts


def get_notification_items(user, limit=10):
    if not getattr(user, "is_authenticated", False):
        return []

    profile, _created = UserProfile.objects.get_or_create(user=user)
    muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications
    items = []

    if profile.notify_chat and not muted_by_dnd:
        for membership in ChatRoomMember.objects.filter(user=user).select_related("room"):
            qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user).select_related("sender").order_by("-created_at")
            if membership.last_read_at:
                qs = qs.filter(created_at__gt=membership.last_read_at)
            unread_count = qs.count()
            latest = qs.first()
            if unread_count and latest:
                room_title = membership.room.title_for(user)
                items.append({
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
        for friendship in Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).select_related("from_user").order_by("-created_at")[:limit]:
            items.append({
                "type": "friend",
                "icon": "fa-solid fa-user-plus",
                "title": _("Freundschaftsanfrage"),
                "text": _("%(user)s möchte mit dir befreundet sein") % {"user": friendship.from_user.username},
                "url": reverse("profile") + "#friend-requests",
                "action_label": _("Ansehen"),
                "created_at": friendship.created_at,
                "badge": 1,
            })

    if profile.notify_skribble and not muted_by_dnd:
        for invite in DrawingGameInvite.objects.filter(to_user=user, status=DrawingGameInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at")[:limit]:
            items.append({
                "type": "skribble",
                "icon": "fa-solid fa-pencil",
                "title": _("Skribble-Einladung"),
                "text": _("%(user)s hat dich in %(lobby)s eingeladen") % {"user": invite.from_user.username, "lobby": invite.lobby.name},
                "url": reverse("skribble_lobby", args=[invite.lobby.code]),
                "action_label": _("Beitreten"),
                "created_at": invite.created_at,
                "badge": 1,
            })

    items.sort(key=lambda item: item.get("created_at") or timezone.now(), reverse=True)
    return items[:limit]
