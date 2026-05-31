from django.conf import settings

from .models import UserProfile
from .notification_utils import get_notification_counts


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }


def current_profile(request):
    if not request.user.is_authenticated:
        return {
            "current_profile": None,
            "incoming_friend_requests_count": 0,
            "unread_chat_messages_count": 0,
            "skribble_invites_count": 0,
            "tictactoe_invites_count": 0,
            "connectfour_invites_count": 0,
            "battleship_invites_count": 0,
            "stadtlandfluss_invites_count": 0,
            "total_notifications_count": 0,
        }

    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        profile = None

    counts = get_notification_counts(request.user)

    return {
        "current_profile": profile,
        "incoming_friend_requests_count": counts["incoming_friend_requests"],
        "unread_chat_messages_count": counts["unread_chat_messages"],
        "skribble_invites_count": counts["skribble_invites"],
        "tictactoe_invites_count": counts["tictactoe_invites"],
        "connectfour_invites_count": counts["connectfour_invites"],
        "battleship_invites_count": counts["battleship_invites"],
        "stadtlandfluss_invites_count": counts["stadtlandfluss_invites"],
        "total_notifications_count": counts["total_notifications"],
    }
