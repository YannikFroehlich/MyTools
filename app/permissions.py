from django.core.exceptions import ObjectDoesNotExist


NOTE_PERMISSION_FIELDS = {
    "view": "can_view_notes",
    "create": "can_create_notes",
    "edit": "can_edit_notes",
    "delete": "can_delete_notes",
    "pin": "can_pin_notes",
    "archive": "can_archive_notes",
}


def get_note_access(user):
    access = {
        "can_view_notes": True,
        "can_create_notes": True,
        "can_edit_notes": True,
        "can_delete_notes": True,
        "can_pin_notes": True,
        "can_archive_notes": True,
    }

    if not getattr(user, "is_authenticated", False):
        return access

    if getattr(user, "is_superuser", False):
        return access

    try:
        permissions = user.note_permissions
    except ObjectDoesNotExist:
        return access

    for field in access:
        access[field] = getattr(permissions, field)

    return access


def user_can_access_notes(user, action):
    field = NOTE_PERMISSION_FIELDS[action]
    return get_note_access(user)[field]
