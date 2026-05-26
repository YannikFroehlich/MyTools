from django.conf import settings

from .permissions import get_note_access


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }


def note_access(request):
    return {
        "note_access": get_note_access(request.user),
    }
