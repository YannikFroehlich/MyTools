from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

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


class PermissionsPolicyMiddleware:
    """Allow browser APIs the app intentionally uses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        return response
