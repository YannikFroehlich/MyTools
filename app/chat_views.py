import re

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

from .chat_forms import ChatGroupSettingsForm
from .models import (
    ChatAttachment,
    ChatMessage,
    ChatMessageReaction,
    ChatMessageRead,
    ChatRoom,
    ChatRoomMember,
    ChatTypingStatus,
    Friendship,
    InboxItem,
    UserBlock,
    UserProfile,
)
from .profile_views import ensure_profiles_for_users, get_friend_profiles
from .notification_utils import invalidate_notification_cache
from .presence_utils import decorate_users_with_presence
from .realtime import broadcast_chat_event

User = get_user_model()


def user_payload(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "avatar_url": media_thumbnail_url(profile.avatar, "avatar-small"),
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

    if users_blocked_between(current_user, target_user):
        raise PermissionError("blocked")

    if created or not room.room_memberships.filter(user=current_user).exists():
        ChatRoomMember.objects.get_or_create(room=room, user=current_user, defaults={"is_admin": True})
    ChatRoomMember.objects.get_or_create(room=room, user=target_user)

    return room


def users_blocked_between(user_a, user_b):
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


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
MAX_CHAT_ATTACHMENT_SIZE = 8 * 1024 * 1024
CHAT_THEME_VALUES = {choice[0] for choice in ChatRoom.THEME_CHOICES}
MENTION_RE = re.compile(r"@([\w.@+-]{1,150})")


def attachment_payload(attachment):
    return {
        "id": attachment.id,
        "name": attachment.filename,
        "url": attachment.file.url if attachment.file else "",
        "preview_url": media_thumbnail_url(attachment.file, "preview") if attachment.is_image else "",
        "content_type": attachment.content_type,
        "size": attachment.size,
        "is_image": attachment.is_image,
    }


def media_thumbnail_url(file_field, spec):
    if not file_field:
        return ""
    return reverse("media_thumbnail", kwargs={"spec": spec, "source": file_field.name})


def chat_day_label(value):
    local_day = timezone.localtime(value).date()
    today = timezone.localdate()
    if local_day == today:
        return _("Heute")
    if local_day == today - timezone.timedelta(days=1):
        return _("Gestern")
    return timezone.localtime(value).strftime("%d.%m.%Y")


def sender_profile_payload(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "profile_url": reverse("public_profile", args=[user.id]),
        "avatar_url": media_thumbnail_url(profile.avatar, "avatar-small"),
        "initials": profile.initials,
        "bio": profile.bio[:140],
        "status": profile.get_status_display(),
        "status_text": profile.status_text,
    }


def reaction_payload(message, current_user):
    grouped = {}
    for reaction in message.reactions.all():
        data = grouped.setdefault(reaction.emoji, {"emoji": reaction.emoji, "count": 0, "mine": False})
        data["count"] += 1
        if reaction.user_id == current_user.id:
            data["mine"] = True
    return list(grouped.values())


def mentioned_users_for_text(text, room, sender):
    usernames = {match.group(1).lower() for match in MENTION_RE.finditer(text or "")}
    if not usernames:
        return User.objects.none()
    query = Q()
    for username in usernames:
        query |= Q(username__iexact=username)
    return room.members.filter(query, is_active=True).exclude(id=sender.id)


def notify_mentions(message):
    mentioned_users = list(mentioned_users_for_text(message.text, message.room, message.sender))
    if not mentioned_users:
        return []

    target_url = reverse("chat_room", args=[message.room_id])
    for mentioned_user in mentioned_users:
        profile, _created = UserProfile.objects.get_or_create(user=mentioned_user)
        muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications
        if profile.notify_chat and not muted_by_dnd:
            InboxItem.objects.create(
                user=mentioned_user,
                item_type=InboxItem.TYPE_CHAT,
                title=_("Du wurdest erwaehnt"),
                message=_("%(user)s hat dich im Chat erwaehnt.") % {"user": message.sender.username},
                target_url=target_url,
                icon="fa-solid fa-at",
            )
    return mentioned_users


def typing_payload(room, current_user):
    cutoff = timezone.now() - timezone.timedelta(seconds=7)
    typing_users = (
        ChatTypingStatus.objects
        .filter(room=room, is_typing=True, updated_at__gte=cutoff)
        .exclude(user=current_user)
        .select_related("user")
        .order_by("-updated_at")[:4]
    )
    return [
        {
            "id": typing.user_id,
            "username": typing.user.username,
            "display_name": typing.user.get_full_name() or typing.user.username,
        }
        for typing in typing_users
    ]


def decorate_message(message, current_user):
    message.reaction_items = reaction_payload(message, current_user)
    message.can_delete = message.sender_id == current_user.id
    message.read_label = read_label_for_message(message, current_user)
    message.day_key = timezone.localtime(message.created_at).strftime("%Y-%m-%d")
    message.day_label = chat_day_label(message.created_at)
    message.sender_profile_payload = sender_profile_payload(message.sender)
    return message


def pinned_message_for(room, current_user):
    if not room or not room.pinned_message_id:
        return None
    message = (
        ChatMessage.objects
        .filter(id=room.pinned_message_id, room=room)
        .select_related("sender", "sender__profile")
        .prefetch_related("reactions", "attachments", "read_receipts")
        .first()
    )
    return decorate_message(message, current_user) if message else None


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
        chat_query = request.GET.get("q", "").strip()
        message_queryset = (
            active_room.messages
            .select_related("sender", "sender__profile")
            .prefetch_related("reactions", "attachments", "read_receipts")
            .order_by("created_at")
        )
        if chat_query:
            message_queryset = message_queryset.filter(
                Q(text__icontains=chat_query) | Q(sender__username__icontains=chat_query)
            )
        messages_qs = list(message_queryset[:150])
        for message in messages_qs:
            decorate_message(message, request.user)
        active_room_members = list(active_room.members.select_related("profile").order_by("username"))
        ensure_profiles_for_users(active_room_members)
        decorate_users_with_presence(active_room_members)
        active_membership = ChatRoomMember.objects.filter(room=active_room, user=request.user).first()
        active_room.current_user_is_admin = bool(active_membership and active_membership.is_admin)
        active_room.settings_form = ChatGroupSettingsForm(user=request.user, room=active_room, instance=active_room) if active_room.room_type == ChatRoom.ROOM_GROUP and active_room.current_user_is_admin else None
        active_room.pinned_chat_message = pinned_message_for(active_room, request.user)
        ChatRoomMember.objects.filter(room=active_room, user=request.user).update(last_read_at=timezone.now())
        mark_room_messages_read(active_room, request.user)

    friend_profiles = get_friend_profiles(request.user)

    return render(request, "app/chat.html", {
        "rooms": rooms,
        "active_room": active_room,
        "chat_messages": messages_qs,
        "active_room_members": active_room_members,
        "friend_profiles": friend_profiles,
        "chat_query": request.GET.get("q", "").strip(),
        "chat_theme_choices": ChatRoom.THEME_CHOICES,
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

    try:
        room = get_or_create_direct_room(request.user, target_user)
    except PermissionError:
        messages.error(request, _("Dieser Chat ist wegen einer Blockierung nicht möglich."))
        return redirect("public_profile", user_id=target_user.id)
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
    blocked_ids = set(UserBlock.objects.filter(blocker=request.user).values_list("blocked_id", flat=True)) | set(UserBlock.objects.filter(blocked=request.user).values_list("blocker_id", flat=True))
    selected_ids = (selected_ids & allowed_friend_ids) - blocked_ids

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
        InboxItem.objects.create(
            user=user,
            item_type=InboxItem.TYPE_CHAT,
            title=_("Neue Chatgruppe"),
            message=_("Du wurdest zu einer neuen Gruppe hinzugefügt."),
            target_url=reverse("chat_room", args=[room.id]),
            icon="fa-solid fa-user-group",
        )

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
    uploaded_files = request.FILES.getlist("attachments") or request.FILES.getlist("attachment")

    if not text and not uploaded_files:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Nachricht darf nicht leer sein.")}, status=400)
        messages.error(request, _("Nachricht darf nicht leer sein."))
        return redirect("chat_room", room_id=room.id)

    for uploaded_file in uploaded_files:
        if uploaded_file.size > MAX_CHAT_ATTACHMENT_SIZE:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": _("Der Anhang darf maximal 8 MB gross sein.")}, status=400)
            messages.error(request, _("Der Anhang darf maximal 8 MB gross sein."))
            return redirect("chat_room", room_id=room.id)

    message = ChatMessage.objects.create(room=room, sender=request.user, text=text[:1200])
    for uploaded_file in uploaded_files:
        ChatAttachment.objects.create(
            message=message,
            file=uploaded_file,
            original_name=uploaded_file.name[:255],
            content_type=getattr(uploaded_file, "content_type", "") or "",
            size=uploaded_file.size,
        )

    room.save(update_fields=["updated_at"])
    ChatTypingStatus.objects.update_or_create(
        room=room,
        user=request.user,
        defaults={"is_typing": False},
    )
    ChatRoomMember.objects.filter(room=room, user=request.user).update(last_read_at=timezone.now())
    mentioned_users = notify_mentions(message)
    mentioned_user_ids = {user.id for user in mentioned_users}
    room_members = list(room.members.select_related("profile"))
    for member in room_members:
        if member.id == request.user.id:
            continue
        if member.id in mentioned_user_ids:
            continue
        member_profile, _created = UserProfile.objects.get_or_create(user=member)
        muted_by_dnd = member_profile.status == UserProfile.STATUS_DND and member_profile.dnd_silence_notifications
        if member_profile.notify_chat and not muted_by_dnd:
            InboxItem.objects.create(
                user=member,
                item_type=InboxItem.TYPE_CHAT,
                title=_("Neue Chatnachricht"),
                message=(text[:120] if text else _("Neuer Anhang")),
                target_url=reverse("chat_room", args=[room.id]),
                icon="fa-solid fa-comments",
            )

    for member in room_members:
        invalidate_notification_cache(member)
    broadcast_chat_event(room.id, "message_created", message_id=message.id)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        message = (
            ChatMessage.objects
            .select_related("room", "sender", "sender__profile")
            .prefetch_related("reactions", "attachments", "read_receipts")
            .get(id=message.id)
        )
        return JsonResponse({"ok": True, "message": message_payload(message, request.user, room.pinned_message_id)})

    return redirect("chat_room", room_id=room.id)

def mark_room_messages_read(room, user):
    unread_messages = list(room.messages.exclude(sender=user).exclude(read_receipts__user=user)[:200])
    if not unread_messages:
        return False
    ChatMessageRead.objects.bulk_create(
        [ChatMessageRead(message=message, user=user) for message in unread_messages],
        ignore_conflicts=True,
    )
    return True


def read_label_for_message(message, current_user):
    if message.sender_id != current_user.id:
        return ""
    other_member_count = message.room.members.exclude(id=current_user.id).count()
    if other_member_count <= 0:
        return ""
    read_count = message.read_receipts.exclude(user=current_user).count()
    if read_count >= other_member_count:
        return _("Gelesen")
    if read_count > 0:
        return _("Gelesen von %(count)s") % {"count": read_count}
    return _("Gesendet")


def message_payload(message, current_user, pinned_message_id=None):
    sender_payload = sender_profile_payload(message.sender)
    is_own = message.sender_id == current_user.id
    if pinned_message_id is None:
        pinned_message_id = getattr(message.room, "pinned_message_id", None)
    return {
        "id": message.id,
        "text": message.text,
        "created_at": timezone.localtime(message.created_at).strftime("%d.%m.%Y %H:%M"),
        "day_key": timezone.localtime(message.created_at).strftime("%Y-%m-%d"),
        "day_label": chat_day_label(message.created_at),
        "edited_at": timezone.localtime(message.edited_at).strftime("%d.%m.%Y %H:%M") if message.edited_at else "",
        "is_edited": bool(message.edited_at),
        "is_own": is_own,
        "is_pinned": message.id == pinned_message_id,
        "delete_url": reverse("chat_message_delete", args=[message.room_id, message.id]) if is_own else "",
        "edit_url": reverse("chat_message_edit", args=[message.room_id, message.id]) if is_own else "",
        "pin_url": reverse("chat_message_pin", args=[message.room_id, message.id]),
        "react_url": reverse("chat_message_react", args=[message.room_id, message.id]),
        "read_label": read_label_for_message(message, current_user) if is_own else "",
        "reactions": reaction_payload(message, current_user),
        "attachments": [attachment_payload(attachment) for attachment in message.attachments.all()],
        "sender": sender_payload,
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

    qs = list(qs.prefetch_related("reactions", "attachments", "read_receipts")) if hasattr(qs, "prefetch_related") else list(qs)
    payload = [message_payload(message, request.user, room.pinned_message_id) for message in qs]

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
            .prefetch_related("reactions", "attachments", "read_receipts")
        )
        existing_ids = {message.id for message in existing_visible_messages}
        deleted_ids = sorted(visible_ids - existing_ids)

    updates = [
        {
            "id": message.id,
            "text": message.text,
            "edited_at": timezone.localtime(message.edited_at).strftime("%d.%m.%Y %H:%M") if message.edited_at else "",
            "is_edited": bool(message.edited_at),
            "reactions": reaction_payload(message, request.user),
            "read_label": read_label_for_message(message, request.user),
            "is_pinned": message.id == room.pinned_message_id,
        }
        for message in existing_visible_messages
    ]

    ChatRoomMember.objects.filter(room=room, user=request.user).update(last_read_at=timezone.now())
    if mark_room_messages_read(room, request.user):
        invalidate_notification_cache(request.user)
    pinned_message = pinned_message_for(room, request.user)
    return JsonResponse({
        "ok": True,
        "messages": payload,
        "deleted_ids": deleted_ids,
        "updates": updates,
        "pinned_message": message_payload(pinned_message, request.user, room.pinned_message_id) if pinned_message else None,
        "typing_users": typing_payload(room, request.user),
    })


@login_required
@require_POST
def delete_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, room=room, sender=request.user)
    message.delete()
    room.save(update_fields=["updated_at"])
    for member in room.members.all():
        invalidate_notification_cache(member)
    broadcast_chat_event(room.id, "message_deleted", message_id=message_id)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "deleted_id": message_id})

    messages.success(request, _("Nachricht wurde gelöscht."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def edit_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(
        ChatMessage.objects.select_related("sender").prefetch_related("reactions", "attachments", "read_receipts"),
        id=message_id,
        room=room,
        sender=request.user,
    )
    text = request.POST.get("text", "").strip()[:1200]
    if not text:
        return JsonResponse({"ok": False, "error": _("Nachricht darf nicht leer sein.")}, status=400)

    message.text = text
    message.edited_at = timezone.now()
    message.save(update_fields=["text", "edited_at"])
    room.save(update_fields=["updated_at"])
    notify_mentions(message)
    message = (
        ChatMessage.objects
        .select_related("room", "sender", "sender__profile")
        .prefetch_related("reactions", "attachments", "read_receipts")
        .get(id=message.id)
    )
    for member in room.members.all():
        invalidate_notification_cache(member)
    broadcast_chat_event(room.id, "message_updated", message_id=message.id)
    return JsonResponse({"ok": True, "message": message_payload(message, request.user, room.pinned_message_id)})


@login_required
@require_POST
def chat_typing_api(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    is_typing = request.POST.get("is_typing", "true") == "true"
    ChatTypingStatus.objects.update_or_create(
        room=room,
        user=request.user,
        defaults={"is_typing": is_typing},
    )
    broadcast_chat_event(room.id, "typing")
    return JsonResponse({"ok": True, "typing_users": typing_payload(room, request.user)})


@login_required
@require_POST
def react_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(
        ChatMessage.objects.select_related("sender").prefetch_related("reactions", "attachments", "read_receipts"),
        id=message_id,
        room=room,
    )


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

    message = ChatMessage.objects.prefetch_related("reactions", "attachments", "read_receipts").get(id=message.id)
    broadcast_chat_event(room.id, "reaction_updated", message_id=message.id)
    return JsonResponse({"ok": True, "message_id": message.id, "reactions": reaction_payload(message, request.user)})


@login_required
@require_POST
def pin_chat_message(request, room_id, message_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    message = get_object_or_404(
        ChatMessage.objects.select_related("sender", "sender__profile").prefetch_related("reactions", "attachments", "read_receipts"),
        id=message_id,
        room=room,
    )
    should_unpin = request.POST.get("action") == "unpin" or room.pinned_message_id == message.id
    room.pinned_message = None if should_unpin else message
    room.save(update_fields=["pinned_message", "updated_at"])
    broadcast_chat_event(room.id, "pinned_updated")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        pinned_message = pinned_message_for(room, request.user)
        return JsonResponse({
            "ok": True,
            "message_id": message.id,
            "is_pinned": not should_unpin,
            "pinned_message": message_payload(pinned_message, request.user, room.pinned_message_id) if pinned_message else None,
        })

    messages.success(request, _("Nachricht wurde angepinnt.") if not should_unpin else _("Angeheftete Nachricht wurde entfernt."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def set_chat_theme(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_memberships__user=request.user)
    theme = request.POST.get("theme", ChatRoom.THEME_DEFAULT).strip()
    if theme not in CHAT_THEME_VALUES:
        messages.error(request, _("Dieses Chat-Theme gibt es nicht."))
        return redirect("chat_room", room_id=room.id)

    room.theme = theme
    room.save(update_fields=["theme", "updated_at"])
    messages.success(request, _("Chat-Theme gespeichert."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def chat_group_settings_view(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_type=ChatRoom.ROOM_GROUP, room_memberships__user=request.user)
    membership = get_object_or_404(ChatRoomMember, room=room, user=request.user)
    if not membership.is_admin:
        messages.error(request, _("Nur Gruppenadmins können die Gruppe bearbeiten."))
        return redirect("chat_room", room_id=room.id)

    form = ChatGroupSettingsForm(request.POST, request.FILES, user=request.user, room=room, instance=room)
    if form.is_valid():
        form.save()
        for user in form.cleaned_data.get("members_to_add", []):
            ChatRoomMember.objects.get_or_create(room=room, user=user)
            InboxItem.objects.create(
                user=user,
                item_type=InboxItem.TYPE_CHAT,
                title=_("Zur Gruppe hinzugefügt"),
                message=room.name or _("Neue Chatgruppe"),
                target_url=reverse("chat_room", args=[room.id]),
                icon="fa-solid fa-user-group",
            )
        messages.success(request, _("Gruppeneinstellungen gespeichert."))
    else:
        messages.error(request, _("Die Gruppeneinstellungen konnten nicht gespeichert werden."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def chat_group_member_action_view(request, room_id, user_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_type=ChatRoom.ROOM_GROUP, room_memberships__user=request.user)
    actor_membership = get_object_or_404(ChatRoomMember, room=room, user=request.user)
    if not actor_membership.is_admin:
        messages.error(request, _("Nur Gruppenadmins können Mitglieder verwalten."))
        return redirect("chat_room", room_id=room.id)
    target_membership = get_object_or_404(ChatRoomMember, room=room, user_id=user_id)
    action = request.POST.get("action", "").strip()
    if target_membership.user_id == request.user.id:
        messages.error(request, _("Du kannst dich hier nicht selbst entfernen."))
    elif action == "promote":
        target_membership.is_admin = True
        target_membership.save(update_fields=["is_admin"])
        messages.success(request, _("Mitglied ist jetzt Gruppenadmin."))
    elif action == "remove":
        target_membership.delete()
        messages.success(request, _("Mitglied entfernt."))
    else:
        messages.error(request, _("Unbekannte Gruppenaktion."))
    return redirect("chat_room", room_id=room.id)


@login_required
@require_POST
def chat_group_leave_view(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id, room_type=ChatRoom.ROOM_GROUP, room_memberships__user=request.user)
    membership = get_object_or_404(ChatRoomMember, room=room, user=request.user)
    if room.room_memberships.count() <= 1:
        room.delete()
        messages.success(request, _("Gruppe gelöscht."))
        return redirect("chat")
    membership.delete()
    if not room.room_memberships.filter(is_admin=True).exists():
        first_member = room.room_memberships.order_by("joined_at").first()
        if first_member:
            first_member.is_admin = True
            first_member.save(update_fields=["is_admin"])
    messages.success(request, _("Du hast die Gruppe verlassen."))
    return redirect("chat")
