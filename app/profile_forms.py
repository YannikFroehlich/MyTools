from django import forms
from django.contrib.auth import get_user_model

from .models import UserProfile

User = get_user_model()
MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Vorname",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": "Dein Vorname",
        }),
    )
    last_name = forms.CharField(
        label="Nachname",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": "Dein Nachname",
        }),
    )
    email = forms.EmailField(
        label="E-Mail",
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "profile-input",
            "placeholder": "deine@email.de",
        }),
    )
    username = forms.CharField(
        label="Benutzername",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "class": "profile-input",
            "placeholder": "Benutzername",
        }),
    )

    class Meta:
        model = UserProfile
        fields = ["avatar", "profile_banner", "bio", "status", "status_text", "privacy_show_online", "privacy_show_friends", "privacy_show_highscores", "privacy_show_chat_button"]
        labels = {
            "avatar": "Profilbild",
            "profile_banner": "Profilbanner",
            "bio": "Über mich",
            "status": "Status",
            "status_text": "Statustext",
            "privacy_show_online": "Online-Status öffentlich anzeigen",
            "privacy_show_friends": "Freundesliste öffentlich anzeigen",
            "privacy_show_highscores": "Highscores öffentlich anzeigen",
            "privacy_show_chat_button": "Chat-Button im Profil anzeigen",
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
                "placeholder": "Schreibe kurz etwas über dich...",
            }),
            "status": forms.Select(attrs={"class": "profile-input"}),
            "status_text": forms.TextInput(attrs={
                "class": "profile-input",
                "placeholder": "z. B. Bin gerade am Zocken",
            }),
            "privacy_show_online": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_friends": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_highscores": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
            "privacy_show_chat_button": forms.CheckboxInput(attrs={"class": "profile-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        self.fields["username"].initial = self.user.username
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.exclude(pk=self.user.pk).filter(username=username).exists():
            raise forms.ValidationError("Dieser Benutzername ist bereits vergeben.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()

        if email and User.objects.exclude(pk=self.user.pk).filter(email=email).exists():
            raise forms.ValidationError("Diese E-Mail-Adresse wird bereits verwendet.")

        return email

    def clean_avatar(self):
        return self.clean_profile_image("avatar", "Das Profilbild")

    def clean_profile_banner(self):
        return self.clean_profile_image("profile_banner", "Das Profilbanner")

    def clean_profile_image(self, field_name, label):
        image = self.cleaned_data.get(field_name)

        if not image:
            return image

        if getattr(image, "size", 0) > MAX_PROFILE_IMAGE_SIZE:
            raise forms.ValidationError(f"{label} darf maximal 5 MB groß sein.")

        content_type = getattr(image, "content_type", "")

        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError(f"{label} muss eine Bilddatei sein.")

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
