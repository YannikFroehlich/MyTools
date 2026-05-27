from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # App-Routen
    path("", include("app.urls")),

    # Django Sprachwechsel
    path("i18n/", include("django.conf.urls.i18n")),

    # Login / Logout
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="app/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # Passwort zurücksetzen
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="app/password_reset.html",
            email_template_name="app/password_reset_email.html",
            subject_template_name="app/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="app/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="app/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="app/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]


# Profilbilder / Uploads im lokalen DEBUG-Modus ausliefern
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)