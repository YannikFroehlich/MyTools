from django.conf import settings

from .models import ChatMessage, ChatRoomMember, Friendship, UserProfile


def fontawesome_kit(request):
    return {
        "fontawesome_kit_key": settings.FONTAWESOME_KIT_KEY,
    }


def current_profile(request):
    if not request.user.is_authenticated:
        return {
            "current_profile": None,
            "incoming_friend_requests_count": 0,
            "unread_chat_messages_count": 0,
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

    try:
        unread_chat_messages_count = 0
        memberships = ChatRoomMember.objects.filter(user=request.user).select_related("room")
        for membership in memberships:
            unread_qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=request.user)
            if membership.last_read_at:
                unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)
            unread_chat_messages_count += unread_qs.count()
    except Exception:
        unread_chat_messages_count = 0

    return {
        "current_profile": profile,
        "incoming_friend_requests_count": incoming_friend_requests_count,
        "unread_chat_messages_count": unread_chat_messages_count,
    }
