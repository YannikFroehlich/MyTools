from django.urls import reverse
from django.utils.translation import gettext_lazy as _

TOOL_CATALOG = [
    {"key": "home", "label": _("Start"), "icon": "fa-solid fa-house", "url_name": "home", "category": _("Alltag")},
    {"key": "weather", "label": _("Wetter"), "icon": "fa-solid fa-cloud-sun", "url_name": "weather", "category": _("Alltag")},
    {"key": "chat", "label": _("Chat"), "icon": "fa-solid fa-comments", "url_name": "chat", "category": _("Kommunikation")},
    {"key": "users", "label": _("Nutzer"), "icon": "fa-solid fa-users", "url_name": "users", "category": _("Kommunikation")},
    {"key": "notes", "label": _("Notizen"), "icon": "fa-regular fa-note-sticky", "url_name": "notes", "category": _("Alltag")},
    {"key": "clock", "label": _("Uhr"), "icon": "fa-regular fa-clock", "url_name": "clock", "category": _("Alltag")},
    {"key": "skribble", "label": _("Skribble"), "icon": "fa-solid fa-pencil", "url_name": "skribble_home", "category": _("Spiele")},
    {"key": "uno", "label": _("Uno"), "icon": "fa-solid fa-layer-group", "url_name": "uno_home", "category": _("Spiele")},
    {"key": "hangman", "label": _("Hangman"), "icon": "fa-solid fa-user-secret", "url_name": "hangman_home", "category": _("Spiele")},
    {"key": "human_benchmark", "label": _("Human Benchmark"), "icon": "fa-solid fa-stopwatch", "url_name": "human-benchmark", "category": _("Spiele")},
    {"key": "drift_circuit", "label": _("Racing Game"), "icon": "fa-solid fa-car-side", "url_name": "drift-circuit", "category": _("Spiele")},
    {"key": "unit_converter", "label": _("Einheitenrechner"), "icon": "fa-solid fa-calculator", "url_name": "unit_converter", "category": _("Tools")},
    {"key": "randomizer_tools", "label": _("Randomizer"), "icon": "fa-solid fa-shuffle", "url_name": "randomizer_tools", "category": _("Tools")},
    {"key": "genius_search", "label": _("Genius Search"), "icon": "fa-solid fa-music", "url_name": "genius-search", "category": _("Tools")},
    {"key": "avatar_wiki", "label": _("Avatar Wiki"), "icon": "fa-solid fa-wind", "url_name": "avatar-wiki", "category": _("Tools")},
    {"key": "stream_deck", "label": _("Stream Deck"), "icon": "fa-solid fa-table-cells-large", "url_name": "stream-deck", "category": _("Streaming")},
    {"key": "obs_dashboard", "label": _("OBS Dashboard"), "icon": "fa-solid fa-display", "url_name": "obs-dashboard", "category": _("Streaming")},
    {"key": "spritkosten", "label": _("Spritkosten"), "icon": "fa-solid fa-gas-pump", "url_name": "spritkostenrechner", "category": _("Alltag")},
]

# Extra Einträge nur für das Feedback-Formular.
# Diese Liste ist absichtlich unabhängig von TOOL_CATALOG, weil nicht jede Seite
# als startbares Tool auf der Favoriten-Seite auftauchen muss.
FEEDBACK_TOOL_CHOICES = [
    ("general", _("Allgemein")),
    ("home", _("Startseite / Widgets")),
    ("favorites", _("Favoriten")),
    ("inbox", _("Inbox / Benachrichtigungen")),
    ("feedback", _("Tool bewerten / Feedback")),
    ("profile", _("Profil")),
    ("users", _("Nutzer / Freunde")),
    ("chat", _("Chats")),
    ("skribble", _("Skribble")),
    ("uno", _("Uno")),
    ("hangman", _("Hangman")),
    ("human_benchmark", _("Human Benchmark")),
    ("weather", _("Wetter")),
    ("notes", _("Notizen")),
    ("clock", _("Uhr")),
    ("unit_converter", _("Einheitenrechner")),
    ("randomizer_tools", _("Randomizer")),
    ("spritkosten", _("Spritkosten")),
    ("genius_search", _("Genius Search")),
    ("avatar_wiki", _("Avatar Wiki")),
    ("stream_deck", _("Stream Deck")),
    ("obs_dashboard", _("OBS Dashboard")),
    ("drift_circuit", _("Racing Game")),
    ("theme", _("Theme / Design")),
    ("notifications", _("Benachrichtigungseinstellungen")),
]


def get_feedback_tool_choices():
    return FEEDBACK_TOOL_CHOICES


def get_feedback_tool_keys():
    return {key for key, _label in FEEDBACK_TOOL_CHOICES}


def resolve_tools(request, favorite_keys=None):
    favorite_keys = set(favorite_keys or [])
    tools = []
    for tool in TOOL_CATALOG:
        item = dict(tool)
        item["url"] = reverse(item["url_name"])
        item["is_favorite"] = item["key"] in favorite_keys
        tools.append(item)
    return tools


def tool_by_key(key):
    return next((tool for tool in TOOL_CATALOG if tool["key"] == key), None)
