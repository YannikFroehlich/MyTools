from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import NotificationDismissal
from .notification_utils import get_notification_counts, get_notification_items


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


def _center_payload(user):
    profile = getattr(user, "profile", None)
    return {
        "ok": True,
        "counts": get_notification_counts(user),
        "items": [_serialize_item(item) for item in get_notification_items(user, limit=12)],
        "settings": {
            "browser_notifications": bool(getattr(profile, "browser_notifications", False)),
            "sound_notifications": bool(getattr(profile, "sound_notifications", False)),
        },
    }


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
@require_POST
def notification_dismiss_api(request):
    key = (request.POST.get("key") or "").strip()
    visible_keys = {item.get("key") for item in get_notification_items(request.user, limit=1000)}

    if not key or key not in visible_keys:
        return JsonResponse({"ok": False, "error": "Benachrichtigung wurde nicht gefunden."}, status=404)

    NotificationDismissal.objects.get_or_create(user=request.user, key=key)
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
    return JsonResponse(_center_payload(request.user))
