import os
import platform
import shutil
from datetime import timedelta

import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .achievement_utils import get_achievement_summary
from .models import FeatureComment, FeatureIdea, FeatureVote, SecurityEvent


STARTED_AT = timezone.now()

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
    uptime = now - STARTED_AT
    disk_usage = _safe_disk_usage(settings.BASE_DIR)
    static_root = getattr(settings, "STATIC_ROOT", "") or _("nicht gesetzt")
    media_root = getattr(settings, "MEDIA_ROOT", "") or _("nicht gesetzt")

    services = [
        {"name": _("Django App"), "status": "ok", "label": _("Online"), "detail": _("Request wurde erfolgreich verarbeitet."), "icon": "fa-solid fa-cloud"},
        _check_database(),
        _check_cache(),
        {"name": _("PWA"), "status": "ok", "label": _("Aktiv"), "detail": reverse("pwa_service_worker"), "icon": "fa-solid fa-mobile-screen-button"},
    ]

    status_counts = {
        "security_events_today": SecurityEvent.objects.filter(created_at__date=timezone.localdate()).count(),
        "failed_logins_today": SecurityEvent.objects.filter(event_type=SecurityEvent.EVENT_LOGIN_FAILED, created_at__date=timezone.localdate()).count(),
        "feature_ideas_open": FeatureIdea.objects.exclude(status__in=[FeatureIdea.STATUS_DONE, FeatureIdea.STATUS_REJECTED]).count(),
        "feature_votes": FeatureVote.objects.count(),
    }

    context = {
        "services": services,
        "all_services_ok": all(service["status"] == "ok" for service in services),
        "disk_usage": disk_usage,
        "metrics": [
            {"label": _("Python"), "value": platform.python_version(), "icon": "fa-brands fa-python"},
            {"label": _("Django"), "value": django.get_version(), "icon": "fa-solid fa-server"},
            {"label": _("Debug"), "value": _("Aktiv") if settings.DEBUG else _("Aus"), "icon": "fa-solid fa-bug"},
            {"label": _("Prozess-RAM"), "value": _process_memory_label(), "icon": "fa-solid fa-memory"},
            {"label": _("Load Average"), "value": _load_average_label(), "icon": "fa-solid fa-chart-line"},
            {"label": _("Uptime"), "value": str(timedelta(seconds=int(uptime.total_seconds()))), "icon": "fa-regular fa-clock"},
        ],
        "paths": [
            {"label": _("Projekt"), "value": str(settings.BASE_DIR)},
            {"label": _("Static Root"), "value": str(static_root)},
            {"label": _("Media Root"), "value": str(media_root)},
        ],
        "status_counts": status_counts,
    }
    return render(request, "app/server_status.html", context)
