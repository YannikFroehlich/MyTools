from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .access_control import access_key_for_url_name, user_can_access_key
from .presence_utils import touch_user_presence


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
            settings.MEDIA_URL,
        )
        return (
            any(path.startswith(prefix) for prefix in exempt_prefixes if prefix)
            or (path.startswith(file_share_download_prefix) and path.endswith(file_share_download_suffix))
        )

    def _is_suspension_exempt(self, path):
        return path.startswith("/accounts/logout/") or path.startswith("/admin/")

    def _tool_access_forbidden(self, request):
        message = "Dieses Tool oder Spiel ist aktuell nicht fuer deinen Account freigegeben."
        wants_json = (
            request.path.startswith("/api/")
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
        )
        if wants_json:
            return JsonResponse({"status": "error", "message": message}, status=403)

        return HttpResponseForbidden(
            (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>Zugriff gesperrt</title></head><body>"
                "<main style='font-family:system-ui;margin:10vh auto;max-width:640px;padding:24px'>"
                "<h1>Zugriff gesperrt</h1>"
                f"<p>{message}</p>"
                "<p>Wenn du glaubst, dass das ein Fehler ist, frag einen Admin nach Zugriff.</p>"
                "</main></body></html>"
            )
        )


class PermissionsPolicyMiddleware:
    """Allow browser APIs the app intentionally uses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        return response
