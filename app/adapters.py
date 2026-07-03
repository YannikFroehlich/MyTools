from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import SiteAccessSettings


class MyToolsSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        if SiteAccessSettings.is_locked():
            return False
        return super().is_open_for_signup(request, sociallogin)

    def pre_social_login(self, request, sociallogin):
        if SiteAccessSettings.is_locked():
            user = self._resolve_user(sociallogin)
            if not (user and user.is_staff):
                messages.error(request, _("Der Login ist aktuell fuer normale Nutzer gesperrt."))
                raise ImmediateHttpResponse(redirect("login"))

        return super().pre_social_login(request, sociallogin)

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
