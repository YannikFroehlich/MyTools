from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    """Require a logged-in user for the app while keeping auth/static endpoints open."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_exempt(request.path):
            return self.get_response(request)

        login_url = reverse(settings.LOGIN_URL)
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")

    def _is_exempt(self, path):
        exempt_prefixes = (
            "/accounts/",
            reverse("signup"),
            "/admin/",
            settings.STATIC_URL,
            settings.MEDIA_URL,
        )
        return any(path.startswith(prefix) for prefix in exempt_prefixes if prefix)
