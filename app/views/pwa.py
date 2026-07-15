import json

from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _, pgettext


PWA_THEME_COLOR = "#1a56d6"
PWA_BACKGROUND_COLOR = "#dce5f5"
PWA_CACHE_VERSION = "mytools-pwa-v18"


def _manifest_language():
    current_language = translation.get_language() or "de"
    return "en-US" if current_language.startswith("en") else "de-DE"


def pwa_manifest_view(request):
    """Return the installable web app manifest for MyTools."""
    manifest = {
        "name": "MyTools",
        "short_name": "MyTools",
        "description": _("Private Tools, Widgets und Spiele in einer installierbaren Web-App."),
        "id": reverse("home"),
        "start_url": reverse("home"),
        "scope": "/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone", "minimal-ui", "browser"],
        "orientation": "portrait-primary",
        "theme_color": PWA_THEME_COLOR,
        "background_color": PWA_BACKGROUND_COLOR,
        "categories": ["productivity", "utilities", "games"],
        "lang": _manifest_language(),
        "icons": [
            {
                "src": static("app/icons/pwa-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("app/icons/pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("app/icons/pwa-maskable-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": static("app/icons/pwa-maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {
                "name": pgettext("PWA manifest shortcut", "Startseite"),
                "short_name": pgettext("PWA manifest shortcut", "Start"),
                "description": pgettext("PWA manifest shortcut", "Dashboard öffnen"),
                "url": reverse("home"),
                "icons": [{"src": static("app/icons/pwa-icon-192.png"), "sizes": "192x192"}],
            },
            {
                "name": pgettext("PWA manifest shortcut", "Notizen"),
                "short_name": pgettext("PWA manifest shortcut", "Notizen"),
                "description": pgettext("PWA manifest shortcut", "Notizen öffnen"),
                "url": reverse("notes"),
                "icons": [{"src": static("app/icons/pwa-icon-192.png"), "sizes": "192x192"}],
            },
            {
                "name": pgettext("PWA manifest shortcut", "Chat"),
                "short_name": pgettext("PWA manifest shortcut", "Chat"),
                "description": pgettext("PWA manifest shortcut", "Chats öffnen"),
                "url": reverse("chat"),
                "icons": [{"src": static("app/icons/pwa-icon-192.png"), "sizes": "192x192"}],
            },
        ],
    }
    response = JsonResponse(manifest, json_dumps_params={"ensure_ascii": False})
    response["Content-Type"] = "application/manifest+json; charset=utf-8"
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def pwa_service_worker_view(request):
    """Serve the Service Worker from the origin root so it can control the whole app."""
    precache_urls = [
        reverse("offline"),
        reverse("shopping_offline"),
        static("app/css/core.css"),
        static("app/css/shopping_list.css"),
        static("app/js/base.js"),
        static("app/js/shopping_offline.js"),
        static("app/js/shopping_offline_shell.js"),
        static("app/icons/cloud-solid.png"),
        static("app/icons/pwa-icon-180.png"),
        static("app/icons/pwa-icon-192.png"),
        static("app/icons/pwa-icon-512.png"),
        static("app/icons/pwa-maskable-192.png"),
        static("app/icons/pwa-maskable-512.png"),
    ]
    response = render(
        request,
        "app/pwa/service-worker.js",
        {
            "cache_version": PWA_CACHE_VERSION,
            "offline_url": reverse("offline"),
            "shopping_offline_url": reverse("shopping_offline"),
            "shopping_list_url": reverse("shopping_list"),
            "precache_urls_json": json.dumps(precache_urls, ensure_ascii=False),
        },
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def offline_view(request):
    response = render(request, "app/pwa/offline.html")
    response["Cache-Control"] = "public, max-age=300"
    return response


def shopping_offline_view(request):
    response = render(request, "app/pwa/shopping_offline.html")
    response["Cache-Control"] = "public, max-age=300"
    return response
