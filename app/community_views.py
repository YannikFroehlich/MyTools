import json
import os
import platform
import shutil
from datetime import timedelta
from pathlib import Path

import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .achievement_utils import get_achievement_summary
from .models import ChatMessage, FeatureComment, FeatureIdea, FeatureVote, FileShare, HomeWidget, ModerationAuditLog, Note, SecurityEvent, SiteAccessSettings, ToolFeedback, UserPresence, UserReport


STARTED_AT = timezone.now()

def get_changelog_entries():
    return [
        {
            "version": "2026.13",
            "date": "21.06.2026",
            "title": _("Dashboard, Navigation und Profile"),
            "summary": _("MyTools ist übersichtlicher, sicherer bedienbar und lässt sich schneller an den eigenen Alltag anpassen."),
            "type": _("Plattform"),
            "icon": "fa-solid fa-sparkles",
            "items": [
                _("Einsteiger-Modus mit Dashboard-Vorlagen für Alltag, Gaming und Homelab ergänzt."),
                _("Papierkorb mit 30 Tagen Wiederherstellung für Notizen, Dateien, Widgets und Shortcuts eingebaut."),
                _("Spiele, Tools, Google-Apps und die globale Suche haben klar unterscheidbare Designs erhalten."),
                _("Header, Profilansicht und Profileinstellungen wurden optisch und funktional voneinander getrennt."),
                _("Barrierefreiheit, Dialog-Fokus, mobile Suche und Rückgängig-Aktionen wurden verbessert."),
            ],
        },
        {
            "version": "2026.12",
            "date": "19.06.2026",
            "title": _("Nebula Forge Tycoon Update"),
            "summary": _("Nebula Forge Tycoon wurde überarbeitet, neue Animationen wurden ergänzt und das Leaderboard zeigt jetzt die aktuellen Spiele."),
            "type": _("Games"),
            "icon": "fa-solid fa-wand-sparkles",
            "items": [
                _("Nebula Forge Tycoon wurde visuell überarbeitet und wirkt jetzt deutlich lebendiger."),
                _("Kauf-, Prestige- und Ability-Aktionen haben neue Animationen und Effekte bekommen."),
                _("Das Leaderboard wurde um aktuelle Spiele wie 2048, Cookie Cosmos V2, Nebula Forge Tycoon, Schiffe versenken, Uno, Kniffel und Pong erweitert."),
                _("Cookie Cosmos, Cookie Cosmos V2 und Nebula Forge Tycoon sortieren ihre Ranglisten jetzt nach aktueller Währung und zeigen zusätzlich Rekorde."),
            ],
        },
        {
            "version": "2026.11",
            "date": "18.06.2026",
            "title": _("Nebula Forge Tycoon Release"),
            "summary": _("Nebula Forge Tycoon wurde hinzugefügt, ähnlich wie Cookie Cosmos und man kann als Admin nun kontrollieren wer auf welches tool oder game zugreifen kann"),
            "type": _("Games"),
            "icon": "fa-solid fa-meteor",
            "items": [
                _("Nebula Forge Tycoon wurde hinzugefügt."),
                _("Kontrolle wer auf welches tool zugreifen kann."),
                _("Kleinere Style Anpassungen"),
            ],
        },
        {
            "version": "2026.10",
            "date": "17.06.2026",
            "title": _("Datei-Konverter und einheitliches Tool-Design"),
            "summary": _("Der neue Datei-Konverter, ein gemeinsamer Tool-Seiten-Look und gezielte Kontrastkorrekturen machen die Werkzeugbereiche einheitlicher und besser lesbar."),
            "type": _("Tools"),
            "icon": "fa-solid fa-file-arrow-down",
            "items": [
                _("Datei-Konverter für DOCX, Tabellen, Präsentationen, Textdateien und Bilder ergänzt."),
                _("Office-zu-PDF läuft serverseitig über LibreOffice und verarbeitet Uploads nur temporär."),
                _("Toolbox-Seiten übernehmen jetzt gemeinsame Theme-Farben, Karten, Buttons, Inputs und Kontrastmodus-Regeln."),
                _("Bild Tools, Datei-Konverter, Einheitenrechner, Spritkosten und QR-Code Tool wurden farblich nachjustiert."),
                _("Der Quality-Workflow startet nicht mehr automatisch bei jedem Push oder Merge, sondern nur noch manuell."),
            ],
        },
        {
            "version": "2026.09",
            "date": "15.06.2026",
            "title": _("Stream Deck mit Voicemod-Steuerung"),
            "summary": _("Das Stream Deck kann Voicemod jetzt direkt steuern und nutzt dafuer einen lokal gespeicherten API-Key pro Browser."),
            "type": _("Integration"),
            "icon": "fa-solid fa-wand-magic-sparkles",
            "items": [
                _("Voicemod-Aktionen fuer Voice Changer, Hear Myself, Mikrofon-Mute, Zufalls-Voice und Voice-Wechsel ergaenzt."),
                _("Voices lassen sich aus Voicemod laden und im Button-Editor per Dropdown auswaehlen."),
                _("Der Voicemod API-Key wird im Stream Deck gespeichert und bei fehlender Verbindung klar als Hinweis angezeigt."),
            ],
        },
        {
            "version": "2026.08",
            "date": "14.06.2026",
            "title": _("Mobile Bedienung, Realtime und Qualität"),
            "summary": _("Die mobile Navigation ist flexibler, Benachrichtigungen aktualisieren sich direkter und die Codebasis ist besser für weitere Updates vorbereitet."),
            "type": _("Update"),
            "icon": "fa-solid fa-mobile-screen-button",
            "items": [
                _("Mobile Ansicht blendet den oberen Header standardmäßig aus und bietet einen Button zum Ein- und Ausblenden."),
                _("Google-Suche auf der Startseite wurde auf kleinen Displays optisch nachjustiert."),
                _("Live-Status und Benachrichtigungszähler nutzen WebSocket-Updates mit HTTP-Fallback."),
                _("Notes- und PWA-Views wurden aus der großen View-Datei herausgelöst."),
                _("Neuer Qualitätslauf bündelt Systemcheck, Migration-Check, Tests, collectstatic-Dry-Run und JavaScript-Syntaxprüfung."),
            ],
        },
        {
            "version": "2026.07",
            "date": "14.06.2026",
            "title": _("Suche, Mobile, Datei-Share und Profile"),
            "summary": _("Globale Suche, Quick Actions, mobile Navigation und bessere Freigaben machen MyTools schneller bedienbar und sichtbarer vernetzt."),
            "type": _("Plattform"),
            "icon": "fa-solid fa-magnifying-glass",
            "items": [
                _("Globale MyTools-Suche mit Ctrl+K für Tools, Notizen, Dateien, Nutzer und Roadmap-Ideen ergänzt."),
                _("Startseite mit Quick Actions für Suche, Widgets, Favoriten, Design und Changelog erweitert."),
                _("Mobile Bottom-Navigation für Start, Suche, Tools, Chat und Profil eingebaut."),
                _("Datei-Share mit Passwortschutz, Ablaufdatum, Download-Limit sowie Bild- und PDF-Vorschau ausgebaut."),
                _("Profilseite mit Spotlight-Statistiken und feineren Benachrichtigungseinstellungen erweitert."),
            ],
        },
        {
            "version": "2026.06",
            "date": "14.06.2026",
            "title": _("Design, Status und Transparenz"),
            "summary": _("Neue Design-Modi, ein ausgebauter System-Monitor und diese Changelog-Seite machen MyTools leichter anpassbar und besser nachvollziehbar."),
            "type": _("Update"),
            "icon": "fa-solid fa-wand-magic-sparkles",
            "items": [
                _("Design-Editor fokussiert: eigene Farben, hoher Kontrast, weniger Bewegung und verbesserter Hintergrundeffekt."),
                _("Serverstatus mit Admin-Karten, App-Aktivität, Mediengröße, Datenbankgröße und letzten Security-Events ausgebaut."),
                _("Neue Was-ist-neu-Seite als zentraler Verlauf für sichtbare Änderungen ergänzt."),
            ],
        },
        {
            "version": "2026.05",
            "date": "12.06.2026",
            "title": _("Community und Sicherheit"),
            "summary": _("Roadmap, Achievement-Center, Moderation und Security-Dashboard geben der Plattform mehr Struktur."),
            "type": _("Plattform"),
            "icon": "fa-solid fa-shield-halved",
            "items": [
                _("Feature-Ideen können gesammelt, gevotet und kommentiert werden."),
                _("Admins erhalten Moderations- und Sicherheitswerkzeuge."),
                _("Benachrichtigungen, 2FA und Security-Events runden den Kontobereich ab."),
            ],
        },
        {
            "version": "2026.04",
            "date": "04.06.2026",
            "title": _("Mehr Tools für den Alltag"),
            "summary": _("Notizen, Datei-Share, Budget-Tracker, Medienwerkzeuge und Widgets wachsen stärker zusammen."),
            "type": _("Tools"),
            "icon": "fa-solid fa-screwdriver-wrench",
            "items": [
                _("Startseiten-Widgets zeigen wichtige Daten schneller an."),
                _("Notizen unterstützen Pins, Erinnerungen und Teilen."),
                _("Dateien, Bilder und Budgetdaten bekommen eigene Arbeitsbereiche."),
            ],
        },
        {
            "version": "2026.03",
            "date": "24.05.2026",
            "title": _("Spielebibliothek"),
            "summary": _("Solo- und Mehrspielerbereiche wurden zu einer kleinen Spieleplattform erweitert."),
            "type": _("Games"),
            "icon": "fa-solid fa-gamepad",
            "items": [
                _("Mehrspieler-Lobbys, Einladungen und Live-Status für mehrere Spiele."),
                _("Highscores und Leaderboards für Solo-Spiele."),
                _("Profilkarten und Achievements geben Spielern mehr Identität."),
            ],
        },
    ]


def get_git_changelog():
    changelog_path = Path(settings.BASE_DIR) / "app" / "static" / "app" / "data" / "changelog_git.json"
    if not changelog_path.exists():
        return {
            "available": False,
            "items": [],
            "generated_at_display": "",
            "branch": "",
            "current_commit": "",
            "reason": "missing",
        }

    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "items": [],
            "generated_at_display": "",
            "branch": "",
            "current_commit": "",
            "reason": "invalid",
        }

    items = []
    for item in data.get("entries", [])[:20]:
        message = _clean_text(item.get("message"), 180)
        if not message:
            continue
        items.append({
            "message": message,
            "short_hash": _clean_text(item.get("short_hash"), 20),
            "date_display": _clean_text(item.get("date_display"), 20),
            "type": _clean_text(item.get("type"), 40) or _("Commit"),
            "icon": _clean_text(item.get("icon"), 80) or "fa-solid fa-code-commit",
            "author": _clean_text(item.get("author"), 80),
        })

    return {
        "available": bool(data.get("available") and items),
        "items": items,
        "generated_at_display": _clean_text(data.get("generated_at_display"), 40),
        "branch": _clean_text(data.get("branch"), 80),
        "current_commit": _clean_text(data.get("current_commit"), 20),
        "reason": _clean_text(data.get("reason"), 180),
    }


staff_required = user_passes_test(
    lambda user: user.is_active and user.is_staff,
    login_url="login",
)


def _clean_text(value, max_length=1000):
    return " ".join(str(value or "").strip().split())[:max_length]


def _human_bytes(size):
    size = float(size or 0)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return "0 B"


def _status_meta():
    return {
        FeatureIdea.STATUS_SUGGESTED: {"icon": "fa-regular fa-lightbulb", "class": "is-suggested"},
        FeatureIdea.STATUS_PLANNED: {"icon": "fa-solid fa-list-check", "class": "is-planned"},
        FeatureIdea.STATUS_IN_PROGRESS: {"icon": "fa-solid fa-code-branch", "class": "is-progress"},
        FeatureIdea.STATUS_DONE: {"icon": "fa-solid fa-circle-check", "class": "is-done"},
        FeatureIdea.STATUS_REJECTED: {"icon": "fa-solid fa-ban", "class": "is-rejected"},
    }


@login_required
@require_http_methods(["GET", "POST"])
def roadmap_view(request):
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            title = _clean_text(request.POST.get("title"), 120)
            description = str(request.POST.get("description") or "").strip()[:1800]
            category = request.POST.get("category")
            priority = request.POST.get("priority")

            valid_categories = {key for key, _label in FeatureIdea.CATEGORY_CHOICES}
            valid_priorities = {key for key, _label in FeatureIdea.PRIORITY_CHOICES}

            if not title or not description:
                messages.error(request, _("Bitte gib Titel und Beschreibung ein."))
            else:
                FeatureIdea.objects.create(
                    author=request.user,
                    title=title,
                    description=description,
                    category=category if category in valid_categories else FeatureIdea.CATEGORY_TOOL,
                    priority=priority if priority in valid_priorities else FeatureIdea.PRIORITY_NORMAL,
                )
                messages.success(request, _("Deine Feature-Idee wurde eingetragen."))
            return redirect("roadmap")

        if action == "vote":
            idea = get_object_or_404(FeatureIdea, pk=request.POST.get("idea_id"))
            vote, created = FeatureVote.objects.get_or_create(idea=idea, user=request.user)
            if created:
                messages.success(request, _("Vote gesetzt."))
            else:
                vote.delete()
                messages.info(request, _("Vote entfernt."))
            return redirect("roadmap")

        if action == "comment":
            idea = get_object_or_404(FeatureIdea, pk=request.POST.get("idea_id"))
            text = str(request.POST.get("text") or "").strip()[:1000]
            if text:
                FeatureComment.objects.create(idea=idea, user=request.user, text=text)
                messages.success(request, _("Kommentar gespeichert."))
            else:
                messages.error(request, _("Bitte gib einen Kommentar ein."))
            return redirect("roadmap")

        if action == "update_status" and request.user.is_staff:
            idea = get_object_or_404(FeatureIdea, pk=request.POST.get("idea_id"))
            status = request.POST.get("status")
            valid_statuses = {key for key, _label in FeatureIdea.STATUS_CHOICES}
            if status in valid_statuses:
                idea.status = status
                idea.admin_note = _clean_text(request.POST.get("admin_note"), 255)
                idea.save(update_fields=["status", "admin_note", "updated_at"])
                messages.success(request, _("Roadmap-Status wurde aktualisiert."))
            else:
                messages.error(request, _("Ungültiger Status."))
            return redirect("roadmap")

    selected_status = request.GET.get("status", "all")
    selected_category = request.GET.get("category", "all")
    selected_order = request.GET.get("order", "popular")
    query = _clean_text(request.GET.get("q"), 120)

    ideas = FeatureIdea.objects.select_related("author").prefetch_related("comments__user").annotate(
        vote_total=Count("votes", distinct=True),
        comment_total=Count("comments", distinct=True),
    )

    valid_statuses = {key for key, _label in FeatureIdea.STATUS_CHOICES}
    valid_categories = {key for key, _label in FeatureIdea.CATEGORY_CHOICES}

    if selected_status in valid_statuses:
        ideas = ideas.filter(status=selected_status)
    else:
        selected_status = "all"

    if selected_category in valid_categories:
        ideas = ideas.filter(category=selected_category)
    else:
        selected_category = "all"

    if query:
        ideas = ideas.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(admin_note__icontains=query))

    if selected_order == "newest":
        ideas = ideas.order_by("-created_at")
    elif selected_order == "active":
        ideas = ideas.order_by("-updated_at", "-created_at")
    else:
        selected_order = "popular"
        ideas = ideas.order_by("-vote_total", "-comment_total", "-created_at")

    voted_idea_ids = set(FeatureVote.objects.filter(user=request.user).values_list("idea_id", flat=True))
    status_counts = FeatureIdea.objects.values("status").annotate(total=Count("id"))
    status_count_map = {row["status"]: row["total"] for row in status_counts}
    status_meta = _status_meta()

    status_tabs = [{
        "key": "all",
        "label": _("Alle"),
        "count": FeatureIdea.objects.count(),
        "icon": "fa-solid fa-layer-group",
        "class": "is-all",
    }]
    for key, label in FeatureIdea.STATUS_CHOICES:
        meta = status_meta.get(key, {})
        status_tabs.append({
            "key": key,
            "label": label,
            "count": status_count_map.get(key, 0),
            "icon": meta.get("icon", "fa-regular fa-circle"),
            "class": meta.get("class", ""),
        })

    context = {
        "ideas": ideas[:80],
        "voted_idea_ids": voted_idea_ids,
        "status_tabs": status_tabs,
        "status_choices": FeatureIdea.STATUS_CHOICES,
        "category_choices": FeatureIdea.CATEGORY_CHOICES,
        "priority_choices": FeatureIdea.PRIORITY_CHOICES,
        "selected_status": selected_status,
        "selected_category": selected_category,
        "selected_order": selected_order,
        "query": query,
        "total_ideas": FeatureIdea.objects.count(),
        "total_votes": FeatureVote.objects.count(),
        "done_count": status_count_map.get(FeatureIdea.STATUS_DONE, 0),
        "in_progress_count": status_count_map.get(FeatureIdea.STATUS_IN_PROGRESS, 0),
    }
    return render(request, "app/roadmap.html", context)


@login_required
def achievement_center_view(request):
    summary = get_achievement_summary(request.user)
    UserModel = get_user_model()
    leaderboard_entries = []

    for user in UserModel.objects.filter(is_active=True).order_by("username")[:100]:
        user_summary = get_achievement_summary(user)
        leaderboard_entries.append({
            "user": user,
            "summary": user_summary,
            "xp": user_summary["total_xp"],
            "level": user_summary["level"]["level"],
            "unlocked_count": user_summary["unlocked_count"],
        })

    leaderboard_entries.sort(key=lambda item: (item["xp"], item["unlocked_count"], item["user"].date_joined), reverse=True)
    user_rank = next((index + 1 for index, item in enumerate(leaderboard_entries) if item["user"].id == request.user.id), None)

    context = {
        "achievement_summary": summary,
        "leaderboard_entries": leaderboard_entries[:10],
        "user_rank": user_rank,
        "recent_unlocked": list(reversed(summary["unlocked"][-6:])),
    }
    return render(request, "app/achievement_center.html", context)


def changelog_view(request):
    changelog_entries = get_changelog_entries()
    git_changelog = get_git_changelog()
    context = {
        "changelog_entries": changelog_entries,
        "latest_entry": changelog_entries[0] if changelog_entries else None,
        "release_count": len(changelog_entries),
        "change_count": sum(len(entry["items"]) for entry in changelog_entries),
        "git_changelog": git_changelog,
        "git_change_count": len(git_changelog["items"]),
    }
    return render(request, "app/changelog.html", context)


def _check_database():
    started = timezone.now()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        duration_ms = round((timezone.now() - started).total_seconds() * 1000)
        return {"name": _("Datenbank"), "status": "ok", "label": _("Online"), "detail": f"{connection.vendor} · {duration_ms} ms", "icon": "fa-solid fa-database"}
    except Exception as exc:
        return {"name": _("Datenbank"), "status": "error", "label": _("Fehler"), "detail": str(exc)[:160], "icon": "fa-solid fa-database"}


def _check_cache():
    key = "mytools_server_status_check"
    value = timezone.now().isoformat()
    try:
        cache.set(key, value, timeout=15)
        ok = cache.get(key) == value
        return {"name": _("Cache"), "status": "ok" if ok else "warning", "label": _("Online") if ok else _("Prüfen"), "detail": _("Schreiben/Lesen erfolgreich") if ok else _("Cache-Wert konnte nicht gelesen werden."), "icon": "fa-solid fa-memory"}
    except Exception as exc:
        return {"name": _("Cache"), "status": "error", "label": _("Fehler"), "detail": str(exc)[:160], "icon": "fa-solid fa-memory"}


def _safe_disk_usage(path):
    try:
        usage = shutil.disk_usage(path)
        used_percent = round((usage.used / usage.total) * 100) if usage.total else 0
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "total_label": _human_bytes(usage.total),
            "used_label": _human_bytes(usage.used),
            "free_label": _human_bytes(usage.free),
            "used_percent": used_percent,
        }
    except Exception:
        return None


def _path_size(path):
    root = Path(path)
    if not root.exists():
        return 0

    if root.is_file():
        try:
            return root.stat().st_size
        except OSError:
            return 0

    total = 0
    try:
        for item in root.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _database_size_label():
    database_settings = settings.DATABASES.get("default", {})
    database_name = database_settings.get("NAME")
    if database_name and database_settings.get("ENGINE", "").endswith("sqlite3"):
        return _human_bytes(_path_size(database_name))
    return _("Nicht verfügbar")


def _media_usage_summary():
    media_root = getattr(settings, "MEDIA_ROOT", "")
    if not media_root:
        return {"label": _("Nicht gesetzt"), "bytes": 0}
    size = _path_size(media_root)
    return {"label": _human_bytes(size), "bytes": size}


def _process_memory_label():
    status_path = "/proc/self/status"
    if not os.path.exists(status_path):
        return _("Nicht verfügbar")
    try:
        with open(status_path, "r", encoding="utf-8") as status_file:
            for line in status_file:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return _human_bytes(int(parts[1]) * 1024)
    except Exception:
        pass
    return _("Nicht verfügbar")


def _load_average_label():
    if hasattr(os, "getloadavg"):
        try:
            values = os.getloadavg()
            return " / ".join(f"{value:.2f}" for value in values)
        except OSError:
            return _("Nicht verfügbar")
    return _("Nicht verfügbar")


@staff_required
def server_status_view(request):
    now = timezone.now()
    today = timezone.localdate()
    uptime = now - STARTED_AT
    disk_usage = _safe_disk_usage(settings.BASE_DIR)
    media_usage = _media_usage_summary()
    static_root = getattr(settings, "STATIC_ROOT", "") or _("nicht gesetzt")
    media_root_value = getattr(settings, "MEDIA_ROOT", "")
    media_root = media_root_value or _("nicht gesetzt")
    media_ready = bool(media_root_value and os.path.isdir(media_root_value))
    UserModel = get_user_model()
    online_since = now - timedelta(minutes=3)

    services = [
        {"name": _("Django App"), "status": "ok", "label": _("Online"), "detail": _("Request wurde erfolgreich verarbeitet."), "icon": "fa-solid fa-cloud"},
        _check_database(),
        _check_cache(),
        {"name": _("PWA"), "status": "ok", "label": _("Aktiv"), "detail": reverse("pwa_service_worker"), "icon": "fa-solid fa-mobile-screen-button"},
        {"name": _("Media"), "status": "ok" if media_ready else "warning", "label": _("Bereit") if media_ready else _("Prüfen"), "detail": media_usage["label"], "icon": "fa-solid fa-photo-film"},
    ]

    status_counts = {
        "security_events_today": SecurityEvent.objects.filter(created_at__date=today).count(),
        "failed_logins_today": SecurityEvent.objects.filter(event_type=SecurityEvent.EVENT_LOGIN_FAILED, created_at__date=today).count(),
        "feature_ideas_open": FeatureIdea.objects.exclude(status__in=[FeatureIdea.STATUS_DONE, FeatureIdea.STATUS_REJECTED]).count(),
        "feature_votes": FeatureVote.objects.count(),
    }
    file_share_bytes = FileShare.objects.aggregate(total=Sum("size"))["total"] or 0
    app_activity = [
        {"label": _("Aktive Nutzer"), "value": UserPresence.objects.filter(last_seen__gte=online_since).count(), "hint": _("letzte 3 Minuten"), "icon": "fa-solid fa-signal"},
        {"label": _("Nutzer gesamt"), "value": UserModel.objects.filter(is_active=True).count(), "hint": _("aktive Konten"), "icon": "fa-solid fa-users"},
        {"label": _("Chatnachrichten heute"), "value": ChatMessage.objects.filter(created_at__date=today).count(), "hint": _("neue Nachrichten"), "icon": "fa-solid fa-comments"},
        {"label": _("Notizen"), "value": Note.objects.filter(is_archived=False).count(), "hint": _("nicht archiviert"), "icon": "fa-regular fa-note-sticky"},
        {"label": _("Dateifreigaben"), "value": FileShare.objects.count(), "hint": _human_bytes(file_share_bytes), "icon": "fa-solid fa-share-nodes"},
        {"label": _("Startseiten-Widgets"), "value": HomeWidget.objects.count(), "hint": _("konfiguriert"), "icon": "fa-solid fa-table-cells-large"},
    ]
    recent_security_events = SecurityEvent.objects.select_related("user").order_by("-created_at")[:6]
    site_access = SiteAccessSettings.get_solo()
    admin_cards = [
        {
            "label": _("Offene Meldungen"),
            "value": UserReport.objects.filter(is_resolved=False).count(),
            "hint": _("Moderation"),
            "icon": "fa-solid fa-flag",
            "url": reverse("moderation"),
        },
        {
            "label": _("Offenes Feedback"),
            "value": ToolFeedback.objects.filter(status=ToolFeedback.STATUS_OPEN).count(),
            "hint": _("Feedback"),
            "icon": "fa-solid fa-comment-dots",
            "url": reverse("moderation"),
        },
        {
            "label": _("Letzte Audits"),
            "value": ModerationAuditLog.objects.count(),
            "hint": _("Protokoll"),
            "icon": "fa-solid fa-clipboard-list",
            "url": reverse("moderation"),
        },
        {
            "label": _("Zugang"),
            "value": _("Gesperrt") if site_access.login_registration_locked else _("Offen"),
            "hint": site_access.updated_at.strftime("%d.%m.%Y %H:%M"),
            "icon": "fa-solid fa-door-open",
            "url": reverse("moderation"),
        },
    ]
    status_warnings = []
    if disk_usage and disk_usage["used_percent"] >= 85:
        status_warnings.append(_("Projekt-Laufwerk ist zu %(percent)s%% belegt.") % {"percent": disk_usage["used_percent"]})
    if status_counts["failed_logins_today"] >= 5:
        status_warnings.append(_("%(count)s fehlgeschlagene Logins heute.") % {"count": status_counts["failed_logins_today"]})

    context = {
        "services": services,
        "all_services_ok": all(service["status"] == "ok" for service in services),
        "disk_usage": disk_usage,
        "media_usage": media_usage,
        "metrics": [
            {"label": _("Python"), "value": platform.python_version(), "icon": "fa-brands fa-python"},
            {"label": _("Django"), "value": django.get_version(), "icon": "fa-solid fa-server"},
            {"label": _("Debug"), "value": _("Aktiv") if settings.DEBUG else _("Aus"), "icon": "fa-solid fa-bug"},
            {"label": _("Prozess-RAM"), "value": _process_memory_label(), "icon": "fa-solid fa-memory"},
            {"label": _("Load Average"), "value": _load_average_label(), "icon": "fa-solid fa-chart-line"},
            {"label": _("Uptime"), "value": str(timedelta(seconds=int(uptime.total_seconds()))), "icon": "fa-regular fa-clock"},
            {"label": _("Datenbankgröße"), "value": _database_size_label(), "icon": "fa-solid fa-database"},
            {"label": _("Medienordner"), "value": media_usage["label"], "icon": "fa-solid fa-photo-film"},
        ],
        "app_activity": app_activity,
        "admin_cards": admin_cards,
        "status_warnings": status_warnings,
        "recent_security_events": recent_security_events,
        "paths": [
            {"label": _("Projekt"), "value": str(settings.BASE_DIR)},
            {"label": _("Static Root"), "value": str(static_root)},
            {"label": _("Media Root"), "value": str(media_root)},
        ],
        "status_counts": status_counts,
    }
    return render(request, "app/server_status.html", context)
