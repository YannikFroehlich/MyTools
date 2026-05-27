from django.conf import settings

from .models import UserProfile


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }


def current_profile(request):
    if not request.user.is_authenticated:
        return {
            "current_profile": None,
        }

    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        profile = None

    return {
        "current_profile": profile,
    }