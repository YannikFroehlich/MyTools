import base64
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .models import UserProfile
from .profile_forms import ProfileForm

User = get_user_model()


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

    return render(request, "app/profile.html", {
        "form": form,
        "profile": profile,
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

    profiles = (
        UserProfile.objects
        .select_related("user")
        .filter(user__in=users)
        .order_by("user__username")
    )

    return render(request, "app/users.html", {
        "profiles": profiles,
        "query": query,
        "total_users": User.objects.filter(is_active=True).count(),
    })


@login_required
def public_profile_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)

    return render(request, "app/public_profile.html", {
        "profile_user": profile_user,
        "profile": profile,
    })