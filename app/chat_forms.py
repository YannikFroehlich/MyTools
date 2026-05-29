from django import forms
from django.contrib.auth import get_user_model

from .models import ChatRoom, Friendship

User = get_user_model()


class ChatGroupSettingsForm(forms.ModelForm):
    members_to_add = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Freunde hinzufügen",
    )

    class Meta:
        model = ChatRoom
        fields = ["name", "description", "avatar", "members_to_add"]
        labels = {
            "name": "Gruppenname",
            "description": "Beschreibung",
            "avatar": "Gruppenbild",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "chat-settings-input", "placeholder": "Gruppenname"}),
            "description": forms.TextInput(attrs={"class": "chat-settings-input", "placeholder": "Kurze Beschreibung"}),
            "avatar": forms.ClearableFileInput(attrs={"class": "chat-settings-file", "accept": "image/*"}),
        }

    def __init__(self, *args, user=None, room=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.room = room or self.instance
        friend_ids = Friendship.friend_ids_for_user(user) if user and user.is_authenticated else []
        existing_ids = []
        if self.room and self.room.pk:
            existing_ids = list(self.room.members.values_list("id", flat=True))
        self.fields["members_to_add"].queryset = User.objects.filter(id__in=friend_ids, is_active=True).exclude(id__in=existing_ids).order_by("username")

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and getattr(avatar, "size", 0) > 5 * 1024 * 1024:
            raise forms.ValidationError("Das Gruppenbild darf maximal 5 MB groß sein.")
        if avatar and getattr(avatar, "content_type", "") and not avatar.content_type.startswith("image/"):
            raise forms.ValidationError("Das Gruppenbild muss eine Bilddatei sein.")
        return avatar
