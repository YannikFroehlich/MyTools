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
    {"key": "human_benchmark", "label": _("Human Benchmark"), "icon": "fa-solid fa-stopwatch", "url_name": "human-benchmark", "category": _("Spiele")},
    {"key": "drift_circuit", "label": _("Racing Game"), "icon": "fa-solid fa-car-side", "url_name": "drift-circuit", "category": _("Spiele")},
    {"key": "unit_converter", "label": _("Einheitenrechner"), "icon": "fa-solid fa-calculator", "url_name": "unit_converter", "category": _("Tools")},
    {"key": "genius_search", "label": _("Genius Search"), "icon": "fa-solid fa-music", "url_name": "genius-search", "category": _("Tools")},
    {"key": "avatar_wiki", "label": _("Avatar Wiki"), "icon": "fa-solid fa-wind", "url_name": "avatar-wiki", "category": _("Tools")},
    {"key": "stream_deck", "label": _("Stream Deck"), "icon": "fa-solid fa-table-cells-large", "url_name": "stream-deck", "category": _("Streaming")},
    {"key": "obs_dashboard", "label": _("OBS Dashboard"), "icon": "fa-solid fa-display", "url_name": "obs-dashboard", "category": _("Streaming")},
    {"key": "spritkosten", "label": _("Spritkosten"), "icon": "fa-solid fa-gas-pump", "url_name": "spritkostenrechner", "category": _("Alltag")},
]


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
