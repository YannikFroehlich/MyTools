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
]
