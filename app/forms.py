from django import forms
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
                "placeholder": "Titel deiner Notiz..."
            }),
            "tags": forms.TextInput(attrs={
                "class": "notes-input",
                "placeholder": "Tags, z. B. Schule, Server, Idee"
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