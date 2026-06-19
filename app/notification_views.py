import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.timesince import timesince
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import Friendship, NotificationDismissal, UserProfile, WebPushSubscription
from .notification_utils import (
    get_notification_counts,
    get_notification_items,
    invalidate_notification_cache,
)
from .presence_utils import decorate_profiles_with_presence
from .push_utils import send_web_push_to_user, web_push_is_configured

LIVE_STATUS_CACHE_SECONDS = 4
LIVE_STATUS_CACHE_VERSION = 1
MAX_LIVE_PRESENCE_IDS = 50


def _serialize_item(item):
    created_at = item.get("created_at")
    return {
        "key": item.get("key", ""),
        "type": item.get("type", "info"),
        "icon": item.get("icon", "fa-solid fa-bell"),
        "title": str(item.get("title", "")),
        "text": str(item.get("text", "")),
        "url": item.get("url", "#"),
        "action_label": str(item.get("action_label", "")),
        "badge": item.get("badge", 1),
        "created_at": created_at.isoformat() if created_at else "",
    }


def _parse_presence_ids(request):
    raw_ids = request.GET.get("ids", "")
    user_ids = []

    for raw_id in raw_ids.split(","):
        raw_id = raw_id.strip()
        if not raw_id.isdigit():
            continue

        user_id = int(raw_id)
        if user_id not in user_ids:
            user_ids.append(user_id)

        if len(user_ids) >= MAX_LIVE_PRESENCE_IDS:
            break

    return user_ids


def _can_view_online_status(viewer, profile, accepted_friend_ids):
    if viewer.is_authenticated and viewer.id == profile.user_id:
        return True

    if profile.status == UserProfile.STATUS_INVISIBLE:
        return False

    if profile.privacy_show_online:
        return True

    return profile.user_id in accepted_friend_ids


def _presence_text(profile):
    if profile.activity_status:
        return str(profile.activity_status)

    if profile.is_online:
        return str(_("Online"))

    if profile.last_seen_at:
        return f'{_("Zuletzt online")} {timesince(profile.last_seen_at)}'

    return str(_("Offline"))


def _serialize_presence_profile(profile):
    return {
        "userId": profile.user_id,
        "isOnline": bool(profile.is_online),
        "statusLine": _presence_text(profile),
        "activityStatus": str(profile.activity_status or ""),
    }


def _presence_cache_key(viewer, user_ids):
    ids = ",".join(str(user_id) for user_id in user_ids)
    return f"live-status:v{LIVE_STATUS_CACHE_VERSION}:viewer:{viewer.pk}:presence:{ids}"


def _presence_payload(request, user_ids):
    if not user_ids:
        return []

    cache_key = _presence_cache_key(request.user, user_ids)
    cached_profiles = cache.get(cache_key)
    if cached_profiles is not None:
        return cached_profiles

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user_id__in=user_ids, user__is_active=True)
    )

    decorate_profiles_with_presence(profiles)
    accepted_friend_ids = set(Friendship.friend_ids_for_user(request.user))

    for profile in profiles:
        if not _can_view_online_status(request.user, profile, accepted_friend_ids):
            profile.is_online = False
            profile.last_seen_at = None
            profile.activity_status = ""

    profiles_by_user_id = {profile.user_id: profile for profile in profiles}
    payload = [
        _serialize_presence_profile(profiles_by_user_id[user_id])
        for user_id in user_ids
        if user_id in profiles_by_user_id
    ]
    cache.set(cache_key, payload, LIVE_STATUS_CACHE_SECONDS)
    return payload


def _notification_payload(user, *, include_items=True):
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None

    payload = {
        "ok": True,
        "counts": get_notification_counts(user),
        "settings": {
            "browser_notifications": bool(getattr(profile, "browser_notifications", False)),
            "sound_notifications": bool(getattr(profile, "sound_notifications", False)),
        },
    }

    if include_items:
        payload["items"] = [_serialize_item(item) for item in get_notification_items(user, limit=12)]

    return payload


def _center_payload(user):
    return _notification_payload(user, include_items=True)


@login_required
@never_cache
@require_GET
def notification_counts_api(request):
    return JsonResponse({
        "ok": True,
        "counts": get_notification_counts(request.user),
    })


@login_required
@never_cache
@require_GET
def notification_center_api(request):
    return JsonResponse(_center_payload(request.user))


@login_required
@never_cache
@require_GET
def live_status_api(request):
    include_items = request.GET.get("items") == "1"
    payload = _notification_payload(request.user, include_items=include_items)
    payload["profiles"] = _presence_payload(request, _parse_presence_ids(request))
    return JsonResponse(payload)


@login_required
@never_cache
@require_POST
def notification_dismiss_api(request):
    key = (request.POST.get("key") or "").strip()
    visible_keys = {item.get("key") for item in get_notification_items(request.user, limit=1000)}

    if not key or key not in visible_keys:
        return JsonResponse({"ok": False, "error": "Benachrichtigung wurde nicht gefunden."}, status=404)

    NotificationDismissal.objects.get_or_create(user=request.user, key=key)
    invalidate_notification_cache(request.user)
    return JsonResponse(_center_payload(request.user))


@login_required
@never_cache
@require_POST
def notification_dismiss_all_api(request):
    keys = [item.get("key") for item in get_notification_items(request.user, limit=1000) if item.get("key")]

    NotificationDismissal.objects.bulk_create(
        [NotificationDismissal(user=request.user, key=key) for key in keys],
        ignore_conflicts=True,
    )
    invalidate_notification_cache(request.user)
    return JsonResponse(_center_payload(request.user))


@login_required
@never_cache
@require_GET
def push_config_api(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    active_count = WebPushSubscription.objects.filter(user=request.user, is_active=True).count()
    return JsonResponse({
        "ok": True,
        "enabled": web_push_is_configured(),
        "public_key": getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", ""),
        "browser_notifications": bool(profile.browser_notifications),
        "active_subscriptions": active_count,
    })


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


@login_required
@never_cache
@require_POST
def push_subscribe_api(request):
    if not web_push_is_configured():
        return JsonResponse({"ok": False, "error": "Web-Push ist noch nicht konfiguriert."}, status=503)

    data = _json_body(request)
    endpoint = str(data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"ok": False, "error": "Ungültiges Push-Abo."}, status=400)

    subscription, _created = WebPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:255],
            "is_active": True,
        },
    )

    profile, _profile_created = UserProfile.objects.get_or_create(user=request.user)
    if not profile.browser_notifications:
        profile.browser_notifications = True
        profile.save(update_fields=["browser_notifications", "updated_at"])

    return JsonResponse({
        "ok": True,
        "active_subscriptions": WebPushSubscription.objects.filter(user=request.user, is_active=True).count(),
        "subscription_id": subscription.pk,
    })


@login_required
@never_cache
@require_POST
def push_unsubscribe_api(request):
    data = _json_body(request)
    endpoint = str(data.get("endpoint") or "").strip()
    subscriptions = WebPushSubscription.objects.filter(user=request.user, is_active=True)
    if endpoint:
        subscriptions = subscriptions.filter(endpoint=endpoint)
    updated = subscriptions.update(is_active=False)
    return JsonResponse({"ok": True, "disabled": updated})


@login_required
@never_cache
@require_POST
def push_test_api(request):
    result = send_web_push_to_user(
        request.user,
        title="MyTools Push-Test",
        body="Web-Push funktioniert. Du bekommst Benachrichtigungen jetzt auch über die PWA.",
        url="/",
        tag="mytools-push-test",
    )
    status = 200 if result.get("configured") else 503
    return JsonResponse({"ok": bool(result.get("configured")), **result}, status=status)
