import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.contrib.staticfiles import finders

from ..access_control import ACCESS_CONTROL_KEYS, get_access_control_items
from ..image_optimization import (
    CHAT_AVATAR_MAX_SIZE,
    FILE_SHARE_IMAGE_MAX_SIZE,
    GALLERY_IMAGE_MAX_SIZE,
    PROFILE_AVATAR_MAX_SIZE,
    SHORTCUT_ICON_MAX_SIZE,
    WIKI_IMAGE_MAX_SIZE,
    optimize_existing_image_field,
    optimize_static_image_path,
)
from ..models import (
    AvatarCharacter,
    ChatRoom,
    FileShare,
    InboxItem,
    ModerationAuditLog,
    ProfileGalleryImage,
    Shortcut,
    SiteAccessSettings,
    ToolFeedback,
    UserBlock,
    UserProfile,
    UserReport,
    UserSuspension,
)


staff_required = user_passes_test(
    lambda user: user.is_active and user.is_staff,
    login_url="login",
)


def _human_size(size):
    size = float(size or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024





STATIC_IMAGE_TARGETS = (
    {"path": "app/img/Airtemple-island.webp", "label": "Avatar-Wiki-Hintergrund", "max_size": (1920, 1080), "quality": 74},
    {"path": "app/img/worldmap.webp", "label": "Uhr-Weltkarte", "max_size": (1800, 900), "quality": 76},
    {"path": "app/img/Skribble-background.webp", "label": "Skribble-Hintergrund", "max_size": (1920, 1080), "quality": 76},
    {"path": "app/img/Skribble-logo.webp", "label": "Skribble-Logo", "max_size": (1000, 500), "quality": 80},
)


def _static_candidate_paths(relative_path):
    candidates = []

    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        candidates.append(os.path.join(static_root, relative_path))

    found_paths = finders.find(relative_path, all=True) or []
    if isinstance(found_paths, str):
        found_paths = [found_paths]
    candidates.extend(found_paths)

    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized not in seen:
            seen.add(normalized)
            yield normalized


def _add_optimization_result_to_stats(stats, result, label):
    stats["bytes_before"] += result.old_size
    stats["bytes_after"] += result.new_size
    stats["bytes_saved"] += result.bytes_saved

    if result.converted:
        stats["converted"] += 1
    elif result.missing:
        stats["missing"] += 1
    else:
        stats["skipped"] += 1

    if result.reason and result.reason not in {"empty", "already_optimized"}:
        stats["details"].append(f"{label}: {result.reason}")

def _optimization_summary(stats):
    return {
        "checked": stats["checked"],
        "converted": stats["converted"],
        "skipped": stats["skipped"],
        "missing": stats["missing"],
        "failed": stats["failed"],
        "bytes_before": stats["bytes_before"],
        "bytes_after": stats["bytes_after"],
        "bytes_saved": stats["bytes_saved"],
        "human_before": _human_size(stats["bytes_before"]),
        "human_after": _human_size(stats["bytes_after"]),
        "human_saved": _human_size(stats["bytes_saved"]),
    }


def _optimize_model_image_fields(queryset, field_name, *, max_size, quality, stats, label, extra_update_fields=None):
    for instance in queryset.iterator():
        stats["checked"] += 1
        try:
            result = optimize_existing_image_field(
                instance,
                field_name,
                max_size=max_size,
                quality=quality,
                extra_update_fields=extra_update_fields(instance) if extra_update_fields else None,
            )
        except Exception as exc:  # pragma: no cover - defensive guard for unexpected storage errors
            stats["failed"] += 1
            stats["details"].append(f"{label} #{instance.pk}: {exc}")
            continue

        _add_optimization_result_to_stats(stats, result, label)



def _optimize_static_image_files(stats):
    for target in STATIC_IMAGE_TARGETS:
        paths = list(_static_candidate_paths(target["path"]))
        if not paths:
            stats["checked"] += 1
            stats["missing"] += 1
            stats["details"].append(f"{target['label']}: missing")
            continue

        for path in paths:
            stats["checked"] += 1
            try:
                result = optimize_static_image_path(
                    path,
                    max_size=target["max_size"],
                    quality=target["quality"],
                )
            except Exception as exc:  # pragma: no cover - defensive guard for unexpected filesystem errors
                stats["failed"] += 1
                stats["details"].append(f"{target['label']}: {exc}")
                continue

            _add_optimization_result_to_stats(stats, result, target["label"])

def _optimize_existing_media_files():
    stats = {
        "checked": 0,
        "converted": 0,
        "skipped": 0,
        "missing": 0,
        "failed": 0,
        "bytes_before": 0,
        "bytes_after": 0,
        "bytes_saved": 0,
        "details": [],
    }

    _optimize_model_image_fields(
        UserProfile.objects.exclude(avatar=""),
        "avatar",
        max_size=PROFILE_AVATAR_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Profilbild",
    )
    _optimize_model_image_fields(
        ProfileGalleryImage.objects.exclude(image=""),
        "image",
        max_size=GALLERY_IMAGE_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Profil-Galerie",
    )
    _optimize_model_image_fields(
        Shortcut.objects.exclude(image=""),
        "image",
        max_size=SHORTCUT_ICON_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Shortcut-Icon",
    )
    _optimize_model_image_fields(
        ChatRoom.objects.exclude(avatar=""),
        "avatar",
        max_size=CHAT_AVATAR_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Chat-Gruppenbild",
    )
    _optimize_model_image_fields(
        AvatarCharacter.objects.exclude(image=""),
        "image",
        max_size=WIKI_IMAGE_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Avatar-Wiki-Bild",
    )
    _optimize_model_image_fields(
        FileShare.objects.filter(content_type__startswith="image/").exclude(file=""),
        "file",
        max_size=FILE_SHARE_IMAGE_MAX_SIZE,
        quality=82,
        stats=stats,
        label="Datei-Freigabe",
        extra_update_fields=lambda instance: {
            "content_type": "image/webp",
            "original_name": f"{instance.original_name.rsplit('.', 1)[0]}.webp" if instance.original_name else "image.webp",
            "size": 0,  # replaced below after save by a second lightweight update
        },
    )

    # Keep FileShare.size exact after conversion. This is intentionally separate
    # because the final storage name is only known after save().
    for share in FileShare.objects.filter(content_type="image/webp").exclude(file=""):
        try:
            actual_size = share.file.storage.size(share.file.name)
        except OSError:
            continue
        if share.size != actual_size:
            share.size = actual_size
            share.save(update_fields=["size"])

    _optimize_static_image_files(stats)

    return stats

def _safe_next(request):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return reverse("moderation")


def _filter_search(queryset, query, fields):
    if not query:
        return queryset

    search = Q()
    for field in fields:
        search |= Q(**{f"{field}__icontains": query})
    return queryset.filter(search)


def _audit(request, action, summary, target_user=None, metadata=None):
    ModerationAuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        target_user=target_user,
        action=action,
        summary=summary[:240],
        metadata=metadata or {},
    )


def _active_suspensions_by_user(users):
    now = timezone.now()
    suspensions = (
        UserSuspension.objects
        .filter(user__in=users, is_active=True, starts_at__lte=now, ends_at__gt=now)
        .select_related("user", "moderator")
        .order_by("user_id", "-ends_at")
    )
    active = {}
    for suspension in suspensions:
        active.setdefault(suspension.user_id, suspension)
    return active


@staff_required
def moderation_dashboard_view(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()

    reports = UserReport.objects.select_related("reporter", "reported")
    reports = _filter_search(
        reports,
        query,
        ["reporter__username", "reported__username", "reported__email", "message", "reason"],
    )

    feedback_items = ToolFeedback.objects.select_related("user")
    feedback_items = _filter_search(
        feedback_items,
        query,
        ["title", "message", "tool_key", "user__username", "user__email"],
    )

    file_shares = FileShare.objects.select_related("owner").prefetch_related("recipients")
    file_shares = _filter_search(
        file_shares,
        query,
        ["original_name", "content_type", "owner__username", "owner__email", "token"],
    )

    blocks = UserBlock.objects.select_related("blocker", "blocked")
    blocks = _filter_search(blocks, query, ["blocker__username", "blocked__username"])

    users = User.objects.order_by("-date_joined")
    users = _filter_search(users, query, ["username", "email", "first_name", "last_name"])
    users = list(users[:10])
    active_suspensions = _active_suspensions_by_user(users)
    for user in users:
        user.active_suspension = active_suspensions.get(user.id)

    inbox_logs = InboxItem.objects.select_related("user")
    inbox_logs = _filter_search(inbox_logs, query, ["title", "message", "user__username"])

    audit_logs = ModerationAuditLog.objects.select_related("actor", "target_user")
    audit_logs = _filter_search(audit_logs, query, ["summary", "actor__username", "target_user__username", "action"])

    suspensions = UserSuspension.objects.select_related("user", "moderator", "lifted_by")
    suspensions = _filter_search(suspensions, query, ["user__username", "moderator__username", "reason"])
    active_suspension_count = UserSuspension.objects.filter(
        is_active=True,
        starts_at__lte=timezone.now(),
        ends_at__gt=timezone.now(),
    ).count()
    access_settings = SiteAccessSettings.get_solo()
    tool_access_items = get_access_control_items(access_settings)
    restricted_tool_count = sum(
        1
        for item in tool_access_items
        if item["access_level"] != SiteAccessSettings.TOOL_ACCESS_ALL
    )

    total_share_size = FileShare.objects.aggregate(total=Sum("size"))["total"] or 0
    stats = [
        {
            "label": _("Offene Meldungen"),
            "value": UserReport.objects.filter(is_resolved=False).count(),
            "icon": "fa-solid fa-flag",
            "tone": "danger",
        },
        {
            "label": _("Offenes Feedback"),
            "value": ToolFeedback.objects.filter(status=ToolFeedback.STATUS_OPEN).count(),
            "icon": "fa-solid fa-comment-dots",
            "tone": "info",
        },
        {
            "label": _("Datei-Freigaben"),
            "value": FileShare.objects.count(),
            "icon": "fa-solid fa-share-nodes",
            "tone": "success",
        },
        {
            "label": _("Bild-Medien"),
            "value": (
                UserProfile.objects.exclude(avatar="").count()
                + ProfileGalleryImage.objects.exclude(image="").count()
                + Shortcut.objects.exclude(image="").count()
                + ChatRoom.objects.exclude(avatar="").count()
                + AvatarCharacter.objects.exclude(image="").count()
                + FileShare.objects.filter(content_type__startswith="image/").exclude(file="").count()
            ),
            "icon": "fa-solid fa-image",
            "tone": "info",
        },
        {
            "label": _("Aktive Nutzer"),
            "value": User.objects.filter(is_active=True).count(),
            "icon": "fa-solid fa-users",
            "tone": "neutral",
        },
        {
            "label": _("Aktive Sperren"),
            "value": active_suspension_count,
            "icon": "fa-solid fa-user-lock",
            "tone": "danger",
        },
        {
            "label": _("Login-Sperre"),
            "value": _("Aktiv") if access_settings.login_registration_locked else _("Aus"),
            "icon": "fa-solid fa-door-closed" if access_settings.login_registration_locked else "fa-solid fa-door-open",
            "tone": "danger" if access_settings.login_registration_locked else "success",
        },
        {
            "label": _("Tool-Regeln"),
            "value": restricted_tool_count,
            "icon": "fa-solid fa-sliders",
            "tone": "danger" if restricted_tool_count else "success",
        },
    ]

    context = {
        "query": query,
        "stats": stats,
        "reports": reports[:12],
        "feedback_items": feedback_items[:12],
        "file_shares": file_shares[:12],
        "blocks": blocks[:10],
        "recent_users": users,
        "inbox_logs": inbox_logs[:14],
        "audit_logs": audit_logs[:16],
        "suspensions": suspensions[:10],
        "feedback_status_choices": ToolFeedback.STATUS_CHOICES,
        "total_share_size": _human_size(total_share_size),
        "public_share_count": FileShare.objects.filter(is_public_link=True).count(),
        "inactive_user_count": User.objects.filter(is_active=False).count(),
        "block_count": UserBlock.objects.count(),
        "active_suspension_count": active_suspension_count,
        "access_settings": access_settings,
        "tool_access_items": tool_access_items,
        "tool_access_choices": SiteAccessSettings.TOOL_ACCESS_CHOICES,
    }
    return render(request, "app/moderation.html", context)


@staff_required
@require_POST
def moderation_access_toggle_view(request):
    access_settings = SiteAccessSettings.get_solo()
    lock_enabled = request.POST.get("login_registration_locked") == "1"
    lock_message = request.POST.get("lock_message", "").strip()[:240]

    access_settings.login_registration_locked = lock_enabled
    access_settings.lock_message = lock_message
    access_settings.updated_by = request.user
    access_settings.save(update_fields=["login_registration_locked", "lock_message", "updated_by", "updated_at"])

    _audit(
        request,
        ModerationAuditLog.ACTION_ACCESS_LOCKED if lock_enabled else ModerationAuditLog.ACTION_ACCESS_UNLOCKED,
        "Login und Registrierung gesperrt" if lock_enabled else "Login und Registrierung entsperrt",
        metadata={"lock_message": lock_message},
    )

    if lock_enabled:
        messages.success(request, _("Login und Registrierung sind jetzt für normale Nutzer gesperrt."))
    else:
        messages.success(request, _("Login und Registrierung sind wieder freigegeben."))
    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_tool_access_view(request):
    access_settings = SiteAccessSettings.get_solo()
    rules = {}

    for key in ACCESS_CONTROL_KEYS:
        level = request.POST.get(f"access_{key}", SiteAccessSettings.TOOL_ACCESS_ALL)
        rules[key] = level

    previous_rules = access_settings.tool_access_rules if isinstance(access_settings.tool_access_rules, dict) else {}
    access_settings.set_tool_access_rules(rules)
    access_settings.updated_by = request.user
    access_settings.save(update_fields=["tool_access_rules", "updated_by", "updated_at"])

    _audit(
        request,
        ModerationAuditLog.ACTION_TOOL_ACCESS_UPDATED,
        "Tool- und Spielzugriffe aktualisiert",
        metadata={
            "before": previous_rules,
            "after": access_settings.tool_access_rules,
        },
    )
    messages.success(request, _("Tool- und Spielzugriffe wurden aktualisiert."))
    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_report_action_view(request, report_id):
    report = get_object_or_404(UserReport, id=report_id)
    action = request.POST.get("action")
    if action == "reopen":
        report.is_resolved = False
        audit_action = ModerationAuditLog.ACTION_REPORT_REOPENED
        audit_summary = f"Meldung #{report.id} wieder geoeffnet"
        messages.success(request, _("Meldung wurde wieder geöffnet."))
    else:
        report.is_resolved = True
        audit_action = ModerationAuditLog.ACTION_REPORT_RESOLVED
        audit_summary = f"Meldung #{report.id} erledigt"
        messages.success(request, _("Meldung wurde erledigt."))
    report.save(update_fields=["is_resolved"])
    _audit(request, audit_action, audit_summary, target_user=report.reported, metadata={"report_id": report.id})
    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_feedback_status_view(request, feedback_id):
    feedback = get_object_or_404(ToolFeedback, id=feedback_id)
    status = request.POST.get("status")
    valid_statuses = {choice[0] for choice in ToolFeedback.STATUS_CHOICES}
    if status not in valid_statuses:
        messages.error(request, _("Ungültiger Feedback-Status."))
        return redirect(_safe_next(request))

    feedback.status = status
    feedback.save(update_fields=["status", "updated_at"])
    _audit(
        request,
        ModerationAuditLog.ACTION_FEEDBACK_STATUS,
        f"Feedback #{feedback.id} auf {status} gesetzt",
        target_user=feedback.user,
        metadata={"feedback_id": feedback.id, "status": status},
    )
    messages.success(request, _("Feedback-Status wurde aktualisiert."))
    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_file_share_delete_view(request, share_id):
    share = get_object_or_404(FileShare, id=share_id)
    owner = share.owner
    original_name = share.original_name
    if share.file:
        share.file.delete(save=False)
    share.delete()
    _audit(
        request,
        ModerationAuditLog.ACTION_FILE_DELETED,
        f"Datei-Freigabe geloescht: {original_name}",
        target_user=owner,
        metadata={"share_id": share_id, "original_name": original_name},
    )
    messages.success(request, _("Datei-Freigabe wurde gelöscht."))
    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_media_optimize_view(request):
    stats = _optimize_existing_media_files()
    summary = _optimization_summary(stats)

    _audit(
        request,
        ModerationAuditLog.ACTION_MEDIA_OPTIMIZED,
        f"Medien komprimiert: {summary['converted']} Dateien, {summary['human_saved']} gespart",
        metadata=summary,
    )

    if stats["converted"]:
        messages.success(
            request,
            _("%(count)s Bilder wurden zu WebP komprimiert. Gespart: %(saved)s.") % {
                "count": stats["converted"],
                "saved": summary["human_saved"],
            },
        )
    else:
        messages.info(request, _("Keine weiteren Bilder mussten komprimiert werden."))

    if stats["missing"] or stats["failed"]:
        messages.warning(
            request,
            _("Hinweis: %(missing)s Dateien fehlen im Speicher, %(failed)s konnten nicht verarbeitet werden.") % {
                "missing": stats["missing"],
                "failed": stats["failed"],
            },
        )

    return redirect(_safe_next(request))


@staff_required
@require_POST
def moderation_user_status_view(request, user_id):
    User = get_user_model()
    target_user = get_object_or_404(User, id=user_id)
    action = request.POST.get("action")

    if action not in {"activate", "deactivate", "suspend", "unsuspend"}:
        messages.error(request, _("Ungültige Nutzeraktion."))
        return redirect(_safe_next(request))

    if target_user == request.user and action in {"deactivate", "suspend"}:
        messages.error(request, _("Du kannst deinen eigenen Account hier nicht deaktivieren."))
        return redirect(_safe_next(request))

    if target_user.is_superuser and not request.user.is_superuser and action in {"deactivate", "suspend"}:
        messages.error(request, _("Nur Superuser können Superuser deaktivieren."))
        return redirect(_safe_next(request))

    if (
        target_user.is_superuser
        and action in {"deactivate", "suspend"}
        and not User.objects.filter(is_active=True, is_superuser=True).exclude(id=target_user.id).exists()
    ):
        messages.error(request, _("Der letzte aktive Superuser kann nicht deaktiviert werden."))
        return redirect(_safe_next(request))

    if action == "suspend":
        duration_hours = request.POST.get("duration_hours", "24")
        try:
            duration_hours = max(1, min(int(duration_hours), 24 * 365))
        except (TypeError, ValueError):
            duration_hours = 24
        reason = request.POST.get("reason", "").strip()[:240]
        now = timezone.now()
        UserSuspension.objects.filter(
            user=target_user,
            is_active=True,
            ends_at__gt=now,
        ).update(is_active=False, lifted_at=now, lifted_by=request.user)
        suspension = UserSuspension.objects.create(
            user=target_user,
            moderator=request.user,
            reason=reason,
            starts_at=now,
            ends_at=now + timezone.timedelta(hours=duration_hours),
        )
        _audit(
            request,
            ModerationAuditLog.ACTION_USER_SUSPENDED,
            f"{target_user.username} für {duration_hours} Stunden gesperrt",
            target_user=target_user,
            metadata={"duration_hours": duration_hours, "reason": reason, "suspension_id": suspension.id},
        )
        messages.success(request, _("Nutzer wurde gesperrt."))
        return redirect(_safe_next(request))

    if action == "unsuspend":
        now = timezone.now()
        updated = UserSuspension.objects.filter(
            user=target_user,
            is_active=True,
            ends_at__gt=now,
        ).update(is_active=False, lifted_at=now, lifted_by=request.user)
        _audit(
            request,
            ModerationAuditLog.ACTION_USER_UNSUSPENDED,
            f"Sperre für {target_user.username} aufgehoben",
            target_user=target_user,
            metadata={"updated": updated},
        )
        messages.success(request, _("Nutzersperre wurde aufgehoben."))
        return redirect(_safe_next(request))

    target_user.is_active = action == "activate"
    target_user.save(update_fields=["is_active"])
    _audit(
        request,
        ModerationAuditLog.ACTION_USER_ACTIVATED if target_user.is_active else ModerationAuditLog.ACTION_USER_DEACTIVATED,
        f"{target_user.username} {'aktiviert' if target_user.is_active else 'deaktiviert'}",
        target_user=target_user,
        metadata={"action": action},
    )

    if target_user.is_active:
        messages.success(request, _("Nutzer wurde aktiviert."))
    else:
        messages.success(request, _("Nutzer wurde deaktiviert."))
    return redirect(_safe_next(request))
