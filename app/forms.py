from django import forms
from django.utils.translation import gettext_lazy as _
import bleach
from bleach.css_sanitizer import CSSSanitizer

from .models import Note


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


class NoteForm(forms.ModelForm):
    content = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={
            "id": "id_content",
        })
    )

    class Meta:
        model = Note
        fields = [
            "title",
            "content",
            "tags",
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
            "color": _("Farbe"),
            "is_pinned": _("Anpinnen"),
            "is_archived": _("Archivieren"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].choices = NOTE_COLOR_CHOICES
        self.fields["title"].widget.attrs["placeholder"] = _("Titel deiner Notiz...")
        self.fields["tags"].widget.attrs["placeholder"] = _("Tags, z. B. Schule, Server, Idee")

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
