from django.conf import settings
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse

from .access_control import (
    ACCESS_CONTROL_ITEMS,
    ACCESS_ITEM_BY_KEY,
    access_key_for_url_name,
    user_is_staff,
)
from .models import SiteAccessSettings, UserProfile
from .notification_utils import get_notification_counts

ACCESS_CONTROL_BUCKETS_CACHE_SECONDS = 300


def _access_control_buckets(access_settings, is_staff):
    """Compute the shared (non-per-request) parts of access_control_status.

    This only depends on the current SiteAccessSettings state and whether the
    user is staff, so it's identical for every non-staff user (and every staff
    user) until settings change - cache it instead of re-running ~150 reverse()
    calls on every single page load.
    """
    cache_key = (
        f"access_control_buckets:{access_settings.pk}:"
        f"{access_settings.updated_at.timestamp()}:{is_staff}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    blocked_keys = {}
    blocked_paths = set()
    restricted_paths = set()
    hidden_paths = set()
    hidden_visible_paths = set()
    device_target_paths = {}

    for item in ACCESS_CONTROL_ITEMS:
        key = item["key"]
        access_level = access_settings.get_tool_access_level(key)
        is_restricted = access_level != SiteAccessSettings.TOOL_ACCESS_ALL
        is_blocked = is_restricted and not is_staff
        is_hidden = access_level == SiteAccessSettings.TOOL_ACCESS_HIDDEN
        is_hidden_for_user = is_hidden and not is_staff
        device_target = access_settings.get_tool_device_target(key)
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

        for url_name in item.get("url_names", ()):
            try:
                path = reverse(url_name)
            except NoReverseMatch:
                continue
            if path_bucket is not None:
                path_bucket.add(path)
            if device_target != SiteAccessSettings.TOOL_DEVICE_BOTH:
                device_target_paths[path] = device_target

    result = {
        "access_blocked_keys": blocked_keys,
        "access_blocked_paths": sorted(blocked_paths),
        "access_restricted_paths": sorted(restricted_paths),
        "access_hidden_paths": sorted(hidden_paths),
        "access_hidden_visible_paths": sorted(hidden_visible_paths),
        "tool_device_target_paths": device_target_paths,
    }
    cache.set(cache_key, result, ACCESS_CONTROL_BUCKETS_CACHE_SECONDS)
    return result


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


def title_suffix(request):
    return {"title_suffix": settings.TITLE_SUFFIX}


def google_oauth_settings(request):
    return {
        "google_oauth_enabled": getattr(settings, "GOOGLE_OAUTH_ENABLED", False),
        "keycloak_login_enabled": getattr(settings, "KEYCLOAK_LOGIN_ENABLED", False),
        "oidc_only": getattr(settings, "OIDC_ONLY", False),
    }


def access_control_status(request):
    default_result = {
        "access_blocked_keys": {},
        "access_blocked_paths": [],
        "access_restricted_paths": [],
        "access_hidden_paths": [],
        "access_hidden_visible_paths": [],
        "tool_device_target_paths": {},
        "current_tool_key": "",
        "current_tool_label": "",
        "current_tool_device_target": SiteAccessSettings.TOOL_DEVICE_BOTH,
    }

    if not request.user.is_authenticated:
        return default_result

    try:
        access_settings = SiteAccessSettings.get_solo()
    except Exception:
        return default_result

    buckets = _access_control_buckets(access_settings, user_is_staff(request.user))

    current_url_name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    current_tool_key = access_key_for_url_name(current_url_name)
    current_item = ACCESS_ITEM_BY_KEY.get(current_tool_key, {})

    return {
        **buckets,
        "current_tool_key": current_tool_key or "",
        "current_tool_label": current_item.get("label", ""),
        "current_tool_device_target": access_settings.get_tool_device_target(current_tool_key) if current_tool_key else SiteAccessSettings.TOOL_DEVICE_BOTH,
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
            "werewolf_invites_count": 0,
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
        "werewolf_invites_count": counts["werewolf_invites"],
        "total_notifications_count": counts["total_notifications"],
    }
