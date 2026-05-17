from django.conf import settings


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }
