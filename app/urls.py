from django.urls import path

from .views import *
from .profile_views import friends_list_view, friendship_action_view, profile_view, users_view, public_profile_view
from .drawing_game_views import *

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('', home, name='home'),
    path('home/', home, name='home'),
    path('about/', about, name='about'),
    path('uhr/', clock_view, name='clock'),

    path('profile/', profile_view, name='profile'),
    path('users/', users_view, name='users'),
    path('users/<int:user_id>/', public_profile_view, name='public_profile'),
    path('users/<int:user_id>/friends/', friends_list_view, name='friends_list'),
    path('users/<int:user_id>/friendship/', friendship_action_view, name='friendship_action'),

    path('weather/', weather, name='weather'),
    path("obs-dashboard/", obs_dashboard, name="obs-dashboard"),
    path("spritkostenrechner/", spritkostenrechner, name="spritkostenrechner"),

    path("human-benchmark/", human_benchmark, name="human-benchmark"),
    path("api/human-benchmark/scores/", human_benchmark_score_api, name="human-benchmark-score-api"),

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

    path("zeichenspiel/", drawing_game_home, name="drawing_game_home"),
    path("zeichenspiel/<slug:code>/", drawing_game_lobby, name="drawing_game_lobby"),
    path("zeichenspiel/<slug:code>/invite/", drawing_game_invite_friend, name="drawing_game_invite_friend"),
    path("zeichenspiel/invite/<int:invite_id>/", drawing_game_invite_response, name="drawing_game_invite_response"),
    path("zeichenspiel/<slug:code>/avatar/", drawing_game_update_avatar, name="drawing_game_update_avatar"),
    path("zeichenspiel/<slug:code>/start/", drawing_game_start, name="drawing_game_start"),
    path("zeichenspiel/<slug:code>/restart/", drawing_game_restart, name="drawing_game_restart"),
    path("zeichenspiel/<slug:code>/leave/", drawing_game_leave_lobby, name="drawing_game_leave_lobby"),
    path("zeichenspiel/<slug:code>/delete/", drawing_game_delete_lobby, name="drawing_game_delete_lobby"),
    path("api/zeichenspiel/<slug:code>/state/", drawing_game_state_api, name="drawing_game_state_api"),
    path("api/zeichenspiel/<slug:code>/choose-word/", drawing_game_choose_word_api, name="drawing_game_choose_word_api"),
    path("api/zeichenspiel/<slug:code>/draw/", drawing_game_draw_api, name="drawing_game_draw_api"),
    path("api/zeichenspiel/<slug:code>/guess/", drawing_game_guess_api, name="drawing_game_guess_api"),

    path("stream-deck/", stream_deck, name="stream-deck"),
]