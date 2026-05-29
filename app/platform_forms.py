from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ToolFeedback
from .platform_utils import TOOL_CATALOG


class ToolFeedbackForm(forms.ModelForm):
    class Meta:
        model = ToolFeedback
        fields = ["tool_key", "feedback_type", "rating", "title", "message"]
        labels = {
            "tool_key": _("Tool"),
            "feedback_type": _("Art"),
            "rating": _("Bewertung"),
            "title": _("Titel"),
            "message": _("Beschreibung"),
        }
        widgets = {
            "tool_key": forms.Select(attrs={"class": "platform-input"}),
            "feedback_type": forms.Select(attrs={"class": "platform-input"}),
            "rating": forms.NumberInput(attrs={"class": "platform-input", "min": 0, "max": 5}),
            "title": forms.TextInput(attrs={"class": "platform-input", "placeholder": _("Kurz zusammenfassen...")}),
            "message": forms.Textarea(attrs={"class": "platform-textarea", "rows": 6, "placeholder": _("Was ist dir aufgefallen oder was wünschst du dir?")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tool_key"].choices = [("", _("Allgemein"))] + [(tool["key"], tool["label"]) for tool in TOOL_CATALOG]
        self.fields["rating"].required = False

    def clean_rating(self):
        rating = self.cleaned_data.get("rating") or 0
        return max(0, min(5, int(rating)))
