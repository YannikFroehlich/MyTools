from django.conf import settings

from .models import UserProfile
from .notification_utils import get_notification_counts


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
        "use_fontawesome_kit": getattr(settings, "USE_FONTAWESOME_KIT", False),
    }


def current_profile(request):
    if not request.user.is_authenticated:
        return {
            "current_profile": None,
            "incoming_friend_requests_count": 0,
            "unread_chat_messages_count": 0,
            "note_reminders_count": 0,
            "shared_files_count": 0,
            "game_turns_count": 0,
            "skribble_invites_count": 0,
            "tictactoe_invites_count": 0,
            "connectfour_invites_count": 0,
            "battleship_invites_count": 0,
            "stadtlandfluss_invites_count": 0,
            "uno_invites_count": 0,
            "kniffel_invites_count": 0,
            "hangman_invites_count": 0,
            "pong_invites_count": 0,
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
        "note_reminders_count": counts["note_reminders"],
        "shared_files_count": counts["shared_files"],
        "game_turns_count": counts["game_turns"],
        "skribble_invites_count": counts["skribble_invites"],
        "tictactoe_invites_count": counts["tictactoe_invites"],
        "connectfour_invites_count": counts["connectfour_invites"],
        "battleship_invites_count": counts["battleship_invites"],
        "stadtlandfluss_invites_count": counts["stadtlandfluss_invites"],
        "uno_invites_count": counts["uno_invites"],
        "kniffel_invites_count": counts["kniffel_invites"],
        "hangman_invites_count": counts["hangman_invites"],
        "pong_invites_count": counts["pong_invites"],
        "total_notifications_count": counts["total_notifications"],
    }
