from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .presence_utils import touch_user_presence


class LoginRequiredMiddleware:
    """Require a logged-in user for the app while keeping auth/static/i18n endpoints open."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_exempt(request.path):
            response = self.get_response(request)
            if request.user.is_authenticated:
                touch_user_presence(request.user)
            return response

        login_url = reverse(settings.LOGIN_URL)
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")

    def _is_exempt(self, path):
        exempt_prefixes = (
            "/accounts/",
            reverse("signup"),
            "/i18n/",
            "/admin/",
            "/media-thumb/",
            settings.STATIC_URL,
            settings.MEDIA_URL,
        )
        return any(path.startswith(prefix) for prefix in exempt_prefixes if prefix)


class PermissionsPolicyMiddleware:
    """Allow browser APIs the app intentionally uses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        return response
