from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import ProfileGalleryImage, UserProfile, UserReport

User = get_user_model()
MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label=_("Vorname"),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": _("Dein Vorname"),
        }),
    )
    last_name = forms.CharField(
        label=_("Nachname"),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": _("Dein Nachname"),
        }),
    )
    email = forms.EmailField(
        label=_("E-Mail"),
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "profile-input",
            "placeholder": "deine@email.de",
        }),
    )
    username = forms.CharField(
        label=_("Benutzername"),
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": _("Benutzername"),
        }),
    )

    class Meta:
        model = UserProfile
        fields = ["avatar", "profile_banner", "bio", "status", "status_text", "privacy_show_online", "privacy_show_friends", "privacy_show_highscores", "privacy_show_chat_button", "notify_chat", "notify_friend_requests", "notify_skribble", "notify_game_invites", "notify_game_turns", "notify_file_shares", "notify_note_reminders", "notify_roadmap", "notify_achievements", "browser_notifications", "sound_notifications", "dnd_silence_notifications"]
        labels = {
            "avatar": _("Profilbild"),
            "profile_banner": _("Profilbanner"),
            "bio": _("Über mich"),
            "status": _("Status"),
            "status_text": _("Statustext"),
            "privacy_show_online": _("Online-Status öffentlich anzeigen"),
            "privacy_show_friends": _("Freundesliste öffentlich anzeigen"),
            "privacy_show_highscores": _("Highscores öffentlich anzeigen"),
            "privacy_show_chat_button": _("Chat-Button im Profil anzeigen"),
            "notify_chat": _("Chat-Benachrichtigungen"),
            "notify_friend_requests": _("Freundschaftsanfragen"),
            "notify_skribble": _("Skribble-Einladungen"),
            "notify_game_invites": _("Spiel-Einladungen"),
            "notify_game_turns": _("Spielzüge"),
            "notify_file_shares": _("Dateifreigaben"),
            "notify_note_reminders": _("Notiz-Erinnerungen"),
            "notify_roadmap": _("Roadmap-Updates"),
            "notify_achievements": _("Achievements"),
            "browser_notifications": _("Browser-Benachrichtigungen"),
            "sound_notifications": _("Sounds abspielen"),
            "dnd_silence_notifications": _("Bei Nicht stören stummschalten"),
        }
        widgets = {
            "avatar": forms.ClearableFileInput(attrs={
                "class": "profile-file-input",
                "accept": "image/*",
            }),
            "profile_banner": forms.ClearableFileInput(attrs={
                "class": "profile-file-input",
                "accept": "image/*",
            }),
            "bio": forms.Textarea(attrs={
                "class": "profile-textarea",
                "rows": 5,
                "placeholder": _("Schreibe kurz etwas über dich..."),
            }),
            "status": forms.Select(attrs={"class": "profile-input"}),
            "status_text": forms.TextInput(attrs={
                "class": "profile-input",
                "placeholder": _("z. B. Bin gerade am Zocken"),
            }),
            "privacy_show_online": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_friends": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_highscores": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_chat_button": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_chat": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_friend_requests": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_skribble": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_game_invites": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_game_turns": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_file_shares": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_note_reminders": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_roadmap": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "notify_achievements": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "browser_notifications": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "sound_notifications": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "dnd_silence_notifications": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        self.fields["username"].initial = self.user.username
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email
        self.fields["status"].required = False

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.exclude(pk=self.user.pk).filter(username=username).exists():
            raise forms.ValidationError(_("Dieser Benutzername ist bereits vergeben."))

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()

        if email and User.objects.exclude(pk=self.user.pk).filter(email=email).exists():
            raise forms.ValidationError(_("Diese E-Mail-Adresse wird bereits verwendet."))

        return email

    def clean_status(self):
        return self.cleaned_data.get("status") or getattr(self.instance, "status", "") or UserProfile.STATUS_ONLINE

    def clean_avatar(self):
        return self.clean_profile_image("avatar", _("Das Profilbild"))

    def clean_profile_banner(self):
        return self.clean_profile_image("profile_banner", _("Das Profilbanner"))

    def clean_profile_image(self, field_name, label):
        image = self.cleaned_data.get(field_name)

        if not image:
            return image

        if getattr(image, "size", 0) > MAX_PROFILE_IMAGE_SIZE:
            raise forms.ValidationError(_("%(label)s darf maximal 5 MB groß sein.") % {"label": label})

        content_type = getattr(image, "content_type", "")

        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError(_("%(label)s muss eine Bilddatei sein.") % {"label": label})

        return image

    def save(self, commit=True):
        profile = super().save(commit=False)

        self.user.username = self.cleaned_data["username"]
        self.user.first_name = self.cleaned_data.get("first_name", "")
        self.user.last_name = self.cleaned_data.get("last_name", "")
        self.user.email = self.cleaned_data.get("email", "")

        if commit:
            self.user.save()
            profile.save()

        return profile


class ProfileGalleryImageForm(forms.ModelForm):
    class Meta:
        model = ProfileGalleryImage
        fields = ["image", "caption", "is_public"]
        labels = {
            "image": _("Bild"),
            "caption": _("Beschreibung"),
            "is_public": _("Öffentlich sichtbar"),
        }
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "profile-file-input", "accept": "image/*"}),
            "caption": forms.TextInput(attrs={"class": "profile-input", "placeholder": _("Kurzer Bildtitel")}),
            "is_public": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and getattr(image, "size", 0) > MAX_PROFILE_IMAGE_SIZE:
            raise forms.ValidationError(_("Galeriebilder dürfen maximal 5 MB groß sein."))
        if image and getattr(image, "content_type", "") and not image.content_type.startswith("image/"):
            raise forms.ValidationError(_("Bitte lade eine Bilddatei hoch."))
        return image


class UserReportForm(forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ["reason", "message"]
        labels = {"reason": _("Grund"), "message": _("Nachricht")}
        widgets = {
            "reason": forms.Select(attrs={"class": "profile-input"}),
            "message": forms.Textarea(attrs={"class": "profile-textarea", "rows": 4, "placeholder": _("Beschreibe kurz, was passiert ist...")}),
        }
