from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage, ChatMessageReaction, ChatRoom, ChatRoomMember, Friendship, UserProfile
from .profile_views import ensure_profiles_for_users, get_friend_profiles
from .presence_utils import decorate_users_with_presence

User = get_user_model()


def user_payload(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "avatar_url": profile.avatar.url if profile.avatar else "",
        "initials": profile.initials,
    }


def room_queryset_for(user):
    return (
        ChatRoom.objects
        .filter(room_memberships__user=user)
        .prefetch_related("members", "members__profile")
        .annotate(last_message_at=Max("messages__created_at"), member_count=Count("members", distinct=True))
        .order_by("-last_message_at", "-updated_at")
        .distinct()
    )


def get_or_create_direct_room(current_user, target_user):
    direct_key = ChatRoom.direct_key_for_users(current_user, target_user)
    room, created = ChatRoom.objects.get_or_create(
        direct_key=direct_key,
        defaults={
            "room_type": ChatRoom.ROOM_DIRECT,
            "created_by": current_user,
        },
    )

    if created or not room.room_memberships.filter(user=current_user).exists():
        ChatRoomMember.objects.get_or_create(room=room, user=current_user, defaults={"is_admin": True})
    ChatRoomMember.objects.get_or_create(room=room, user=target_user)

    return room


def decorate_room(room, current_user):
    members = list(room.members.all())
    other_members = [member for member in members if member.id != current_user.id]
    room.display_title = room.title_for(current_user)
    room.other_members = other_members
    room.preview_members = other_members[:4]
    room.last_message = room.messages.select_related("sender").order_by("-created_at").first()
    unread_qs = room.messages.exclude(sender=current_user)
    membership = getattr(room, "current_membership", None)
    if membership and membership.last_read_at:
        unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)
    room.unread_count = unread_qs.count()
    return room


CHAT_REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🙏"]


def reaction_payload(message, current_user):
    grouped = {}
    for reaction in message.reactions.all():
        data = grouped.setdefault(reaction.emoji, {"emoji": reaction.emoji, "count": 0, "mine": False})
        data["count"] += 1
        if reaction.user_id == current_user.id:
            data["mine"] = True
    return list(grouped.values())


def decorate_message(message, current_user):
    message.reaction_items = reaction_payload(message, current_user)
    message.can_delete = message.sender_id == current_user.id
    return message


@login_required
def chat_view(request, room_id=None):
    rooms = list(room_queryset_for(request.user))
    memberships = {
        membership.room_id: membership
        for membership in ChatRoomMember.objects.filter(user=request.user, room__in=rooms)
    }

    all_room_members = []
    for room in rooms:
        room.current_membership = memberships.get(room.id)
        all_room_members.extend(list(room.members.all()))
    ensure_profiles_for_users(all_room_members)
    decorate_users_with_presence(all_room_members)

    for room in rooms:
        decorate_room(room, request.user)

    active_room = None
    if room_id:
        active_room = get_object_or_404(room_queryset_for(request.user), id=room_id)
    elif rooms:
        active_room = rooms[0]

    messages_qs = []
    active_room_members = []
    if active_room:
        active_room = decorate_room(active_room, request.user)
        messages_qs = list(
            active_room.messages
            .select_related("sender", "sender__profile")
            .prefetch_related("reactions")
            .order_by("created_at")[:150]
        )
        for message in messages_qs:
            decorate_message(message, request.user)
        active_room_members = list(active_room.members.select_related("profile").order_by("username"))
        ensure_profiles_for_users(active_room_members)
        decorate_users_with_presence(active_room_members)
        ChatRoomMember.objects.filter(room=active_room, user=request.user).update(last_read_at=timezone.now())

    friend_profiles = get_friend_profiles(request.user)

    return render(request, "app/chat.html", {
        "rooms": rooms,
        "active_room": active_room,
        "chat_messages": messages_qs,
        "active_room_members": active_room_members,
        "friend_profiles": friend_profiles,
    })


@login_required
@require_POST
def start_direct_chat(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)

    if target_user == request.user:
        messages.info(request, _("Das ist dein eigenes Profil."))
        return redirect("chat")

    friendship = Friendship.between(request.user, target_user)
    if not friendship or friendship.status != Friendship.STATUS_ACCEPTED:
        messages.error(request, _("Du kannst nur mit Freunden einen Direktchat starten."))
        return redirect("public_profile", user_id=target_user.id)

    room = get_or_create_direct_room(request.user, target_user)
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def create_group_chat(request):
    name = request.POST.get("name", "").strip()[:80]
    member_ids = request.POST.getlist("members")

    if not name:
        messages.error(request, _("Gib der Gruppe einen Namen."))
        return redirect("chat")

    allowed_friend_ids = set(Friendship.friend_ids_for_user(request.user))
    selected_ids = {int(member_id) for member_id in member_ids if member_id.isdigit()}
    selected_ids = selected_ids & allowed_friend_ids

    if not selected_ids:
        messages.error(request, _("Wähle mindestens einen Freund für die Gruppe aus."))
        return redirect("chat")

    room = ChatRoom.objects.create(
        room_type=ChatRoom.ROOM_GROUP,
        name=name,
        created_by=request.user,
    )
    ChatRoomMember.objects.create(room=room, user=request.user, is_admin=True, last_read_at=timezone.now())

    for user in User.objects.filter(id__in=selected_ids, is_active=True):
        ChatRoomMember.objects.get_or_create(room=room, user=user)

    ChatMessage.objects.create(
        room=room,
        sender=request.user,
        text=_("Gruppe erstellt."),
    )
    messages.success(request, _("Gruppe wurde erstellt."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def send_chat_message(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    text = request.POST.get("text", "").strip()

    if not text:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Nachricht darf nicht leer sein.")}, status=400)
        messages.error(request, _("Nachricht darf nicht leer sein."))
        return redirect("chat_room", room_id=room.id)

    message = ChatMessage.objects.create(room=room, sender=request.user, text=text[:1200])
    room.save(update_fields=["updated_at"])
    ChatRoomMember.objects.filter(room=room, user=request.user).update(last_read_at=timezone.now())

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": message_payload(message, request.user)})

    return redirect("chat_room", room_id=room.id)


def message_payload(message, current_user):
    sender_profile, _ = UserProfile.objects.get_or_create(user=message.sender)
    is_own = message.sender_id == current_user.id
    return {
        "id": message.id,
        "text": message.text,
        "created_at": timezone.localtime(message.created_at).strftime("%d.%m.%Y %H:%M"),
        "is_own": is_own,
        "delete_url": reverse("chat_message_delete", args=[message.room_id, message.id]) if is_own else "",
        "react_url": reverse("chat_message_react", args=[message.room_id, message.id]) if not is_own else "",
        "reactions": reaction_payload(message, current_user),
        "sender": {
            "id": message.sender_id,
            "username": message.sender.username,
            "display_name": message.sender.get_full_name() or message.sender.username,
            "avatar_url": sender_profile.avatar.url if sender_profile.avatar else "",
            "initials": sender_profile.initials,
        },
    }


@login_required
@require_GET
def chat_messages_api(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    after_id = request.GET.get("after")

    qs = room.messages.select_related("sender", "sender__profile").order_by("created_at")
    if after_id and after_id.isdigit():
        qs = qs.filter(id__gt=int(after_id))
    else:
        qs = qs.order_by("-created_at")[:80]
        qs = reversed(list(qs))

    qs = list(qs.prefetch_related("reactions")) if hasattr(qs, "prefetch_related") else list(qs)
    payload = [message_payload(message, request.user) for message in qs]

    visible_ids = {
        int(message_id)
        for message_id in request.GET.get("visible", "").split(",")
        if message_id.isdigit()
    }
    existing_visible_messages = []
    deleted_ids = []
    if visible_ids:
        existing_visible_messages = list(
            room.messages
            .filter(id__in=visible_ids)
            .select_related("sender", "sender__profile")
            .prefetch_related("reactions")
        )
        existing_ids = {message.id for message in existing_visible_messages}
        deleted_ids = sorted(visible_ids - existing_ids)

    updates = [
        {"id": message.id, "reactions": reaction_payload(message, request.user)}
        for message in existing_visible_messages
    ]

    ChatRoomMember.objects.filter(room=room, user=request.user).update(last_read_at=timezone.now())
    return JsonResponse({"ok": True, "messages": payload, "deleted_ids": deleted_ids, "updates": updates})


@login_required
@require_POST
def delete_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, room=room, sender=request.user)
    message.delete()
    room.save(update_fields=["updated_at"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "deleted_id": message_id})

    messages.success(request, _("Nachricht wurde gelöscht."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def react_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(
        ChatMessage.objects.select_related("sender").prefetch_related("reactions"),
        id=message_id,
        room=room,
    )

    if message.sender_id == request.user.id:
        return JsonResponse({"ok": False, "error": _("Auf eigene Nachrichten kannst du hier nicht reagieren.")}, status=400)

    emoji = request.POST.get("emoji", "").strip()
    if emoji not in CHAT_REACTION_EMOJIS:
        return JsonResponse({"ok": False, "error": _("Diese Reaktion ist nicht erlaubt.")}, status=400)

    existing = ChatMessageReaction.objects.filter(message=message, user=request.user).first()
    if existing and existing.emoji == emoji:
        existing.delete()
    elif existing:
        existing.emoji = emoji
        existing.save(update_fields=["emoji", "updated_at"])
    else:
        ChatMessageReaction.objects.create(message=message, user=request.user, emoji=emoji)

    message = ChatMessage.objects.prefetch_related("reactions").get(id=message.id)
    return JsonResponse({"ok": True, "message_id": message.id, "reactions": reaction_payload(message, request.user)})
