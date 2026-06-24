"""
URL configuration for MyTools project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include, re_path
from django.urls import reverse_lazy
from django.views.i18n import set_language
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as media_serve
from django.contrib.staticfiles.views import serve as staticfiles_serve
from app.views.media import media_thumbnail
from app.views.auth import AccessAwareLoginView

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        'accounts/password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='app/auth/password_reset_form.html',
            email_template_name='app/auth/password_reset_email.html',
            subject_template_name='app/auth/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'accounts/password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='app/auth/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'accounts/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='app/auth/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='app/auth/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    path('accounts/login/', AccessAwareLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('app.urls')),
    path('i18n/setlang/', set_language, name='set_language'),
    path('media-thumb/<str:spec>/<path:source>', media_thumbnail, name='media_thumbnail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.RUNSERVER_SERVE_STATIC and not settings.DEBUG:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", staticfiles_serve, {"insecure": True}),
        re_path(r"^media/(?P<path>.*)$", media_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
