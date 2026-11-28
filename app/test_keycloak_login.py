from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django_recaptcha.client import RecaptchaResponse

from .adapters import KEYCLOAK_SESSION_KEY, MyToolsSocialAccountAdapter
from .models import SiteAccessSettings, UserTwoFactorSettings

ISSUER = "https://auth.example.test/realms/yfserver"
KEYCLOAK_SETTINGS = {
    "OIDC_ISSUER": ISSUER,
    "OIDC_CLIENT_ID": "mytools",
    "OIDC_CLIENT_SECRET": "client-secret",
    "OIDC_REQUIRED_GROUP": "",
    "KEYCLOAK_LOGIN_ENABLED": True,
    "SOCIALACCOUNT_PROVIDERS": {
        "openid_connect": {
            "OAUTH_PKCE_ENABLED": True,
            "APPS": [
                {
                    "provider_id": "keycloak",
                    "name": "yfserver",
                    "client_id": "mytools",
                    "secret": "client-secret",
                    "settings": {"server_url": ISSUER},
                }
            ],
        }
    },
}
OPENID_CONFIGURATION = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
    "userinfo_endpoint": f"{ISSUER}/protocol/openid-connect/userinfo",
    "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
}


@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakLoginTests(TestCase):
    def setUp(self):
        self.adapter = MyToolsSocialAccountAdapter()
        self.user = get_user_model().objects.create_user("ada", "ada@example.com", "pw")

    def request(self):
        request = RequestFactory().get("/accounts/oidc/keycloak/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request

    def sociallogin(self, user=None, **userinfo):
        account = SocialAccount(provider="keycloak", uid="kc-user-1", extra_data={"userinfo": userinfo})
        return SocialLogin(user=user or self.user, account=account)

    def test_login_page_offers_keycloak(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("openid_connect_login", args=["keycloak"]))

    @override_settings(KEYCLOAK_LOGIN_ENABLED=False)
    def test_login_page_hides_keycloak_when_not_configured(self):
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, reverse("openid_connect_login", args=["keycloak"]))

    def test_login_starts_code_flow_with_pkce(self):
        config_response = MagicMock(json=MagicMock(return_value=OPENID_CONFIGURATION))
        with patch("requests.Session.get", return_value=config_response):
            response = self.client.post(
                reverse("openid_connect_login", args=["keycloak"]), {"process": "login"}
            )
        location = urlsplit(response["Location"])
        query = parse_qs(location.query)
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            OPENID_CONFIGURATION["authorization_endpoint"],
        )
        self.assertEqual(query["client_id"], ["mytools"])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_admin_group_grants_and_removes_admin_rights(self):
        self.adapter.pre_social_login(self.request(), self.sociallogin(groups=["admins"]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff and self.user.is_superuser)
        self.adapter.pre_social_login(self.request(), self.sociallogin(groups=[]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff or self.user.is_superuser)

    def test_admin_rights_stay_when_no_groups_are_sent(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.adapter.pre_social_login(self.request(), self.sociallogin())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)

    def test_new_user_gets_admin_rights_before_saving(self):
        new_user = get_user_model()(username="new", email="new@example.com")
        self.adapter.pre_social_login(self.request(), self.sociallogin(new_user, groups=["admins"]))
        self.assertTrue(new_user.is_staff and new_user.is_superuser)
        self.assertIsNone(new_user.pk)

    @override_settings(OIDC_REQUIRED_GROUP="dev-access")
    def test_required_group_is_enforced(self):
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request(), self.sociallogin(groups=["admins"]))
        self.adapter.pre_social_login(self.request(), self.sociallogin(groups=["dev-access"]))

    def test_keycloak_login_skips_mytools_two_factor_and_marks_session(self):
        UserTwoFactorSettings.objects.create(user=self.user, secret_key="x", is_enabled=True)
        request = self.request()
        self.adapter.pre_social_login(request, self.sociallogin())
        self.assertTrue(request.session[KEYCLOAK_SESSION_KEY])

    def test_site_lock_still_applies_to_normal_users(self):
        settings_obj = SiteAccessSettings.get_solo()
        settings_obj.login_registration_locked = True
        settings_obj.save()
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request(), self.sociallogin(groups=[]))
        self.adapter.pre_social_login(self.request(), self.sociallogin(groups=["admins"]))

    def test_logout_after_keycloak_login_ends_keycloak_session(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[KEYCLOAK_SESSION_KEY] = True
        session.save()
        response = self.client.post(reverse("logout"))
        location = urlsplit(response["Location"])
        query = parse_qs(location.query)
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            f"{ISSUER}/protocol/openid-connect/logout",
        )
        self.assertEqual(query["client_id"], ["mytools"])
        self.assertEqual(query["post_logout_redirect_uri"], ["http://testserver/accounts/login/"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_logout_is_unchanged(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)


@override_settings(**KEYCLOAK_SETTINGS, OIDC_ONLY=True)
@patch("django_recaptcha.fields.client.submit", return_value=RecaptchaResponse(is_valid=True))
class OIDCOnlyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user("ada", "ada@example.com", "pw-123456789")
        self.admin = user_model.objects.create_user("root", "root@example.com", "pw-123456789", is_staff=True)

    def password_login(self, username):
        return self.client.post(
            reverse("login"),
            {"username": username, "password": "pw-123456789", "g-recaptcha-response": "PASSED"},
        )

    def test_login_page_offers_password_only_as_break_glass(self, _submit):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'class="auth-break-glass"')
        self.assertNotContains(response, reverse("signup"))
        self.assertNotContains(response, reverse("password_reset"))

    def test_password_login_is_left_to_staff(self, _submit):
        response = self.password_login("ada")
        codes = [error.code for error in response.context["form"].non_field_errors().as_data()]
        self.assertEqual(codes, ["oidc_only"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.password_login("root")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)

    def test_signups_lead_to_login_or_are_closed(self, _submit):
        self.assertRedirects(self.client.get(reverse("signup")), reverse("login"), fetch_redirect_response=False)
        response = self.client.get(reverse("account_signup"))
        self.assertTemplateUsed(response, "account/signup_closed.html")

    def test_keycloak_signup_stays_open(self, _submit):
        request = RequestFactory().get("/")
        account = SocialAccount(provider="keycloak", uid="kc-new")
        self.assertTrue(MyToolsSocialAccountAdapter().is_open_for_signup(request, SocialLogin(account=account)))
