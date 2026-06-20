from datetime import timedelta

from django.utils import timezone

from .models import FileShare, HomeWidget, Note, Shortcut


TRASH_RETENTION_DAYS = 30

TRASH_TYPES = {
    "note": {"model": Note, "owner_field": "user"},
    "file": {"model": FileShare, "owner_field": "owner"},
    "widget": {"model": HomeWidget, "owner_field": "user"},
    "shortcut": {"model": Shortcut, "owner_field": "user"},
}


def deleted_items_for(item_type, user=None):
    spec = TRASH_TYPES.get(item_type)
    if not spec:
        return None

    queryset = spec["model"].all_objects.filter(deleted_at__isnull=False)
    if user is not None:
        queryset = queryset.filter(**{spec["owner_field"]: user})
    return queryset


def purge_expired_trash(*, user=None, now=None, dry_run=False):
    cutoff = (now or timezone.now()) - timedelta(days=TRASH_RETENTION_DAYS)
    deleted_count = 0

    for item_type in TRASH_TYPES:
        queryset = deleted_items_for(item_type, user).filter(deleted_at__lte=cutoff)
        if dry_run:
            deleted_count += queryset.count()
            continue

        # Instanzweise löschen, damit Dateien und Shortcut-Bilder aus dem
        # Storage ebenfalls entfernt werden.
        for item in queryset.iterator():
            item.delete()
            deleted_count += 1

    return deleted_count
