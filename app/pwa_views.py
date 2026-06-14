import json

from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse


PWA_THEME_COLOR = "#1a56d6"
PWA_BACKGROUND_COLOR = "#dce5f5"
PWA_CACHE_VERSION = "mytools-pwa-v3"


def pwa_manifest_view(request):
    """Return the installable web app manifest for MyTools."""
    manifest = {
        "name": "MyTools",
        "short_name": "MyTools",
        "description": "Private Tools, Widgets und Spiele in einer installierbaren Web-App.",
        "id": reverse("home"),
        "start_url": reverse("home"),
        "scope": "/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone", "minimal-ui", "browser"],
        "orientation": "portrait-primary",
        "theme_color": PWA_THEME_COLOR,
        "background_color": PWA_BACKGROUND_COLOR,
        "categories": ["productivity", "utilities", "games"],
        "lang": "de-DE",
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
                "name": "Startseite",
                "short_name": "Start",
                "description": "Dashboard öffnen",
                "url": reverse("home"),
                "icons": [{"src": static("app/icons/pwa-icon-192.png"), "sizes": "192x192"}],
            },
            {
                "name": "Notizen",
                "short_name": "Notizen",
                "description": "Notizen öffnen",
                "url": reverse("notes"),
                "icons": [{"src": static("app/icons/pwa-icon-192.png"), "sizes": "192x192"}],
            },
            {
                "name": "Chat",
                "short_name": "Chat",
                "description": "Chats öffnen",
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
        static("app/css/core.css"),
        static("app/js/base.js"),
        static("app/icons/cloud-solid.png"),
        static("app/icons/pwa-icon-180.png"),
        static("app/icons/pwa-icon-192.png"),
        static("app/icons/pwa-icon-512.png"),
        static("app/icons/pwa-maskable-192.png"),
        static("app/icons/pwa-maskable-512.png"),
    ]
    response = render(
        request,
        "app/service-worker.js",
        {
            "cache_version": PWA_CACHE_VERSION,
            "offline_url": reverse("offline"),
            "precache_urls_json": json.dumps(precache_urls, ensure_ascii=False),
        },
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def offline_view(request):
    response = render(request, "app/offline.html")
    response["Cache-Control"] = "public, max-age=300"
    return response
