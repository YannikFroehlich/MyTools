import math
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import HomeWidget, Shortcut, ShortcutSection
from ..trash_utils import TRASH_RETENTION_DAYS, TRASH_TYPES, deleted_items_for, purge_expired_trash


TRASH_PRESENTATION = {
    "note": {"label": _("Notiz"), "icon": "fa-regular fa-note-sticky", "color": "blue"},
    "file": {"label": _("Datei"), "icon": "fa-regular fa-file", "color": "purple"},
    "widget": {"label": _("Widget"), "icon": "fa-solid fa-table-cells-large", "color": "green"},
    "shortcut": {"label": _("Verknüpfung"), "icon": "fa-solid fa-link", "color": "orange"},
}


def _owned_deleted_item(user, item_type, item_id):
    queryset = deleted_items_for(item_type, user)
    if queryset is None:
        return None
    return get_object_or_404(queryset, pk=item_id)


def _trash_card(item_type, item, now):
    presentation = TRASH_PRESENTATION[item_type]
    expires_at = item.deleted_at + timedelta(days=TRASH_RETENTION_DAYS)
    days_remaining = max(0, math.ceil((expires_at - now).total_seconds() / 86400))

    if item_type == "note":
        title = item.title or _("Unbenannte Notiz")
        subtitle = strip_tags(item.content or _("Ohne Inhalt")).strip()[:140]
    elif item_type == "file":
        title = item.original_name
        subtitle = _("%(size)s · %(downloads)s Downloads") % {
            "size": item.human_size,
            "downloads": item.download_count,
        }
    elif item_type == "widget":
        title = item.title
        subtitle = item.get_widget_type_display()
    else:
        title = item.name
        subtitle = item.url

    return {
        "id": item.pk,
        "type": item_type,
        "type_label": presentation["label"],
        "icon": presentation["icon"],
        "color": presentation["color"],
        "title": title,
        "subtitle": subtitle,
        "deleted_at": item.deleted_at,
        "expires_at": expires_at,
        "days_remaining": days_remaining,
    }


@login_required
def trash_view(request):
    purge_expired_trash(user=request.user)
    now = timezone.now()
    items = []
    counts = {}

    for item_type in TRASH_TYPES:
        queryset = deleted_items_for(item_type, request.user).order_by("-deleted_at", "-pk")
        counts[item_type] = queryset.count()
        items.extend(_trash_card(item_type, item, now) for item in queryset)

    items.sort(key=lambda item: item["deleted_at"], reverse=True)

    return render(request, "app/trash.html", {
        "trash_items": items,
        "trash_counts": counts,
        "trash_total": len(items),
        "retention_days": TRASH_RETENTION_DAYS,
    })


@login_required
@require_POST
@transaction.atomic
def trash_restore_view(request, item_type, item_id):
    item = _owned_deleted_item(request.user, item_type, item_id)
    if item is None:
        messages.error(request, _("Unbekannter Papierkorb-Eintrag."))
        return redirect("trash")

    if item_type == "widget":
        item.order = (HomeWidget.objects.filter(user=request.user).aggregate(Max("order"))["order__max"] or 0) + 1
        item.deleted_at = None
        item.save(update_fields=["order", "deleted_at"])
    elif item_type == "shortcut":
        section = item.section
        if not section or section.user_id != request.user.id:
            section, _created = ShortcutSection.objects.get_or_create(
                user=request.user,
                name="Verknüpfungen",
                defaults={"color": "blue", "order": 0},
            )
        item.section = section
        item.order = (
            Shortcut.objects.filter(user=request.user, section=section).aggregate(Max("order"))["order__max"] or 0
        ) + 1
        item.deleted_at = None
        item.save(update_fields=["section", "order", "deleted_at"])
    else:
        item.restore_from_trash()

    messages.success(request, _("Eintrag wurde wiederhergestellt."))
    return redirect("trash")


@login_required
@require_POST
def trash_delete_view(request, item_type, item_id):
    item = _owned_deleted_item(request.user, item_type, item_id)
    if item is None:
        messages.error(request, _("Unbekannter Papierkorb-Eintrag."))
        return redirect("trash")

    item.delete()
    messages.success(request, _("Eintrag wurde endgültig gelöscht."))
    return redirect("trash")


@login_required
@require_POST
def trash_empty_view(request):
    deleted_count = 0
    for item_type in TRASH_TYPES:
        for item in deleted_items_for(item_type, request.user).iterator():
            item.delete()
            deleted_count += 1

    if deleted_count:
        messages.success(request, _("Papierkorb wurde geleert."))
    else:
        messages.info(request, _("Der Papierkorb ist bereits leer."))
    return redirect("trash")
