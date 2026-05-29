from django.utils import timezone

from .models import UserPresence

ONLINE_WINDOW_MINUTES = 3
TOUCH_THROTTLE_SECONDS = 45


def touch_user_presence(user):
    if not getattr(user, "is_authenticated", False):
        return

    now = timezone.now()
    try:
        presence, created = UserPresence.objects.get_or_create(user=user)
        if created or presence.last_seen <= now - timezone.timedelta(seconds=TOUCH_THROTTLE_SECONDS):
            presence.last_seen = now
            presence.save(update_fields=["last_seen"])
    except Exception:
        pass


def online_cutoff():
    return timezone.now() - timezone.timedelta(minutes=ONLINE_WINDOW_MINUTES)


def decorate_users_with_presence(users):
    user_list = list(users)
    ids = [user.id for user in user_list if getattr(user, "id", None)]
    presences = {
        presence.user_id: presence
        for presence in UserPresence.objects.filter(user_id__in=ids)
    }
    cutoff = online_cutoff()

    for user in user_list:
        presence = presences.get(user.id)
        user.is_online = bool(presence and presence.last_seen >= cutoff)
        user.last_seen_at = presence.last_seen if presence else None

    return user_list


def decorate_profiles_with_presence(profiles):
    profile_list = list(profiles)
    decorate_users_with_presence([profile.user for profile in profile_list])
    for profile in profile_list:
        profile.is_online = getattr(profile.user, "is_online", False)
        profile.last_seen_at = getattr(profile.user, "last_seen_at", None)
    return profile_list
