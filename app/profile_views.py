import base64
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Friendship, HumanBenchmarkHighScore, HumanBenchmarkScore, UserProfile
from .profile_forms import ProfileForm

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
    friends = get_friend_users(user)

    if limit:
        friends = friends[:limit]

    friends = list(friends)
    ensure_profiles_for_users(friends)

    return (
        UserProfile.objects
        .select_related("user")
        .filter(user__in=friends)
        .order_by("user__username")
    )


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

    return render(request, "app/profile.html", {
        "form": form,
        "profile": profile,
        "benchmark_highscores": get_profile_human_benchmark_highscores(request.user),
        "incoming_friend_requests": incoming_requests,
        "outgoing_friend_requests": outgoing_requests,
        "friends_preview": get_friend_profiles(request.user, limit=6),
        "friends_count": friends_count,
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

    users_qs = User.objects.filter(is_active=True)

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

    for profile in profiles:
        profile.friendship_state = get_friendship_state(request.user, profile.user)

    return render(request, "app/users.html", {
        "profiles": profiles,
        "query": query,
        "total_users": User.objects.filter(is_active=True).count(),
    })


@login_required
def public_profile_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    friends_count = Friendship.accepted_for_user(profile_user).count()

    return render(request, "app/public_profile.html", {
        "profile_user": profile_user,
        "profile": profile,
        "benchmark_highscores": get_profile_human_benchmark_highscores(profile_user),
        "friendship_state": get_friendship_state(request.user, profile_user),
        "friends_preview": get_friend_profiles(profile_user, limit=6),
        "friends_count": friends_count,
    })


@login_required
def friends_list_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    friends = get_friend_profiles(profile_user)

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
