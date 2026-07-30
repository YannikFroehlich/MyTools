from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.urls import reverse


PENDING_USER_SESSION_KEY = "two_factor_user_id"
PENDING_BACKEND_SESSION_KEY = "two_factor_backend"
PENDING_NEXT_SESSION_KEY = "two_factor_next"
PENDING_ATTEMPTS_SESSION_KEY = "two_factor_attempts"
VERIFIED_USER_SESSION_KEY = "two_factor_verified_user_id"
PENDING_LOGIN_SECONDS = 5 * 60
MAX_PENDING_ATTEMPTS = 5


def begin_pending_two_factor_login(request, user, *, backend=None, next_url=None):
    backend = backend or getattr(user, "backend", None)
    if not backend:
        backend = request.session.get(BACKEND_SESSION_KEY)
    if not backend:
        backend = settings.AUTHENTICATION_BACKENDS[0]

    request.session[PENDING_USER_SESSION_KEY] = user.pk
    request.session[PENDING_BACKEND_SESSION_KEY] = backend
    request.session[PENDING_NEXT_SESSION_KEY] = next_url or reverse("home")
    request.session[PENDING_ATTEMPTS_SESSION_KEY] = 0
    request.session.pop(VERIFIED_USER_SESSION_KEY, None)
    request.session.set_expiry(PENDING_LOGIN_SECONDS)


def clear_pending_two_factor_login(request):
    for key in (
        PENDING_USER_SESSION_KEY,
        PENDING_BACKEND_SESSION_KEY,
        PENDING_NEXT_SESSION_KEY,
        PENDING_ATTEMPTS_SESSION_KEY,
    ):
        request.session.pop(key, None)


def mark_two_factor_verified(request, user):
    request.session[VERIFIED_USER_SESSION_KEY] = user.pk


def is_two_factor_verified(request, user):
    return str(request.session.get(VERIFIED_USER_SESSION_KEY, "")) == str(user.pk)
