import base64
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .models import UserProfile
from .profile_forms import ProfileForm


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

            profile.save()
            messages.success(request, _("Dein Profil wurde gespeichert."))
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    return render(request, "app/profile.html", {
        "form": form,
        "profile": profile,
    })