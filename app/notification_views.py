from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .notification_utils import get_notification_counts, get_notification_items


def _serialize_item(item):
    created_at = item.get("created_at")
    return {
        "type": item.get("type", "info"),
        "icon": item.get("icon", "fa-solid fa-bell"),
        "title": str(item.get("title", "")),
        "text": str(item.get("text", "")),
        "url": item.get("url", "#"),
        "badge": item.get("badge", 1),
        "created_at": created_at.isoformat() if created_at else "",
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
    profile = getattr(request.user, "profile", None)
    return JsonResponse({
        "ok": True,
        "counts": get_notification_counts(request.user),
        "items": [_serialize_item(item) for item in get_notification_items(request.user, limit=12)],
        "settings": {
            "browser_notifications": bool(getattr(profile, "browser_notifications", False)),
            "sound_notifications": bool(getattr(profile, "sound_notifications", False)),
        },
    })
