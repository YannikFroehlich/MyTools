from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.translation import gettext as _

from .access_control import access_key_for_url_name, user_can_access_key
from .presence_utils import touch_user_presence
from .rate_limits import check_rate_limit, rule_for_request


class RateLimitMiddleware:
    """Apply small cache-backed limits to high-risk write/API endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = getattr(request, "resolver_match", None)
        url_name = getattr(match, "url_name", None)
        rule = rule_for_request(url_name, request.method)
        if not rule:
            return None

        result = check_rate_limit(request, rule)
        if result.allowed:
            return None

        return self._rate_limited_response(request, result.retry_after)

    def _rate_limited_response(self, request, retry_after):
        message = _("Zu viele Anfragen. Bitte warte kurz und versuche es erneut.")
        wants_json = (
            request.path.startswith("/api/")
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
        )
        if wants_json:
            response = JsonResponse({"ok": False, "error": message, "retry_after": retry_after}, status=429)
        else:
            messages.error(request, message)
            response = redirect(request.META.get("HTTP_REFERER") or request.path or reverse(settings.LOGIN_URL))

        response["Retry-After"] = str(retry_after)
        return response


class LoginRequiredMiddleware:
    """Require a logged-in user for the app while keeping auth/static/i18n endpoints open."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_exempt(request.path):
            if request.user.is_authenticated and not self._is_suspension_exempt(request.path):
                from .models import UserSuspension

                suspension = UserSuspension.active_for_user(request.user)
                if suspension and not request.user.is_staff:
                    return HttpResponseForbidden(
                        (
                            "<!doctype html><html><head><meta charset='utf-8'>"
                            "<title>Account gesperrt</title></head><body>"
                            "<main style='font-family:system-ui;margin:10vh auto;max-width:640px;padding:24px'>"
                            "<h1>Account gesperrt</h1>"
                            f"<p>Dein Account ist bis {suspension.ends_at:%d.%m.%Y %H:%M} gesperrt.</p>"
                            f"<p>{suspension.reason or 'Kein Grund angegeben.'}</p>"
                            "<p>Du kannst dich ueber das Browser-Menue oder nach Ablauf der Sperre erneut anmelden.</p>"
                            "</main></body></html>"
                        )
                    )
            response = self.get_response(request)
            if request.user.is_authenticated:
                touch_user_presence(request.user)
            return response

        login_url = reverse(settings.LOGIN_URL)
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or request.path.startswith("/admin/"):
            return None

        try:
            match = request.resolver_match or resolve(request.path_info)
        except Resolver404:
            return None

        access_key = access_key_for_url_name(match.url_name)
        if not access_key or user_can_access_key(request.user, access_key):
            return None

        return self._tool_access_forbidden(request)

    def _is_exempt(self, path):
        file_share_download_pattern = reverse("file_share_download", args=["__token__"])
        file_share_download_prefix, file_share_download_suffix = file_share_download_pattern.split("__token__")
        public_media_prefixes = tuple(
            f"{settings.MEDIA_URL}{prefix}"
            for prefix in ("public/", "profile_pictures/", "profile_banners/", "shortcut_icons/", "avatar_characters/")
        )
        exempt_prefixes = (
            "/accounts/",
            reverse("signup"),
            "/i18n/",
            "/admin/",
            "/media-thumb/",
            "/manifest.webmanifest",
            "/service-worker.js",
            "/offline/",
            settings.STATIC_URL,
            *public_media_prefixes,
        )
        return (
            any(path.startswith(prefix) for prefix in exempt_prefixes if prefix)
            or (path.startswith(file_share_download_prefix) and path.endswith(file_share_download_suffix))
        )

    def _is_suspension_exempt(self, path):
        return path.startswith("/accounts/logout/") or path.startswith("/admin/")

    def _tool_access_forbidden(self, request):
        message = "Dieses Tool oder Spiel ist aktuell nicht für deinen Account freigegeben."
        wants_json = (
            request.path.startswith("/api/")
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
        )
        if wants_json:
            return JsonResponse({"status": "error", "message": message}, status=403)

        messages.error(request, message)
        return redirect("favorites")


class PermissionsPolicyMiddleware:
    """Allow browser APIs the app intentionally uses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        return response


class ContentSecurityPolicyMiddleware:
    """Send the configured CSP header, defaulting to report-only rollout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CSP_POLICY", "")
        if not policy:
            return response

        header_name = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", True)
            else "Content-Security-Policy"
        )
        if header_name not in response:
            response[header_name] = policy
        return response
