from django import forms
from django.utils.translation import gettext_lazy as _

from ..models import ToolFeedback
from ..platform_utils import get_feedback_tool_choices, get_feedback_tool_keys


class ToolFeedbackForm(forms.ModelForm):
    tool_key = forms.ChoiceField(
        label=_("Tool"),
        required=False,
        choices=[],
        widget=forms.Select(attrs={"class": "platform-input"}),
    )

    class Meta:
        model = ToolFeedback
        fields = ["tool_key", "feedback_type", "rating", "title", "message"]
        labels = {
            "feedback_type": _("Art"),
            "rating": _("Bewertung"),
            "title": _("Titel"),
            "message": _("Beschreibung"),
        }
        widgets = {
            "feedback_type": forms.Select(attrs={"class": "platform-input"}),
            "rating": forms.NumberInput(attrs={"class": "platform-input", "min": 0, "max": 5}),
            "title": forms.TextInput(attrs={"class": "platform-input", "placeholder": _("Kurz zusammenfassen...")}),
            "message": forms.Textarea(attrs={
                "class": "platform-textarea",
                "rows": 6,
                "placeholder": _("Was ist dir aufgefallen oder was wünschst du dir?"),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        choices = list(get_feedback_tool_choices())
        if not choices:
            choices = [("general", _("Allgemein"))]

        self.fields["tool_key"].choices = choices
        self.fields["rating"].required = False

        # Falls die Seite mit ?tool=xyz aufgerufen wird und xyz nicht mehr existiert,
        # soll die Selectbox trotzdem sauber auf "Allgemein" fallen.
        current_value = self.initial.get("tool_key") or self.data.get("tool_key")
        valid_keys = {key for key, _label in choices}
        if current_value and current_value not in valid_keys:
            self.initial["tool_key"] = "general"

    def clean_tool_key(self):
        tool_key = self.cleaned_data.get("tool_key") or "general"
        if tool_key not in get_feedback_tool_keys():
            return "general"
        return tool_key

    def clean_rating(self):
        rating = self.cleaned_data.get("rating") or 0
        return max(0, min(5, int(rating)))
