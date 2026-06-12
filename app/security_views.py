import base64
import re
from io import BytesIO

from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .models import SecurityEvent, UserTwoFactorSettings


HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
QR_TYPES = {"text", "url", "wifi", "contact"}
QR_ERROR_LEVELS = {"L", "M", "Q", "H"}
QR_ENCRYPTION_TYPES = {"WPA", "WEP", "nopass"}


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def create_security_event(request, user, event_type, severity=SecurityEvent.SEVERITY_INFO, note="", session_key=""):
    if not user:
        return None
    return SecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        severity=severity,
        ip_address=get_client_ip(request) or None,
        user_agent=get_user_agent(request),
        session_key=(session_key or getattr(request.session, "session_key", "") or "")[:64],
        note=str(note or "")[:255],
    )


def _session_belongs_to_user(session, user):
    try:
        data = session.get_decoded()
    except Exception:
        return False
    return str(data.get("_auth_user_id")) == str(user.pk)


def _active_sessions_for_user(user, current_session_key):
    sessions = []
    event_map = {
        event.session_key: event
        for event in SecurityEvent.objects.filter(
            user=user,
            event_type=SecurityEvent.EVENT_LOGIN_SUCCESS,
            session_key__gt="",
        ).order_by("-created_at")[:100]
    }

    for session in Session.objects.filter(expire_date__gte=timezone.now()).order_by("-expire_date"):
        if not _session_belongs_to_user(session, user):
            continue
        event = event_map.get(session.session_key)
        sessions.append({
            "key": session.session_key,
            "is_current": session.session_key == current_session_key,
            "expire_date": session.expire_date,
            "last_event": event,
            "ip_address": event.ip_address if event else "",
            "user_agent": event.user_agent if event else "",
        })
    return sessions


@login_required
@require_http_methods(["GET", "POST"])
def security_dashboard_view(request):
    current_session_key = request.session.session_key

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "revoke_session":
            session_key = (request.POST.get("session_key") or "").strip()
            if not session_key:
                messages.error(request, _("Es wurde keine Sitzung ausgewählt."), extra_tags="security")
                return redirect("security_dashboard")
            if session_key == current_session_key:
                messages.error(request, _("Die aktuelle Sitzung kann nicht hier beendet werden."), extra_tags="security")
                return redirect("security_dashboard")

            session = Session.objects.filter(session_key=session_key, expire_date__gte=timezone.now()).first()
            if session and _session_belongs_to_user(session, request.user):
                session.delete()
                create_security_event(
                    request,
                    request.user,
                    SecurityEvent.EVENT_SESSION_REVOKED,
                    SecurityEvent.SEVERITY_WARNING,
                    note=_("Eine andere Sitzung wurde beendet."),
                    session_key=session_key,
                )
                messages.success(request, _("Die ausgewählte Sitzung wurde beendet."), extra_tags="security")
            else:
                messages.error(request, _("Diese Sitzung konnte nicht gefunden werden."), extra_tags="security")
            return redirect("security_dashboard")

        if action == "revoke_other_sessions":
            deleted_count = 0
            for session in Session.objects.filter(expire_date__gte=timezone.now()):
                if session.session_key == current_session_key:
                    continue
                if _session_belongs_to_user(session, request.user):
                    session.delete()
                    deleted_count += 1

            create_security_event(
                request,
                request.user,
                SecurityEvent.EVENT_SESSIONS_REVOKED,
                SecurityEvent.SEVERITY_WARNING,
                note=_("%(count)s andere Sitzung(en) wurden beendet.") % {"count": deleted_count},
            )
            messages.success(
                request,
                _("%(count)s andere Sitzung(en) wurden beendet.") % {"count": deleted_count},
                extra_tags="security",
            )
            return redirect("security_dashboard")

    security_messages = [
        message for message in get_messages(request)
        if "security" in message.tags.split()
    ]

    two_factor_settings = UserTwoFactorSettings.objects.filter(user=request.user).first()
    two_factor_enabled = bool(two_factor_settings and two_factor_settings.is_enabled and two_factor_settings.secret_key)
    active_sessions = _active_sessions_for_user(request.user, current_session_key)
    events = SecurityEvent.objects.filter(user=request.user).order_by("-created_at")[:30]

    context = {
        "two_factor_settings": two_factor_settings,
        "two_factor_enabled": two_factor_enabled,
        "active_sessions": active_sessions,
        "current_session_key": current_session_key,
        "security_events": events,
        "security_messages": security_messages,
        "login_success_count": SecurityEvent.objects.filter(user=request.user, event_type=SecurityEvent.EVENT_LOGIN_SUCCESS).count(),
        "login_failed_count": SecurityEvent.objects.filter(user=request.user, event_type=SecurityEvent.EVENT_LOGIN_FAILED).count(),
    }
    return render(request, "app/security_dashboard.html", context)


def _clean_color(value, fallback):
    value = (value or "").strip()
    return value if HEX_COLOR_RE.match(value) else fallback


def _clean_int(value, fallback, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(number, maximum))


def _escape_wifi(value):
    return str(value or "").replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace(":", r"\:")


def _one_line(value, max_length=160):
    return " ".join(str(value or "").split())[:max_length]


def _build_qr_payload(post_data):
    qr_type = post_data.get("qr_type") if post_data.get("qr_type") in QR_TYPES else "text"

    if qr_type == "url":
        url = _one_line(post_data.get("url"), 2000)
        if not url:
            raise ValueError(_("Bitte gib eine URL ein."))
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = f"https://{url}"
        return qr_type, url

    if qr_type == "wifi":
        ssid = _one_line(post_data.get("wifi_ssid"), 80)
        password = str(post_data.get("wifi_password") or "")[:120]
        encryption = post_data.get("wifi_encryption") if post_data.get("wifi_encryption") in QR_ENCRYPTION_TYPES else "WPA"
        hidden = "true" if post_data.get("wifi_hidden") else "false"
        if not ssid:
            raise ValueError(_("Bitte gib den WLAN-Namen ein."))
        if encryption == "nopass":
            return qr_type, f"WIFI:T:nopass;S:{_escape_wifi(ssid)};H:{hidden};;"
        return qr_type, f"WIFI:T:{encryption};S:{_escape_wifi(ssid)};P:{_escape_wifi(password)};H:{hidden};;"

    if qr_type == "contact":
        name = _one_line(post_data.get("contact_name"), 120)
        phone = _one_line(post_data.get("contact_phone"), 80)
        email = _one_line(post_data.get("contact_email"), 120)
        organisation = _one_line(post_data.get("contact_org"), 120)
        website = _one_line(post_data.get("contact_url"), 200)
        if not any([name, phone, email, organisation, website]):
            raise ValueError(_("Bitte gib mindestens einen Kontaktdaten-Wert ein."))
        lines = ["BEGIN:VCARD", "VERSION:3.0"]
        if name:
            lines.append(f"FN:{name}")
        if organisation:
            lines.append(f"ORG:{organisation}")
        if phone:
            lines.append(f"TEL:{phone}")
        if email:
            lines.append(f"EMAIL:{email}")
        if website:
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", website):
                website = f"https://{website}"
            lines.append(f"URL:{website}")
        lines.append("END:VCARD")
        return qr_type, "\n".join(lines)

    text_value = str(post_data.get("text") or "").strip()[:2500]
    if not text_value:
        raise ValueError(_("Bitte gib einen Text ein."))
    return "text", text_value


def _generate_qr_data_uri(payload, foreground, background, error_level, box_size, border):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q

    error_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_map.get(error_level, ERROR_CORRECT_M),
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color=foreground, back_color=background).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}", image.size


@login_required
@require_http_methods(["GET", "POST"])
def qr_code_tool_view(request):
    form_data = {
        "qr_type": "text",
        "text": "",
        "url": "",
        "wifi_ssid": "",
        "wifi_password": "",
        "wifi_encryption": "WPA",
        "wifi_hidden": False,
        "contact_name": "",
        "contact_phone": "",
        "contact_email": "",
        "contact_org": "",
        "contact_url": "",
        "foreground": "#111827",
        "background": "#ffffff",
        "error_level": "M",
        "box_size": "10",
        "border": "4",
    }
    qr_data_uri = ""
    qr_payload = ""
    qr_size = None
    selected_type = "text"

    if request.method == "POST":
        for key in form_data:
            if key == "wifi_hidden":
                form_data[key] = bool(request.POST.get(key))
            else:
                form_data[key] = request.POST.get(key, form_data[key])
        form_data["foreground"] = _clean_color(form_data.get("foreground"), "#111827")
        form_data["background"] = _clean_color(form_data.get("background"), "#ffffff")
        form_data["error_level"] = form_data.get("error_level") if form_data.get("error_level") in QR_ERROR_LEVELS else "M"
        form_data["box_size"] = str(_clean_int(form_data.get("box_size"), 10, 4, 16))
        form_data["border"] = str(_clean_int(form_data.get("border"), 4, 1, 8))

        try:
            selected_type, qr_payload = _build_qr_payload(request.POST)
            form_data["qr_type"] = selected_type
            qr_data_uri, qr_size = _generate_qr_data_uri(
                qr_payload,
                form_data["foreground"],
                form_data["background"],
                form_data["error_level"],
                int(form_data["box_size"]),
                int(form_data["border"]),
            )
            messages.success(request, _("QR-Code wurde erstellt."))
        except Exception as exc:
            messages.error(request, str(exc) or _("QR-Code konnte nicht erstellt werden."))

    return render(request, "app/qr_code_tool.html", {
        "form_data": form_data,
        "selected_type": selected_type,
        "qr_data_uri": qr_data_uri,
        "qr_payload": qr_payload,
        "qr_size": qr_size,
        "qr_download_name": "mytools-qr-code.png",
    })
