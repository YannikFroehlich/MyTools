from django.conf import settings
from django.urls import NoReverseMatch, reverse

from .access_control import ACCESS_CONTROL_ITEMS, user_can_access_key, user_can_see_key
from .models import SiteAccessSettings, UserProfile
from .notification_utils import get_notification_counts


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
        "use_fontawesome_kit": getattr(settings, "USE_FONTAWESOME_KIT", False),
    }




def analytics_settings(request):
    return {
        "google_analytics_enabled": getattr(settings, "GOOGLE_ANALYTICS_ENABLED", False),
        "google_analytics_id": getattr(settings, "GOOGLE_ANALYTICS_ID", ""),
    }


def access_control_status(request):
    if not request.user.is_authenticated:
        return {
            "access_blocked_keys": {},
            "access_blocked_paths": [],
            "access_restricted_paths": [],
            "access_hidden_paths": [],
            "access_hidden_visible_paths": [],
        }

    try:
        access_settings = SiteAccessSettings.get_solo()
    except Exception:
        return {
            "access_blocked_keys": {},
            "access_blocked_paths": [],
            "access_restricted_paths": [],
            "access_hidden_paths": [],
            "access_hidden_visible_paths": [],
        }

    blocked_keys = {}
    blocked_paths = set()
    restricted_paths = set()
    hidden_paths = set()
    hidden_visible_paths = set()

    for item in ACCESS_CONTROL_ITEMS:
        key = item["key"]
        access_level = access_settings.get_tool_access_level(key)
        is_restricted = access_level != SiteAccessSettings.TOOL_ACCESS_ALL
        is_blocked = not user_can_access_key(request.user, key, access_settings)
        is_hidden = access_level == SiteAccessSettings.TOOL_ACCESS_HIDDEN
        is_hidden_for_user = is_hidden and not user_can_see_key(request.user, key, access_settings)
        blocked_keys[key] = is_blocked

        if is_hidden_for_user:
            path_bucket = hidden_paths
        elif is_hidden:
            path_bucket = hidden_visible_paths
        elif is_blocked:
            path_bucket = blocked_paths
        elif is_restricted:
            path_bucket = restricted_paths
        else:
            path_bucket = None

        if path_bucket is None:
            continue

        for url_name in item.get("url_names", ()):
            try:
                path_bucket.add(reverse(url_name))
            except NoReverseMatch:
                continue

    return {
        "access_blocked_keys": blocked_keys,
        "access_blocked_paths": sorted(blocked_paths),
        "access_restricted_paths": sorted(restricted_paths),
        "access_hidden_paths": sorted(hidden_paths),
        "access_hidden_visible_paths": sorted(hidden_visible_paths),
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
