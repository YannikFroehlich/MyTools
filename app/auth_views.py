import base64
from io import BytesIO

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

from .models import SecurityEvent, SiteAccessSettings, UserTwoFactorSettings
from .security_views import create_security_event
from .totp_utils import generate_totp_secret, provisioning_uri, verify_totp


class AccessLockedAuthenticationForm(AuthenticationForm):
    captcha = ReCaptchaField(
        label="",
        error_messages={
            "required": _("Bitte bestätige, dass du kein Roboter bist."),
        },
        widget=ReCaptchaV2Checkbox(
            attrs={
                "data-size": "normal",
            }
        ),
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "placeholder": _("Benutzername"),
        })
        self.fields["password"].widget.attrs.update({
            "autocomplete": "current-password",
            "placeholder": _("Passwort"),
        })

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        settings_obj = SiteAccessSettings.get_solo()
        if settings_obj.login_registration_locked and not user.is_staff:
            raise forms.ValidationError(
                _("Der Login ist aktuell für normale Nutzer gesperrt."),
                code="login_locked",
            )


class TwoFactorTokenForm(forms.Form):
    token = forms.CharField(
        label=_("Authentifizierungs-Code"),
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "placeholder": "123456",
        }),
    )

    def clean_token(self):
        token = "".join(ch for ch in self.cleaned_data["token"] if ch.isdigit())
        if len(token) != 6:
            raise forms.ValidationError(_("Bitte gib einen 6-stelligen Code ein."))
        return token


class AccessAwareLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = AccessLockedAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings_obj = SiteAccessSettings.get_solo()
        context["access_settings"] = settings_obj
        context["access_locked"] = settings_obj.login_registration_locked
        return context

    def form_valid(self, form):
        user = form.get_user()
        if SiteAccessSettings.is_locked() and not user.is_staff:
            messages.error(self.request, _("Der Login ist aktuell für normale Nutzer gesperrt."))
            return self.form_invalid(form)

        two_factor_settings = UserTwoFactorSettings.enabled_for_user(user)
        if two_factor_settings:
            self.request.session["two_factor_user_id"] = user.pk
            self.request.session["two_factor_backend"] = user.backend
            self.request.session["two_factor_next"] = self.get_success_url()
            self.request.session.set_expiry(300)
            return redirect("two_factor_verify")

        response = super().form_valid(form)
        create_security_event(
            self.request,
            user,
            SecurityEvent.EVENT_LOGIN_SUCCESS,
            SecurityEvent.SEVERITY_SUCCESS,
            note=_("Login ohne 2FA abgeschlossen."),
        )
        return response

    def form_invalid(self, form):
        username = (self.request.POST.get("username") or "").strip()
        if username:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(username__iexact=username).first()
            if user:
                create_security_event(
                    self.request,
                    user,
                    SecurityEvent.EVENT_LOGIN_FAILED,
                    SecurityEvent.SEVERITY_DANGER,
                    note=_("Login-Versuch wurde abgelehnt."),
                )
        return super().form_invalid(form)


@require_http_methods(["GET", "POST"])
def two_factor_verify_view(request):
    user_id = request.session.get("two_factor_user_id")
    if not user_id:
        return redirect("login")

    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    two_factor_settings = UserTwoFactorSettings.enabled_for_user(user)
    if not user or not two_factor_settings:
        request.session.pop("two_factor_user_id", None)
        request.session.pop("two_factor_backend", None)
        request.session.pop("two_factor_next", None)
        return redirect("login")

    form = TwoFactorTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_totp(two_factor_settings.secret_key, form.cleaned_data["token"]):
            backend = request.session.get("two_factor_backend")
            next_url = request.session.get("two_factor_next") or reverse("home")
            request.session.flush()
            auth_login(request, user, backend=backend)
            create_security_event(
                request,
                user,
                SecurityEvent.EVENT_LOGIN_SUCCESS,
                SecurityEvent.SEVERITY_SUCCESS,
                note=_("Login mit 2FA bestätigt."),
            )
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = reverse("home")
            return HttpResponseRedirect(next_url)
        form.add_error("token", _("Der Code ist ungültig oder abgelaufen."))

    return render(request, "registration/two_factor_verify.html", {"form": form})


def _qr_code_data_uri(uri):
    try:
        import qrcode
    except ImportError:
        return ""

    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_settings_view(request):
    settings_obj, created = UserTwoFactorSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start_setup":
            settings_obj.secret_key = generate_totp_secret()
            settings_obj.is_enabled = False
            settings_obj.confirmed_at = None
            settings_obj.save(update_fields=["secret_key", "is_enabled", "confirmed_at", "updated_at"])
            messages.info(request, _("Scanne den QR-Code und bestätige die Einrichtung mit einem 6-stelligen Code."))
            return redirect("two_factor_settings")

        if action == "confirm_setup":
            form = TwoFactorTokenForm(request.POST)
            if form.is_valid() and verify_totp(settings_obj.secret_key, form.cleaned_data["token"]):
                settings_obj.is_enabled = True
                settings_obj.confirmed_at = timezone.now()
                settings_obj.save(update_fields=["is_enabled", "confirmed_at", "updated_at"])
                create_security_event(
                    request,
                    request.user,
                    SecurityEvent.EVENT_TWO_FACTOR_ENABLED,
                    SecurityEvent.SEVERITY_SUCCESS,
                    note=_("2FA wurde für den Account aktiviert."),
                )
                messages.success(request, _("Zwei-Faktor-Authentifizierung wurde aktiviert."))
                return redirect("two_factor_settings")
            messages.error(request, _("Der Code konnte nicht bestätigt werden."))

        if action == "disable":
            form = TwoFactorTokenForm(request.POST)
            if settings_obj.is_enabled and form.is_valid() and verify_totp(settings_obj.secret_key, form.cleaned_data["token"]):
                settings_obj.is_enabled = False
                settings_obj.secret_key = ""
                settings_obj.confirmed_at = None
                settings_obj.save(update_fields=["is_enabled", "secret_key", "confirmed_at", "updated_at"])
                create_security_event(
                    request,
                    request.user,
                    SecurityEvent.EVENT_TWO_FACTOR_DISABLED,
                    SecurityEvent.SEVERITY_WARNING,
                    note=_("2FA wurde für den Account deaktiviert."),
                )
                messages.success(request, _("Zwei-Faktor-Authentifizierung wurde deaktiviert."))
                return redirect("two_factor_settings")
            messages.error(request, _("Der Code ist ungültig. 2FA wurde nicht deaktiviert."))

    uri = provisioning_uri(settings_obj.secret_key, request.user.username) if settings_obj.secret_key else ""
    return render(request, "app/two_factor_settings.html", {
        "two_factor_settings": settings_obj,
        "setup_form": TwoFactorTokenForm(),
        "disable_form": TwoFactorTokenForm(),
        "provisioning_uri": uri,
        "qr_code_data_uri": _qr_code_data_uri(uri) if uri and not settings_obj.is_enabled else "",
    })
