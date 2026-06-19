import json
import logging

from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import UserProfile, WebPushSubscription

logger = logging.getLogger(__name__)

INVALID_SUBSCRIPTION_STATUS_CODES = {404, 410}


def web_push_is_configured():
    return bool(
        getattr(settings, "WEB_PUSH_ENABLED", False)
        and getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "")
        and getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY", "")
    )


def default_push_icon_url():
    return getattr(settings, "STATIC_URL", "/static/") + "app/icons/pwa-icon-192.png"


def default_push_badge_url():
    return getattr(settings, "STATIC_URL", "/static/") + "app/icons/pwa-icon-180.png"


def normalize_push_url(url):
    url = str(url or "").strip()
    if not url:
        return reverse("home")
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return url
    return reverse("home")


def build_push_payload(*, title=None, body=None, url=None, tag=None, icon=None, badge=None):
    return {
        "title": str(title or _("MyTools"))[:120],
        "body": str(body or _("Du hast eine neue Benachrichtigung."))[:240],
        "url": normalize_push_url(url),
        "tag": str(tag or "mytools-notification")[:160],
        "icon": icon or default_push_icon_url(),
        "badge": badge or default_push_badge_url(),
    }


def deactivate_subscription(subscription, reason=""):
    if not subscription.is_active:
        return
    subscription.is_active = False
    subscription.save(update_fields=["is_active", "updated_at"])
    if reason:
        logger.info("Web-Push-Abo deaktiviert: %s", reason)


def send_web_push_subscription(subscription, payload):
    if not web_push_is_configured() or not subscription.is_active:
        return False

    try:
        from pywebpush import WebPushException, webpush
    except Exception as exc:  # pragma: no cover - dependency/runtime guard
        logger.exception(exc)
        return False

    try:
        webpush(
            subscription_info=subscription.subscription_info,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY,
            vapid_claims=settings.WEB_PUSH_VAPID_CLAIMS,
        )
        return True
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in INVALID_SUBSCRIPTION_STATUS_CODES:
            deactivate_subscription(subscription, f"HTTP {status_code}")
        else:
            logger.exception(exc)
        return False
    except Exception as exc:  # pragma: no cover - network/provider errors
        logger.exception(exc)
        return False


def send_web_push_to_user(user, *, title=None, body=None, url=None, tag=None, icon=None, badge=None):
    if not getattr(user, "is_authenticated", False) or not web_push_is_configured():
        return {"sent": 0, "total": 0, "configured": web_push_is_configured()}

    profile, _created = UserProfile.objects.get_or_create(user=user)
    muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications
    if not profile.browser_notifications or muted_by_dnd:
        return {"sent": 0, "total": 0, "configured": True}

    payload = build_push_payload(title=title, body=body, url=url, tag=tag, icon=icon, badge=badge)
    subscriptions = WebPushSubscription.objects.filter(user=user, is_active=True)
    total = subscriptions.count()
    sent = 0

    for subscription in subscriptions:
        if send_web_push_subscription(subscription, payload):
            sent += 1

    return {"sent": sent, "total": total, "configured": True}
