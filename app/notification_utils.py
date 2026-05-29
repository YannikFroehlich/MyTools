from .models import ChatMessage, ChatRoomMember, DrawingGameInvite, Friendship


def get_notification_counts(user):
    """Return all small header notification counters for the current user."""
    counts = {
        "unread_chat_messages": 0,
        "incoming_friend_requests": 0,
        "skribble_invites": 0,
        "total_notifications": 0,
    }

    if not getattr(user, "is_authenticated", False):
        return counts

    try:
        counts["incoming_friend_requests"] = Friendship.objects.filter(
            to_user=user,
            status=Friendship.STATUS_PENDING,
        ).count()
    except Exception:
        counts["incoming_friend_requests"] = 0

    try:
        counts["skribble_invites"] = DrawingGameInvite.objects.filter(
            to_user=user,
            status=DrawingGameInvite.STATUS_PENDING,
        ).count()
    except Exception:
        counts["skribble_invites"] = 0

    try:
        unread_count = 0
        memberships = ChatRoomMember.objects.filter(user=user).select_related("room")

        for membership in memberships:
            unread_qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user)

            if membership.last_read_at:
                unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)

            unread_count += unread_qs.count()

        counts["unread_chat_messages"] = unread_count
    except Exception:
        counts["unread_chat_messages"] = 0

    counts["total_notifications"] = (
        counts["unread_chat_messages"]
        + counts["incoming_friend_requests"]
        + counts["skribble_invites"]
    )

    return counts
