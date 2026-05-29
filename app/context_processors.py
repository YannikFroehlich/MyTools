from django.conf import settings

from .models import Friendship, UserProfile


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }


def current_profile(request):
    if not request.user.is_authenticated:
        return {
            "current_profile": None,
            "incoming_friend_requests_count": 0,
        }

    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        profile = None

    try:
        incoming_friend_requests_count = Friendship.objects.filter(
            to_user=request.user,
            status=Friendship.STATUS_PENDING,
        ).count()
    except Exception:
        incoming_friend_requests_count = 0

    return {
        "current_profile": profile,
        "incoming_friend_requests_count": incoming_friend_requests_count,
    }
