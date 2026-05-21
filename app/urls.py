from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('home/', home, name='home'),
    path('about/', about, name='about'),

    path('weather/', weather, name='weather'),
    path("obs-dashboard/", obs_dashboard, name="obs-dashboard"),
    path("spritkostenrechner/", spritkostenrechner, name="spritkostenrechner"),
    path("human-benchmark/", human_benchmark, name="human-benchmark"),
    path("genius-search/", genius_search, name="genius-search"),
    path("avatar-wiki/", avatar_wiki, name="avatar-wiki"),
    path("api/avatar-characters/", avatar_characters_api, name="avatar-characters-api"),
    path("api/avatar-characters/<int:character_id>/", avatar_character_detail_api, name="avatar-character-detail-api"),
    path("api/genius/search/", genius_search_api, name="genius-search-api"),
    path("api/tankstellen/", tankstellen_api, name="tankstellen-api"),

    path("notes/", notes_view, name="notes"),
    path("notes/new/", note_create_view, name="note_create"),
    path("notes/<int:pk>/edit/", note_edit_view, name="note_edit"),
    path("notes/<int:pk>/delete/", note_delete_view, name="note_delete"),
    path("notes/<int:pk>/pin/", note_toggle_pin_view, name="note_toggle_pin"),
    path("notes/<int:pk>/archive/", note_toggle_archive_view, name="note_toggle_archive"),

    path("einheitenrechner/", unit_converter_view, name="unit_converter"),

    path("drift-circuit/", drift_circuit, name="drift-circuit"),
]
