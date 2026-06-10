from django.db.models import Max, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import (
    BattleshipGame,
    ChatMessage,
    ChatRoom,
    ConnectFourGame,
    CookieClickerHighScore,
    Game2048HighScore,
    DrawingGamePlayer,
    FileShare,
    Friendship,
    HangmanLobby,
    HangmanPlayer,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    KniffelGame,
    KniffelPlayer,
    Note,
    PongGame,
    ProfileGalleryImage,
    SkribbleStats,
    StadtLandFlussPlayer,
    TicTacToeGame,
    UnoGame,
    UnoPlayer,
    UserProfile,
    UserPresence,
)


CATEGORY_META = {
    "games": {"label": _("Spiele"), "icon": "fa-solid fa-gamepad"},
    "notes": {"label": _("Notizen"), "icon": "fa-regular fa-note-sticky"},
    "chat": {"label": _("Chat"), "icon": "fa-solid fa-comments"},
    "profile": {"label": _("Profil"), "icon": "fa-solid fa-id-card-clip"},
    "uploads": {"label": _("Uploads"), "icon": "fa-solid fa-share-nodes"},
    "daily": {"label": _("Aktive Tage"), "icon": "fa-regular fa-calendar-check"},
}


def achievement_definitions():
    return [
        {
            "key": "profile_started",
            "category": "profile",
            "label": _("Profil gestartet"),
            "description": _("Profilinformationen gepflegt."),
            "icon": "fa-solid fa-id-card",
            "metric": "profile_fields",
            "target": 1,
            "xp": 30,
        },
        {
            "key": "profile_complete",
            "category": "profile",
            "label": _("Profil komplett"),
            "description": _("Avatar, Banner, Bio und Name sind gepflegt."),
            "icon": "fa-solid fa-user-check",
            "metric": "profile_fields",
            "target": 4,
            "xp": 90,
        },
        {
            "key": "social_start",
            "category": "profile",
            "label": _("Erster Kontakt"),
            "description": _("Mindestens ein Freund verbunden."),
            "icon": "fa-solid fa-user-group",
            "metric": "friends_count",
            "target": 1,
            "xp": 45,
        },
        {
            "key": "gallery_moment",
            "category": "profile",
            "label": _("Galerie-Moment"),
            "description": _("Ein Profilbild in die Galerie geladen."),
            "icon": "fa-regular fa-images",
            "metric": "gallery_count",
            "target": 1,
            "xp": 35,
        },
        {
            "key": "profile_showcase",
            "category": "profile",
            "label": _("Showcase gebaut"),
            "description": _("Profilkarte oder Spielkarten angepasst."),
            "icon": "fa-solid fa-palette",
            "metric": "profile_card_customized",
            "target": 1,
            "xp": 55,
        },
        {
            "key": "profile_collector",
            "category": "profile",
            "label": _("Galerie-Sammlung"),
            "description": _("Fünf Profilbilder in der Galerie."),
            "icon": "fa-solid fa-images",
            "metric": "gallery_count",
            "target": 5,
            "xp": 85,
        },
        {
            "key": "daily_visit",
            "category": "daily",
            "label": _("Tagesbesuch"),
            "description": _("An einem Tag Aktivität gesammelt."),
            "icon": "fa-regular fa-calendar-check",
            "metric": "active_days",
            "target": 1,
            "xp": 25,
        },
        {
            "key": "weekly_regular",
            "category": "daily",
            "label": _("Wochenrhythmus"),
            "description": _("An sieben verschiedenen Tagen aktiv."),
            "icon": "fa-solid fa-calendar-week",
            "metric": "active_days",
            "target": 7,
            "xp": 95,
        },
        {
            "key": "daily_anchor",
            "category": "daily",
            "label": _("Fester Anker"),
            "description": _("An dreißig verschiedenen Tagen aktiv."),
            "icon": "fa-solid fa-calendar-days",
            "metric": "active_days",
            "target": 30,
            "xp": 180,
        },
        {
            "key": "first_note",
            "category": "notes",
            "label": _("Erste Notiz"),
            "description": _("Eine Notiz erstellt."),
            "icon": "fa-regular fa-note-sticky",
            "metric": "notes_count",
            "target": 1,
            "xp": 30,
        },
        {
            "key": "note_keeper",
            "category": "notes",
            "label": _("Notizsammler"),
            "description": _("Fünf Notizen erstellt."),
            "icon": "fa-solid fa-layer-group",
            "metric": "notes_count",
            "target": 5,
            "xp": 70,
        },
        {
            "key": "note_architect",
            "category": "notes",
            "label": _("Wissensarchitekt"),
            "description": _("Zwanzig Notizen erstellt."),
            "icon": "fa-solid fa-building-columns",
            "metric": "notes_count",
            "target": 20,
            "xp": 130,
        },
        {
            "key": "reminder_ready",
            "category": "notes",
            "label": _("Dran gedacht"),
            "description": _("Eine Notiz mit Erinnerung versehen."),
            "icon": "fa-regular fa-bell",
            "metric": "note_reminders",
            "target": 1,
            "xp": 45,
        },
        {
            "key": "note_collab",
            "category": "notes",
            "label": _("Geteilte Idee"),
            "description": _("Eine Notiz mit Freunden geteilt."),
            "icon": "fa-solid fa-users-viewfinder",
            "metric": "notes_shared",
            "target": 1,
            "xp": 55,
        },
        {
            "key": "first_message",
            "category": "chat",
            "label": _("Erste Nachricht"),
            "description": _("Eine Chatnachricht gesendet."),
            "icon": "fa-solid fa-message",
            "metric": "chat_messages",
            "target": 1,
            "xp": 30,
        },
        {
            "key": "chatty",
            "category": "chat",
            "label": _("Gesprächig"),
            "description": _("25 Chatnachrichten gesendet."),
            "icon": "fa-solid fa-comments",
            "metric": "chat_messages",
            "target": 25,
            "xp": 80,
        },
        {
            "key": "chat_regular",
            "category": "chat",
            "label": _("Stammtisch"),
            "description": _("100 Chatnachrichten gesendet."),
            "icon": "fa-solid fa-comment-medical",
            "metric": "chat_messages",
            "target": 100,
            "xp": 140,
        },
        {
            "key": "chat_marathon",
            "category": "chat",
            "label": _("Chat-Marathon"),
            "description": _("500 Chatnachrichten gesendet."),
            "icon": "fa-solid fa-comment-dots",
            "metric": "chat_messages",
            "target": 500,
            "xp": 230,
        },
        {
            "key": "room_hopper",
            "category": "chat",
            "label": _("Raumreisender"),
            "description": _("In drei Chaträumen aktiv."),
            "icon": "fa-solid fa-door-open",
            "metric": "chat_rooms",
            "target": 3,
            "xp": 65,
        },
        {
            "key": "group_regular",
            "category": "chat",
            "label": _("Gruppenmensch"),
            "description": _("In drei Gruppenchats aktiv."),
            "icon": "fa-solid fa-people-group",
            "metric": "group_chat_rooms",
            "target": 3,
            "xp": 90,
        },
        {
            "key": "first_upload",
            "category": "uploads",
            "label": _("Erster Upload"),
            "description": _("Eine Datei geteilt."),
            "icon": "fa-solid fa-upload",
            "metric": "uploads_count",
            "target": 1,
            "xp": 35,
        },
        {
            "key": "file_sharer",
            "category": "uploads",
            "label": _("Datei-Verteiler"),
            "description": _("Fünf Dateien geteilt."),
            "icon": "fa-solid fa-folder-open",
            "metric": "uploads_count",
            "target": 5,
            "xp": 75,
        },
        {
            "key": "public_link",
            "category": "uploads",
            "label": _("Privater Link"),
            "description": _("Eine Datei per privatem Link freigegeben."),
            "icon": "fa-solid fa-link",
            "metric": "public_uploads",
            "target": 1,
            "xp": 45,
        },
        {
            "key": "downloaded",
            "category": "uploads",
            "label": _("Angekommen"),
            "description": _("Zehn Downloads deiner Freigaben erreicht."),
            "icon": "fa-solid fa-download",
            "metric": "upload_downloads",
            "target": 10,
            "xp": 110,
        },
        {
            "key": "first_game",
            "category": "games",
            "label": _("Spiel gestartet"),
            "description": _("Erste Spielaktivität gesammelt."),
            "icon": "fa-solid fa-play",
            "metric": "game_activity",
            "target": 1,
            "xp": 35,
        },
        {
            "key": "score_hunter",
            "category": "games",
            "label": _("Score-Jäger"),
            "description": _("Drei Highscores erspielt."),
            "icon": "fa-solid fa-stopwatch",
            "metric": "highscores_count",
            "target": 3,
            "xp": 80,
        },
        {
            "key": "benchmark_regular",
            "category": "games",
            "label": _("Benchmark-Routine"),
            "description": _("Zehn Human-Benchmark-Runs gespielt."),
            "icon": "fa-solid fa-stopwatch",
            "metric": "human_benchmark_runs",
            "target": 10,
            "xp": 95,
        },
        {
            "key": "highscore_master",
            "category": "games",
            "label": _("Highscore-Meister"),
            "description": _("Alle fünf Highscore-Slots gefüllt."),
            "icon": "fa-solid fa-ranking-star",
            "metric": "highscores_count",
            "target": 5,
            "xp": 150,
        },
        {
            "key": "tile_1024",
            "category": "games",
            "label": _("1024-Kachel"),
            "description": _("In 2048 mindestens die 1024-Kachel erreicht."),
            "icon": "fa-solid fa-table-cells-large",
            "metric": "game_2048_best_tile",
            "target": 1024,
            "xp": 100,
        },
        {
            "key": "tile_2048",
            "category": "games",
            "label": _("2048 geschafft"),
            "description": _("In 2048 die 2048-Kachel erreicht."),
            "icon": "fa-solid fa-crown",
            "metric": "game_2048_best_tile",
            "target": 2048,
            "xp": 180,
        },
        {
            "key": "game_2048_regular",
            "category": "games",
            "label": _("Kachel-Routine"),
            "description": _("Zehn 2048-Runden gespielt."),
            "icon": "fa-solid fa-repeat",
            "metric": "game_2048_runs",
            "target": 10,
            "xp": 95,
        },
        {
            "key": "cookie_collector",
            "category": "games",
            "label": _("Cookie-Sammler"),
            "description": _("25 Cookie-Cosmos-Achievements gesammelt."),
            "icon": "fa-solid fa-cookie-bite",
            "metric": "cookie_achievements",
            "target": 25,
            "xp": 120,
        },
        {
            "key": "skribble_artist",
            "category": "games",
            "label": _("Zeichenhand"),
            "description": _("Zehn Skribble-Zeichnungen gemacht."),
            "icon": "fa-solid fa-pen-nib",
            "metric": "skribble_drawings",
            "target": 10,
            "xp": 115,
        },
        {
            "key": "pong_first_match",
            "category": "games",
            "label": _("Pong-Duell"),
            "description": _("Ein Pong-Match beendet."),
            "icon": "fa-solid fa-table-tennis-paddle-ball",
            "metric": "pong_matches",
            "target": 1,
            "xp": 55,
        },
        {
            "key": "pong_rally",
            "category": "games",
            "label": _("Rally-Kontrolle"),
            "description": _("In Pong eine Rally mit zehn Ballkontakten erreicht."),
            "icon": "fa-solid fa-arrows-left-right",
            "metric": "pong_best_rally",
            "target": 10,
            "xp": 90,
        },
        {
            "key": "pong_champion",
            "category": "games",
            "label": _("Pong-Champion"),
            "description": _("Drei Pong-Matches gewonnen."),
            "icon": "fa-solid fa-crown",
            "metric": "pong_wins",
            "target": 3,
            "xp": 125,
        },
        {
            "key": "table_player",
            "category": "games",
            "label": _("Mitspieler"),
            "description": _("Zehn Multiplayer-Teilnahmen gesammelt."),
            "icon": "fa-solid fa-people-arrows",
            "metric": "multiplayer_entries",
            "target": 10,
            "xp": 95,
        },
        {
            "key": "first_win",
            "category": "games",
            "label": _("Erster Sieg"),
            "description": _("Ein Spiel gewonnen."),
            "icon": "fa-solid fa-trophy",
            "metric": "wins_count",
            "target": 1,
            "xp": 80,
        },
        {
            "key": "winner_circle",
            "category": "games",
            "label": _("Siegesserie"),
            "description": _("Fünf Spiele gewonnen."),
            "icon": "fa-solid fa-medal",
            "metric": "wins_count",
            "target": 5,
            "xp": 150,
        },
        {
            "key": "game_veteran",
            "category": "games",
            "label": _("Game Veteran"),
            "description": _("25 Spielaktivitäten gesammelt."),
            "icon": "fa-solid fa-crown",
            "metric": "game_activity",
            "target": 25,
            "xp": 150,
        },
        {
            "key": "multiplayer_veteran",
            "category": "games",
            "label": _("Lobby-Veteran"),
            "description": _("50 Multiplayer-Teilnahmen gesammelt."),
            "icon": "fa-solid fa-users",
            "metric": "multiplayer_entries",
            "target": 50,
            "xp": 220,
        },
    ]


def _safe_count(queryset):
    return queryset.count()


def _profile_field_count(user):
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return 0

    return sum([
        bool(profile.avatar),
        bool(profile.profile_banner),
        bool((profile.bio or "").strip()),
        bool(user.get_full_name()),
    ])


def _profile_card_customized(user):
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return 0

    defaults = {
        "profile_card_style": UserProfile.CARD_STYLE_GLASS,
        "profile_card_primary": "#7c3aed",
        "profile_card_secondary": "#06b6d4",
        "profile_card_tertiary": "#c026d3",
        "profile_card_pattern": UserProfile.CARD_PATTERN_ORBS,
        "profile_card_radius": UserProfile.CARD_RADIUS_BOLD,
        "profile_card_avatar_shape": UserProfile.CARD_AVATAR_ROUNDED,
        "profile_card_badge_text": "MyTools",
    }
    changed_style = any(getattr(profile, field) != value for field, value in defaults.items())
    changed_game_cards = bool(profile.profile_game_cards)
    return int(changed_style or changed_game_cards)


def _date_from_value(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()
    return value


def _add_queryset_days(days, queryset, field_name):
    null_filter = {f"{field_name}__isnull": False}
    for active_day in (
        queryset
        .filter(**null_filter)
        .annotate(active_day=TruncDate(field_name))
        .values_list("active_day", flat=True)
        .distinct()
    ):
        if active_day:
            days.add(active_day)


def _active_days_for_user(user, include_private=True, include_games=True):
    days = set()
    for value in [getattr(user, "date_joined", None), getattr(user, "last_login", None)]:
        active_day = _date_from_value(value)
        if active_day:
            days.add(active_day)

    presence = UserPresence.objects.filter(user=user).first()
    active_day = _date_from_value(getattr(presence, "last_seen", None))
    if active_day:
        days.add(active_day)

    if include_private:
        _add_queryset_days(days, Note.objects.filter(user=user), "created_at")
        _add_queryset_days(days, ChatMessage.objects.filter(sender=user), "created_at")
        _add_queryset_days(days, FileShare.objects.filter(owner=user), "created_at")
        _add_queryset_days(days, ProfileGalleryImage.objects.filter(user=user), "created_at")

    if include_games:
        _add_queryset_days(days, HumanBenchmarkScore.objects.filter(user=user), "created_at")
        _add_queryset_days(days, HumanBenchmarkHighScore.objects.filter(user=user), "achieved_at")
        _add_queryset_days(days, Game2048HighScore.objects.filter(user=user), "achieved_at")
        _add_queryset_days(days, TicTacToeGame.objects.filter(Q(player_x=user) | Q(player_o=user)), "created_at")
        _add_queryset_days(days, ConnectFourGame.objects.filter(Q(player_red=user) | Q(player_yellow=user)), "created_at")
        _add_queryset_days(days, BattleshipGame.objects.filter(Q(player_a=user) | Q(player_b=user)), "created_at")
        _add_queryset_days(days, UnoPlayer.objects.filter(user=user), "joined_at")
        _add_queryset_days(days, KniffelPlayer.objects.filter(user=user), "joined_at")
        _add_queryset_days(days, StadtLandFlussPlayer.objects.filter(user=user), "joined_at")
        _add_queryset_days(days, HangmanPlayer.objects.filter(user=user), "joined_at")
        _add_queryset_days(days, DrawingGamePlayer.objects.filter(user=user), "joined_at")

        cookie_highscore = CookieClickerHighScore.objects.filter(user=user).first()
        active_day = _date_from_value(getattr(cookie_highscore, "achieved_at", None))
        if active_day:
            days.add(active_day)

    return len(days)


def collect_achievement_metrics(user, include_private=True, include_games=True):
    friends_count = Friendship.accepted_for_user(user).count()
    gallery_items = ProfileGalleryImage.objects.filter(user=user)
    if not include_private:
        gallery_items = gallery_items.filter(is_public=True)
    gallery_count = gallery_items.count()

    metrics = {
        "profile_fields": _profile_field_count(user),
        "friends_count": friends_count,
        "gallery_count": gallery_count,
        "profile_card_customized": _profile_card_customized(user),
        "notes_count": 0,
        "note_reminders": 0,
        "notes_shared": 0,
        "chat_messages": 0,
        "chat_rooms": 0,
        "group_chat_rooms": 0,
        "uploads_count": 0,
        "public_uploads": 0,
        "upload_downloads": 0,
        "game_activity": 0,
        "highscores_count": 0,
        "multiplayer_entries": 0,
        "wins_count": 0,
        "human_benchmark_runs": 0,
        "cookie_achievements": 0,
        "game_2048_best_tile": 0,
        "game_2048_runs": 0,
        "skribble_drawings": 0,
        "pong_matches": 0,
        "pong_wins": 0,
        "pong_best_rally": 0,
        "active_days": _active_days_for_user(user, include_private=include_private, include_games=include_games),
    }

    if include_private:
        user_notes = Note.objects.filter(user=user)
        metrics.update({
            "notes_count": _safe_count(user_notes),
            "note_reminders": _safe_count(user_notes.filter(reminder_at__isnull=False)),
            "notes_shared": _safe_count(user_notes.filter(shared_with__isnull=False).distinct()),
            "chat_messages": _safe_count(ChatMessage.objects.filter(sender=user)),
            "chat_rooms": _safe_count(ChatRoom.objects.filter(room_memberships__user=user).distinct()),
            "group_chat_rooms": _safe_count(ChatRoom.objects.filter(room_type=ChatRoom.ROOM_GROUP, room_memberships__user=user).distinct()),
            "uploads_count": _safe_count(FileShare.objects.filter(owner=user)),
            "public_uploads": _safe_count(FileShare.objects.filter(owner=user, is_public_link=True)),
            "upload_downloads": FileShare.objects.filter(owner=user).aggregate(total=Sum("download_count"))["total"] or 0,
        })

    if include_games:
        highscore_count = _safe_count(HumanBenchmarkHighScore.objects.filter(user=user))
        cookie_highscore = CookieClickerHighScore.objects.filter(user=user).first()
        if cookie_highscore:
            highscore_count += 1
        game_2048_highscore = Game2048HighScore.objects.filter(user=user).first()
        if game_2048_highscore:
            highscore_count += 1

        skribble_stats = SkribbleStats.objects.filter(user=user).first()
        skribble_played = skribble_stats.games_played if skribble_stats else 0
        skribble_wins = skribble_stats.games_won if skribble_stats else 0
        skribble_drawings = skribble_stats.drawings_made if skribble_stats else 0

        tictactoe_entries = _safe_count(TicTacToeGame.objects.filter(Q(player_x=user) | Q(player_o=user)).distinct())
        connectfour_entries = _safe_count(ConnectFourGame.objects.filter(Q(player_red=user) | Q(player_yellow=user)).distinct())
        battleship_entries = _safe_count(BattleshipGame.objects.filter(Q(player_a=user) | Q(player_b=user)).distinct())
        uno_entries = _safe_count(UnoPlayer.objects.filter(user=user))
        kniffel_entries = _safe_count(KniffelPlayer.objects.filter(user=user))
        stadt_entries = _safe_count(StadtLandFlussPlayer.objects.filter(user=user))
        hangman_entries = _safe_count(HangmanPlayer.objects.filter(user=user))
        drawing_entries = _safe_count(DrawingGamePlayer.objects.filter(user=user))
        pong_entries = _safe_count(PongGame.objects.filter(Q(player_left=user) | Q(player_right=user)).distinct())

        multiplayer_entries = sum([
            tictactoe_entries,
            connectfour_entries,
            battleship_entries,
            uno_entries,
            kniffel_entries,
            stadt_entries,
            hangman_entries,
            drawing_entries,
            pong_entries,
        ])

        wins_count = skribble_wins
        wins_count += _safe_count(TicTacToeGame.objects.filter(
            Q(player_x=user, winner_symbol=TicTacToeGame.SYMBOL_X)
            | Q(player_o=user, winner_symbol=TicTacToeGame.SYMBOL_O)
        ))
        wins_count += _safe_count(ConnectFourGame.objects.filter(
            Q(player_red=user, winner_disc=ConnectFourGame.DISC_RED)
            | Q(player_yellow=user, winner_disc=ConnectFourGame.DISC_YELLOW)
        ))
        wins_count += _safe_count(BattleshipGame.objects.filter(
            Q(player_a=user, winner_side=BattleshipGame.SIDE_A)
            | Q(player_b=user, winner_side=BattleshipGame.SIDE_B)
        ))
        wins_count += _safe_count(UnoGame.objects.filter(winner_user_id=user.id))
        wins_count += _safe_count(KniffelGame.objects.filter(winner_user_id=user.id))
        wins_count += _safe_count(HangmanLobby.objects.filter(winner=user))
        pong_finished = PongGame.objects.filter(Q(player_left=user) | Q(player_right=user), status=PongGame.STATUS_FINISHED).distinct()
        pong_wins = _safe_count(PongGame.objects.filter(
            Q(player_left=user, winner_side=PongGame.SIDE_LEFT)
            | Q(player_right=user, winner_side=PongGame.SIDE_RIGHT)
        ))
        pong_best_rally = pong_finished.aggregate(best=Max("best_rally"))["best"] or 0
        wins_count += pong_wins

        game_activity = (
            _safe_count(HumanBenchmarkScore.objects.filter(user=user))
            + highscore_count
            + multiplayer_entries
            + skribble_played
            + (game_2048_highscore.games_played if game_2048_highscore else 0)
        )

        metrics.update({
            "game_activity": game_activity,
            "highscores_count": highscore_count,
            "multiplayer_entries": multiplayer_entries,
            "wins_count": wins_count,
            "human_benchmark_runs": _safe_count(HumanBenchmarkScore.objects.filter(user=user)),
            "cookie_achievements": cookie_highscore.achievements_count if cookie_highscore else 0,
            "game_2048_best_tile": game_2048_highscore.best_tile if game_2048_highscore else 0,
            "game_2048_runs": game_2048_highscore.games_played if game_2048_highscore else 0,
            "skribble_drawings": skribble_drawings,
            "pong_matches": _safe_count(pong_finished),
            "pong_wins": pong_wins,
            "pong_best_rally": pong_best_rally,
        })

    return metrics


def _format_metric(value):
    return f"{int(value):,}".replace(",", ".")


def _level_from_xp(xp):
    level = 1
    remaining = int(xp)
    next_level_xp = 100

    while remaining >= next_level_xp:
        remaining -= next_level_xp
        level += 1
        next_level_xp = 100 + (level - 1) * 50

    progress_percent = round((remaining / next_level_xp) * 100) if next_level_xp else 100
    return {
        "level": level,
        "current_xp": remaining,
        "next_level_xp": next_level_xp,
        "progress_percent": min(100, max(0, progress_percent)),
    }


def get_achievement_summary(user, include_private=True, include_games=True):
    metrics = collect_achievement_metrics(
        user,
        include_private=include_private,
        include_games=include_games,
    )
    allowed_categories = {"profile"}
    if include_games:
        allowed_categories.add("games")
    if include_private:
        allowed_categories.update({"notes", "chat", "uploads", "daily"})

    achievements = []
    for definition in achievement_definitions():
        if definition["category"] not in allowed_categories:
            continue

        value = metrics.get(definition["metric"], 0)
        target = definition["target"]
        unlocked = value >= target
        progress_percent = round((min(value, target) / target) * 100) if target else 100
        achievements.append({
            **definition,
            "value": value,
            "value_label": _format_metric(value),
            "progress_percent": min(100, max(0, progress_percent)),
            "unlocked": unlocked,
        })

    unlocked_achievements = [achievement for achievement in achievements if achievement["unlocked"]]
    total_xp = sum(achievement["xp"] for achievement in unlocked_achievements)
    total_available_xp = sum(achievement["xp"] for achievement in achievements)

    categories = []
    for key, meta in CATEGORY_META.items():
        category_achievements = [achievement for achievement in achievements if achievement["category"] == key]
        if not category_achievements:
            continue

        unlocked_count = sum(1 for achievement in category_achievements if achievement["unlocked"])
        categories.append({
            "key": key,
            **meta,
            "unlocked_count": unlocked_count,
            "total_count": len(category_achievements),
            "progress_percent": round((unlocked_count / len(category_achievements)) * 100),
        })

    next_achievements = [achievement for achievement in achievements if not achievement["unlocked"]][:3]

    return {
        "achievements": achievements,
        "unlocked": unlocked_achievements,
        "categories": categories,
        "level": _level_from_xp(total_xp),
        "total_xp": total_xp,
        "total_available_xp": total_available_xp,
        "unlocked_count": len(unlocked_achievements),
        "total_count": len(achievements),
        "next_achievements": next_achievements,
        "metrics": metrics,
        "profile_url": reverse("profile"),
    }
