from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import ChatRoom, UserBlock


def users_blocked_between(user_a, user_b):
    if not user_a or not user_b:
        return False
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def blocked_user_ids_for(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    outgoing = UserBlock.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    incoming = UserBlock.objects.filter(blocked=user).values_list("blocker_id", flat=True)
    return set(outgoing).union(incoming)


def accessible_chat_rooms_for_user(user, queryset=None):
    queryset = queryset if queryset is not None else ChatRoom.objects.all()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    queryset = queryset.filter(room_memberships__user=user)
    blocked_ids = blocked_user_ids_for(user)
    if blocked_ids:
        queryset = queryset.exclude(
            Q(room_type=ChatRoom.ROOM_DIRECT)
            & Q(room_memberships__user_id__in=blocked_ids)
        )
    return queryset.distinct()


def user_can_access_chat_room(user, room):
    if not room or not getattr(user, "is_authenticated", False):
        return False
    return accessible_chat_rooms_for_user(user).filter(pk=room.pk).exists()


def get_accessible_chat_room_or_404(user, room_id, **filters):
    return get_object_or_404(
        accessible_chat_rooms_for_user(user).filter(**filters),
        id=room_id,
    )


def require_chat_room_access(user, room):
    if not user_can_access_chat_room(user, room):
        raise PermissionDenied
    return room
