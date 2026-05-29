from django.urls import path

from .views import *
from .profile_views import friends_list_view, friendship_action_view, profile_view, users_view, public_profile_view
from .skribble_views import *
from .chat_views import *
from .notification_views import notification_center_api, notification_counts_api

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

    path("chat/", chat_view, name="chat"),
    path("chat/<int:room_id>/", chat_view, name="chat_room"),
    path("chat/direct/<int:user_id>/", start_direct_chat, name="chat_direct"),
    path("chat/group/new/", create_group_chat, name="chat_group_create"),
    path("chat/<int:room_id>/send/", send_chat_message, name="chat_send"),
    path("chat/<int:room_id>/message/<int:message_id>/delete/", delete_chat_message, name="chat_message_delete"),
    path("chat/<int:room_id>/message/<int:message_id>/react/", react_chat_message, name="chat_message_react"),
    path("api/chat/<int:room_id>/messages/", chat_messages_api, name="chat_messages_api"),
    path("api/notifications/counts/", notification_counts_api, name="notification_counts_api"),
    path("api/notifications/center/", notification_center_api, name="notification_center_api"),

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

    path("skribble/", skribble_home, name="skribble_home"),
    path("skribble/<slug:code>/", skribble_lobby, name="skribble_lobby"),
    path("skribble/<slug:code>/invite/", skribble_invite_friend, name="skribble_invite_friend"),
    path("skribble/invite/<int:invite_id>/", skribble_invite_response, name="skribble_invite_response"),
    path("skribble/<slug:code>/avatar/", skribble_update_avatar, name="skribble_update_avatar"),
    path("skribble/<slug:code>/start/", skribble_start, name="skribble_start"),
    path("skribble/<slug:code>/restart/", skribble_restart, name="skribble_restart"),
    path("skribble/<slug:code>/leave/", skribble_leave_lobby, name="skribble_leave_lobby"),
    path("skribble/<slug:code>/delete/", skribble_delete_lobby, name="skribble_delete_lobby"),
    path("api/skribble/<slug:code>/state/", skribble_state_api, name="skribble_state_api"),
    path("api/skribble/<slug:code>/choose-word/", skribble_choose_word_api, name="skribble_choose_word_api"),
    path("api/skribble/<slug:code>/draw/", skribble_draw_api, name="skribble_draw_api"),
    path("api/skribble/<slug:code>/guess/", skribble_guess_api, name="skribble_guess_api"),

    path("stream-deck/", stream_deck, name="stream-deck"),
]