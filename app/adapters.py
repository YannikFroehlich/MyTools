from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import SiteAccessSettings, UserTwoFactorSettings
from .two_factor import begin_pending_two_factor_login

KEYCLOAK_PROVIDER_ID = "keycloak"
KEYCLOAK_ADMIN_GROUP = "admins"
# Set when the session was opened through Keycloak, so logout can end the Keycloak session too.
KEYCLOAK_SESSION_KEY = "keycloak_login"


def keycloak_claims(sociallogin):
    """The user info (or ID token) claims allauth stored for a Keycloak login."""
    extra_data = getattr(sociallogin.account, "extra_data", None) or {}
    return extra_data.get("userinfo") or extra_data.get("id_token") or {}


class MyToolsSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        if SiteAccessSettings.is_locked():
            return False
        return super().is_open_for_signup(request, sociallogin)

    def pre_social_login(self, request, sociallogin):
        is_keycloak = sociallogin.account.provider == KEYCLOAK_PROVIDER_ID
        user = self._resolve_user(sociallogin)
        if is_keycloak:
            user = self._apply_keycloak_groups(request, sociallogin, user)

        if SiteAccessSettings.is_locked():
            if not (user and user.is_staff):
                messages.error(request, _("Der Login ist aktuell fuer normale Nutzer gesperrt."))
                raise ImmediateHttpResponse(redirect("login"))

        # Keycloak already asked for its own second factor.
        if not is_keycloak and user and UserTwoFactorSettings.enabled_for_user(user):
            begin_pending_two_factor_login(
                request,
                user,
                backend="allauth.account.auth_backends.AuthenticationBackend",
            )
            raise ImmediateHttpResponse(redirect("two_factor_verify"))

        if is_keycloak:
            request.session[KEYCLOAK_SESSION_KEY] = True
        return super().pre_social_login(request, sociallogin)

    def _apply_keycloak_groups(self, request, sociallogin, user):
        groups = keycloak_claims(sociallogin).get("groups")
        required_group = settings.OIDC_REQUIRED_GROUP
        if required_group and required_group not in (groups or []):
            messages.error(request, _("Dein Konto hat keinen Zugriff auf diese MyTools-Instanz."))
            raise ImmediateHttpResponse(redirect("login"))
        # Keycloak is the source of truth for admin rights, but only when it sends groups.
        if groups is None:
            return user
        target = user or sociallogin.user
        is_admin = KEYCLOAK_ADMIN_GROUP in groups
        if target.is_staff != is_admin or target.is_superuser != is_admin:
            target.is_staff = target.is_superuser = is_admin
            if target.pk:
                target.save(update_fields=["is_staff", "is_superuser"])
        return target

    def _resolve_user(self, sociallogin):
        user = getattr(sociallogin, "user", None)
        if getattr(user, "pk", None):
            return user

        account = getattr(sociallogin, "account", None)
        account_user = getattr(account, "user", None)
        if getattr(account_user, "pk", None):
            return account_user

        email = (getattr(user, "email", "") or "").strip()
        if not email:
            return None

        UserModel = get_user_model()
        return UserModel.objects.filter(email__iexact=email).first()
