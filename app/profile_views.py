import base64
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import ChatRoom, Friendship, HumanBenchmarkHighScore, HumanBenchmarkScore, InboxItem, ProfileGalleryImage, SkribbleStats, UserBlock, UserProfile, UserReport
from .profile_forms import ProfileForm, ProfileGalleryImageForm, UserReportForm
from .presence_utils import decorate_profiles_with_presence, decorate_users_with_presence

User = get_user_model()


def get_profile_human_benchmark_highscores(user):
    highscores = {
        highscore.game: highscore
        for highscore in HumanBenchmarkHighScore.objects.filter(user=user)
    }

    return [
        {
            "game": game,
            "label": label,
            "highscore": highscores.get(game),
        }
        for game, label in HumanBenchmarkScore.GAME_CHOICES
    ]


def get_friend_users(user):
    friend_ids = Friendship.friend_ids_for_user(user)

    if not friend_ids:
        return User.objects.none()

    return User.objects.filter(id__in=friend_ids, is_active=True).order_by("username")


def get_friend_profiles(user, limit=None):
    friendships = list(Friendship.accepted_for_user(user))

    if not friendships:
        return []

    friend_ids = []
    friendship_since_by_user_id = {}

    for friendship in friendships:
        friend_user = friendship.other_user(user)

        if not friend_user or not friend_user.is_active:
            continue

        friend_ids.append(friend_user.id)
        friendship_since_by_user_id[friend_user.id] = friendship.updated_at

    if not friend_ids:
        return []

    friends = list(
        User.objects
        .filter(id__in=friend_ids, is_active=True)
        .order_by("username")
    )

    if limit:
        friends = friends[:limit]

    ensure_profiles_for_users(friends)

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user__in=friends)
        .order_by("user__username")
    )
    decorate_profiles_with_presence(profiles)

    for profile in profiles:
        profile.friendship_since = friendship_since_by_user_id.get(profile.user_id)

    return profiles


def can_view_private_profile_area(viewer, profile_user):
    return viewer.is_authenticated and (viewer == profile_user or get_friendship_state(viewer, profile_user) == "friends")


def apply_profile_privacy(profile, viewer):
    owner = profile.user
    is_self = viewer.is_authenticated and viewer == owner
    is_friend = viewer.is_authenticated and get_friendship_state(viewer, owner) == "friends"
    if not (is_self or is_friend) and not profile.privacy_show_online:
        profile.is_online = False
        profile.last_seen_at = None
        profile.activity_status = ""
    if profile.status == UserProfile.STATUS_INVISIBLE and not is_self:
        profile.is_online = False
        profile.last_seen_at = None
        profile.activity_status = ""
    return profile


def get_friend_activity(profile_user, viewer):
    if not can_view_private_profile_area(viewer, profile_user):
        return []
    activity = []
    recent_chat_count = ChatRoom.objects.filter(room_memberships__user=profile_user).distinct().count()
    if recent_chat_count:
        activity.append({"icon": "fa-solid fa-comments", "label": _("Aktive Chats"), "value": recent_chat_count})
    score_count = HumanBenchmarkHighScore.objects.filter(user=profile_user).count()
    if score_count:
        activity.append({"icon": "fa-solid fa-trophy", "label": _("Highscores"), "value": score_count})
    return activity


def get_friendship_state(viewer, profile_user):
    if not viewer.is_authenticated or viewer == profile_user:
        return "self" if viewer == profile_user else "none"

    friendship = Friendship.between(viewer, profile_user)

    if not friendship:
        return "none"

    if friendship.status == Friendship.STATUS_ACCEPTED:
        return "friends"

    if friendship.from_user_id == viewer.id:
        return "pending_sent"

    return "pending_received"


def is_blocked_between(user_a, user_b):
    if not user_a.is_authenticated or user_a == user_b:
        return False
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        if form.is_valid():
            old_avatar = profile.avatar
            old_profile_banner = profile.profile_banner
            profile = form.save(commit=False)

            cropped_avatar = request.POST.get("avatar_cropped", "").strip()

            if cropped_avatar.startswith("data:image"):
                try:
                    format_part, image_data = cropped_avatar.split(";base64,")
                    extension = format_part.split("/")[-1].lower()

                    if extension == "jpeg":
                        extension = "jpg"

                    file_name = f"profile_{request.user.id}_{uuid.uuid4().hex}.{extension}"
                    decoded_file = base64.b64decode(image_data)

                    if profile.avatar:
                        profile.avatar.delete(save=False)

                    profile.avatar.save(
                        file_name,
                        ContentFile(decoded_file),
                        save=False,
                    )
                except Exception:
                    messages.error(request, _("Das Profilbild konnte nicht verarbeitet werden."))
                    return redirect("profile")
            elif request.FILES.get("avatar") and old_avatar and old_avatar != profile.avatar:
                old_avatar.delete(save=False)

            if request.FILES.get("profile_banner") and old_profile_banner and old_profile_banner != profile.profile_banner:
                old_profile_banner.delete(save=False)

            # Profil speichern
            profile.save()

            # User-Daten speichern:
            # Vorname, Nachname, E-Mail und Benutzername liegen NICHT im UserProfile,
            # sondern direkt im Django-User.
            request.user.username = form.cleaned_data.get("username", "").strip()
            request.user.first_name = form.cleaned_data.get("first_name", "").strip()
            request.user.last_name = form.cleaned_data.get("last_name", "").strip()
            request.user.email = form.cleaned_data.get("email", "").strip()

            request.user.save(update_fields=[
                "username",
                "first_name",
                "last_name",
                "email",
            ])

            messages.success(request, _("Dein Profil wurde gespeichert."))
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    incoming_requests = (
        Friendship.objects
        .select_related("from_user", "from_user__profile")
        .filter(to_user=request.user, status=Friendship.STATUS_PENDING)
        .order_by("-created_at")
    )
    outgoing_requests = (
        Friendship.objects
        .select_related("to_user", "to_user__profile")
        .filter(from_user=request.user, status=Friendship.STATUS_PENDING)
        .order_by("-created_at")
    )
    friends_count = Friendship.accepted_for_user(request.user).count()
    chat_rooms_count = ChatRoom.objects.filter(room_memberships__user=request.user).distinct().count()
    total_highscores_count = HumanBenchmarkHighScore.objects.filter(user=request.user).count()

    return render(request, "app/profile.html", {
        "form": form,
        "profile": profile,
        "benchmark_highscores": get_profile_human_benchmark_highscores(request.user),
        "incoming_friend_requests": incoming_requests,
        "outgoing_friend_requests": outgoing_requests,
        "friends_preview": get_friend_profiles(request.user, limit=6),
        "friends_count": friends_count,
        "chat_rooms_count": chat_rooms_count,
        "total_highscores_count": total_highscores_count,
        "gallery_form": ProfileGalleryImageForm(),
        "gallery_images": ProfileGalleryImage.objects.filter(user=request.user)[:12],
        "blocked_users": UserBlock.objects.select_related("blocked", "blocked__profile").filter(blocker=request.user)[:20],
    })


def ensure_profiles_for_users(users):
    existing_profile_user_ids = set(
        UserProfile.objects
        .filter(user__in=users)
        .values_list("user_id", flat=True)
    )

    profiles_to_create = [
        UserProfile(user=user)
        for user in users
        if user.id not in existing_profile_user_ids
    ]

    if profiles_to_create:
        UserProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)


@login_required
def users_view(request):
    query = request.GET.get("q", "").strip()

    blocked_ids = set(UserBlock.objects.filter(blocker=request.user).values_list("blocked_id", flat=True))
    blocked_ids |= set(UserBlock.objects.filter(blocked=request.user).values_list("blocker_id", flat=True))
    users_qs = User.objects.filter(is_active=True).exclude(id__in=blocked_ids)

    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__bio__icontains=query)
        ).distinct()

    users = list(users_qs.order_by("username"))
    ensure_profiles_for_users(users)

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user__in=users)
        .order_by("user__username")
    )

    decorate_profiles_with_presence(profiles)

    for profile in profiles:
        profile.friendship_state = get_friendship_state(request.user, profile.user)
        apply_profile_privacy(profile, request.user)
        profile.activity_summary = get_friend_activity(profile.user, request.user)

    return render(request, "app/users.html", {
        "profiles": profiles,
        "query": query,
        "total_users": User.objects.filter(is_active=True).count(),
    })


@login_required
def public_profile_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    decorate_users_with_presence([profile_user])
    profile.is_online = getattr(profile_user, "is_online", False)
    profile.last_seen_at = getattr(profile_user, "last_seen_at", None)
    profile.activity_status = getattr(profile_user, "activity_status", "")
    apply_profile_privacy(profile, request.user)
    blocked_by_viewer = UserBlock.objects.filter(blocker=request.user, blocked=profile_user).exists()
    viewer_blocked = UserBlock.objects.filter(blocker=profile_user, blocked=request.user).exists()
    friends_count = Friendship.accepted_for_user(profile_user).count()
    chat_rooms_count = ChatRoom.objects.filter(room_memberships__user=profile_user).distinct().count()
    total_highscores_count = HumanBenchmarkHighScore.objects.filter(user=profile_user).count()

    return render(request, "app/public_profile.html", {
        "profile_user": profile_user,
        "profile": profile,
        "benchmark_highscores": get_profile_human_benchmark_highscores(profile_user) if profile.privacy_show_highscores or can_view_private_profile_area(request.user, profile_user) else [],
        "friendship_state": get_friendship_state(request.user, profile_user),
        "friends_preview": get_friend_profiles(profile_user, limit=6) if profile.privacy_show_friends or can_view_private_profile_area(request.user, profile_user) else [],
        "can_view_friends": profile.privacy_show_friends or can_view_private_profile_area(request.user, profile_user),
        "can_use_chat_button": profile.privacy_show_chat_button or can_view_private_profile_area(request.user, profile_user),
        "friend_activity": get_friend_activity(profile_user, request.user),
        "friends_count": friends_count,
        "chat_rooms_count": chat_rooms_count,
        "total_highscores_count": total_highscores_count,
        "blocked_by_viewer": blocked_by_viewer,
        "viewer_blocked": viewer_blocked,
        "report_form": UserReportForm(),
        "gallery_images": ProfileGalleryImage.objects.filter(user=profile_user, is_public=True)[:12] if not viewer_blocked else [],
        "skribble_stats": SkribbleStats.objects.filter(user=profile_user).first(),
    })


@login_required
def friends_list_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    if not (profile.privacy_show_friends or can_view_private_profile_area(request.user, profile_user)):
        messages.info(request, _("Diese Freundesliste ist privat."))
        return redirect("public_profile", user_id=profile_user.id)
    friends = get_friend_profiles(profile_user)
    for friend_profile in friends:
        apply_profile_privacy(friend_profile, request.user)
        friend_profile.activity_summary = get_friend_activity(friend_profile.user, request.user)

    return render(request, "app/friends.html", {
        "profile_user": profile_user,
        "profile": profile,
        "friends": friends,
        "friends_count": Friendship.accepted_for_user(profile_user).count(),
    })


@login_required
@require_POST
def friendship_action_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    action = request.POST.get("action", "").strip()
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"

    if target_user == request.user:
        messages.error(request, _("Du kannst dir selbst keine Freundschaftsanfrage senden."))
        return redirect(next_url)

    if is_blocked_between(request.user, target_user):
        messages.error(request, _("Diese Aktion ist wegen einer Blockierung nicht möglich."))
        return redirect(next_url)

    friendship = Friendship.between(request.user, target_user)

    if action == "send":
        if friendship:
            if friendship.status == Friendship.STATUS_ACCEPTED:
                messages.info(request, _("Ihr seid bereits befreundet."))
            elif friendship.from_user_id == request.user.id:
                messages.info(request, _("Deine Freundschaftsanfrage ist bereits offen."))
            else:
                friendship.status = Friendship.STATUS_ACCEPTED
                friendship.save(update_fields=["status", "updated_at"])
                messages.success(request, _("Freundschaftsanfrage angenommen."))
        else:
            Friendship.objects.create(from_user=request.user, to_user=target_user)
            target_profile, _created = UserProfile.objects.get_or_create(user=target_user)
            muted_by_dnd = target_profile.status == UserProfile.STATUS_DND and target_profile.dnd_silence_notifications
            if target_profile.notify_friend_requests and not muted_by_dnd:
                InboxItem.objects.create(
                    user=target_user,
                    item_type=InboxItem.TYPE_FRIEND,
                    title=_("Neue Freundschaftsanfrage"),
                    message=f"{request.user.username} möchte dich hinzufügen.",
                    target_url=reverse("profile") + "#friend-requests",
                    icon="fa-solid fa-user-plus",
                )
            messages.success(request, _("Freundschaftsanfrage gesendet."))

    elif action == "accept":
        if friendship and friendship.to_user_id == request.user.id and friendship.status == Friendship.STATUS_PENDING:
            friendship.status = Friendship.STATUS_ACCEPTED
            friendship.save(update_fields=["status", "updated_at"])
            messages.success(request, _("Freundschaftsanfrage angenommen."))
        else:
            messages.error(request, _("Diese Freundschaftsanfrage konnte nicht angenommen werden."))

    elif action in ["decline", "cancel"]:
        if friendship and friendship.status == Friendship.STATUS_PENDING:
            if action == "decline" and friendship.to_user_id != request.user.id:
                messages.error(request, _("Diese Freundschaftsanfrage kannst du nicht ablehnen."))
            elif action == "cancel" and friendship.from_user_id != request.user.id:
                messages.error(request, _("Diese Freundschaftsanfrage kannst du nicht zurückziehen."))
            else:
                friendship.delete()
                messages.success(request, _("Freundschaftsanfrage entfernt."))
        else:
            messages.error(request, _("Es gibt keine offene Freundschaftsanfrage."))

    elif action == "remove":
        if friendship and friendship.status == Friendship.STATUS_ACCEPTED:
            friendship.delete()
            messages.success(request, _("Freundschaft entfernt."))
        else:
            messages.error(request, _("Ihr seid aktuell nicht befreundet."))

    else:
        messages.error(request, _("Unbekannte Freundschafts-Aktion."))

    return redirect(next_url)


@login_required
@require_POST
def profile_gallery_upload_view(request):
    form = ProfileGalleryImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save(commit=False)
        image.user = request.user
        image.save()
        messages.success(request, _("Galeriebild hochgeladen."))
    else:
        messages.error(request, _("Das Galeriebild konnte nicht hochgeladen werden."))
    return redirect("profile")


@login_required
@require_POST
def delete_gallery_image_view(request, image_id):
    image = get_object_or_404(ProfileGalleryImage, id=image_id, user=request.user)
    image.image.delete(save=False)
    image.delete()
    messages.success(request, _("Galeriebild gelöscht."))
    return redirect("profile")


@login_required
@require_POST
def block_user_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"
    if target_user == request.user:
        messages.error(request, _("Du kannst dich nicht selbst blockieren."))
        return redirect(next_url)
    action = request.POST.get("action", "block")
    if action == "unblock":
        UserBlock.objects.filter(blocker=request.user, blocked=target_user).delete()
        messages.success(request, _("Blockierung aufgehoben."))
    else:
        UserBlock.objects.get_or_create(blocker=request.user, blocked=target_user)
        Friendship.objects.filter(Q(from_user=request.user, to_user=target_user) | Q(from_user=target_user, to_user=request.user)).delete()
        messages.success(request, _("Nutzer blockiert."))
    return redirect(next_url)


@login_required
@require_POST
def report_user_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"
    if target_user == request.user:
        messages.error(request, _("Du kannst dich nicht selbst melden."))
        return redirect(next_url)
    form = UserReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.reporter = request.user
        report.reported = target_user
        report.save()
        messages.success(request, _("Meldung wurde gespeichert."))
    else:
        messages.error(request, _("Die Meldung konnte nicht gespeichert werden."))
    return redirect(next_url)
