from django import forms
from django.contrib.auth import get_user_model

from .models import UserProfile

User = get_user_model()


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
        fields = ["avatar", "bio"]
        labels = {
            "avatar": "Profilbild",
            "bio": "Über mich",
        }
        widgets = {
            "avatar": forms.ClearableFileInput(attrs={
                "class": "profile-file-input",
                "accept": "image/*",
            }),
            "bio": forms.Textarea(attrs={
                "class": "profile-textarea",
                "rows": 5,
                "placeholder": "Schreibe kurz etwas über dich...",
            }),
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