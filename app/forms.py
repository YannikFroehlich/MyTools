from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import bleach
from bleach.css_sanitizer import CSSSanitizer

from .models import Friendship, Note


ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "blockquote",
    "code",
    "pre",
    "span",
    "a",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "ul": ["class"],
    "ol": ["class"],
    "li": ["class", "data-checked"],
    "span": ["style"],
    "p": ["style"],
    "h2": ["style"],
    "h3": ["style"],
}

ALLOWED_CSS_PROPERTIES = [
    "font-size",
    "text-align",
]

NOTE_COLOR_CHOICES = [
    ("blue", _("Blau")),
    ("purple", _("Lila")),
    ("green", _("Grün")),
    ("orange", _("Orange")),
    ("red", _("Rot")),
    ("gray", _("Grau")),
]


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label=_("E-Mail"),
        error_messages={
            "required": _("Bitte gib eine E-Mail-Adresse ein."),
            "invalid": _("Bitte gib eine gültige E-Mail-Adresse ein."),
        },
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": _("E-Mail-Adresse"),
            "required": "required",
        }),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Diese E-Mail-Adresse wird bereits verwendet."))

        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "placeholder": _("Benutzername"),
        })
        self.fields["password1"].widget.attrs.update({
            "autocomplete": "new-password",
            "placeholder": _("Passwort"),
        })
        self.fields["password2"].widget.attrs.update({
            "autocomplete": "new-password",
            "placeholder": _("Passwort wiederholen"),
        })


class NoteForm(forms.ModelForm):
    content = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={
            "id": "id_content",
        })
    )
    reminder_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "class": "notes-input",
                "type": "datetime-local",
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )
    shared_with = forms.ModelMultipleChoiceField(
        required=False,
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Note
        fields = [
            "title",
            "content",
            "tags",
            "reminder_at",
            "shared_with",
            "color",
            "is_pinned",
            "is_archived",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "notes-input",
                "placeholder": _("Titel deiner Notiz...")
            }),
            "tags": forms.TextInput(attrs={
                "class": "notes-input",
                "placeholder": _("Tags, z. B. Schule, Server, Idee")
            }),
            "color": forms.Select(attrs={
                "class": "notes-select"
            }),
            "is_pinned": forms.CheckboxInput(attrs={
                "class": "notes-checkbox"
            }),
            "is_archived": forms.CheckboxInput(attrs={
                "class": "notes-checkbox"
            }),
        }

        labels = {
            "title": _("Titel"),
            "content": _("Inhalt"),
            "tags": _("Tags"),
            "reminder_at": _("Erinnerung"),
            "shared_with": _("Mit Freunden teilen"),
            "color": _("Farbe"),
            "is_pinned": _("Anpinnen"),
            "is_archived": _("Archivieren"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["color"].choices = NOTE_COLOR_CHOICES
        self.fields["title"].widget.attrs["placeholder"] = _("Titel deiner Notiz...")
        self.fields["tags"].widget.attrs["placeholder"] = _("Tags, z. B. Schule, Server, Idee")
        self.fields["reminder_at"].widget.attrs["placeholder"] = _("Datum und Uhrzeit")

        if self.user and self.user.is_authenticated:
            friend_ids = Friendship.friend_ids_for_user(self.user)
            self.fields["shared_with"].queryset = User.objects.filter(
                id__in=friend_ids,
                is_active=True,
            ).order_by("username")

    def clean_content(self):
        content = self.cleaned_data.get("content", "")

        css_sanitizer = CSSSanitizer(
            allowed_css_properties=ALLOWED_CSS_PROPERTIES
        )

        cleaned_content = bleach.clean(
            content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=["http", "https", "mailto"],
            strip=True,
            css_sanitizer=css_sanitizer,
        )

        return cleaned_content
