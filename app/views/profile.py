import base64
import re
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Count, Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..models import (
    BattleshipGame,
    ChatMessage,
    ChatRoom,
    ConnectFourGame,
    CookieClickerHighScore,
    FileShare,
    Game2048HighScore,
    Friendship,
    HangmanLobby,
    HangmanPlayer,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    InboxItem,
    KniffelGame,
    KniffelPlayer,
    ProfileGalleryImage,
    PongGame,
    SkribbleStats,
    StadtLandFlussPlayer,
    Note,
    TicTacToeGame,
    ToolFavorite,
    UnoGame,
    UnoPlayer,
    UserBlock,
    UserProfile,
    UserReport,
)
from ..achievement_utils import get_achievement_summary
from ..forms.profile import ProfileForm, ProfileGalleryImageForm, UserReportForm
from ..image_optimization import (
    GALLERY_IMAGE_MAX_SIZE,
    PROFILE_AVATAR_MAX_SIZE,
    optimize_uploaded_image,
)
from ..notification_utils import invalidate_notification_cache
from ..platform_utils import resolve_tools
from ..presence_utils import decorate_profiles_with_presence, decorate_users_with_presence

User = get_user_model()

PROFILE_GAME_CARD_DEFINITIONS = [
    {"key": "game_2048", "label": "2048", "icon": "fa-solid fa-table-cells-large", "url_name": "game-2048"},
    {"key": "cookie_cosmos", "label": "Cookie Cosmos", "icon": "fa-solid fa-cookie-bite", "url_name": "cookie-clicker"},
    {"key": "human_benchmark", "label": "Human Benchmark", "icon": "fa-solid fa-stopwatch", "url_name": "human-benchmark"},
    {"key": "skribble", "label": "Skribble", "icon": "fa-solid fa-pen-nib", "url_name": "skribble_home"},
    {"key": "tictactoe", "label": "Tic Tac Toe", "icon": "fa-solid fa-xmark", "url_name": "tictactoe_home"},
    {"key": "connectfour", "label": "Vier gewinnt", "icon": "fa-solid fa-table-cells-large", "url_name": "connectfour_home"},
    {"key": "battleship", "label": "Schiffe versenken", "icon": "fa-solid fa-anchor", "url_name": "battleship_home"},
    {"key": "stadtlandfluss", "label": "Stadt Land Fluss", "icon": "fa-solid fa-list-check", "url_name": "stadtlandfluss_home"},
    {"key": "hangman", "label": "Hangman", "icon": "fa-solid fa-spell-check", "url_name": "hangman_home"},
    {"key": "uno", "label": "Uno", "icon": "fa-solid fa-layer-group", "url_name": "uno_home"},
    {"key": "kniffel", "label": "Kniffel", "icon": "fa-solid fa-dice", "url_name": "kniffel_home"},
    {"key": "pong", "label": "Pong", "icon": "fa-solid fa-table-tennis-paddle-ball", "url_name": "pong_home"},
    {"key": "snake_powerups", "label": "Snake Powerups", "icon": "fa-solid fa-bolt", "url_name": "snake-powerups"},
    {"key": "nebula_forge_tycoon", "label": "Nebula Forge Tycoon", "icon": "fa-solid fa-meteor", "url_name": "nebula-forge-tycoon"},
]
PROFILE_GAME_CARD_DEFINITIONS_BY_KEY = {item["key"]: item for item in PROFILE_GAME_CARD_DEFINITIONS}


def _is_hex_color(value):
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value or ""))


def _clean_fa_icon(value):
    value = (value or "").strip()[:40]
    if re.fullmatch(r"[a-z0-9\- ]+", value):
        return value
    return "fa-solid fa-star"


def get_profile_human_benchmark_highscores(user):
    highscores = {
        highscore.game: highscore
        for highscore in HumanBenchmarkHighScore.objects.filter(user=user)
    }

    return [
        {
            "game": game,
            "label": label,
            "highscore": highscores.get(game),
        }
        for game, label in HumanBenchmarkScore.GAME_CHOICES
    ]


def get_profile_cookie_highscore(user):
    return CookieClickerHighScore.objects.filter(user=user).first()


def get_profile_2048_highscore(user):
    return Game2048HighScore.objects.filter(user=user).first()


def get_total_profile_highscores(user):
    total = HumanBenchmarkHighScore.objects.filter(user=user).count()
    if CookieClickerHighScore.objects.filter(user=user).exists():
        total += 1
    if Game2048HighScore.objects.filter(user=user).exists():
        total += 1
    return total


def _display_number(value, default="0"):
    if value is None:
        return default
    return f"{value:,}".replace(",", ".")


def get_profile_spotlight_stats(user, achievement_summary, *, friends_count=0, highscore_count=0, include_private=False):
    stats = []
    if achievement_summary is not None:
        stats.extend([
            {
                "label": _("Level"),
                "value": _display_number(achievement_summary["level"]["level"]),
                "hint": _("%(xp)s XP") % {"xp": _display_number(achievement_summary["total_xp"])},
                "icon": "fa-solid fa-ranking-star",
            },
            {
                "label": _("Achievements"),
                "value": _display_number(achievement_summary["unlocked_count"]),
                "hint": _("%(total)s gesamt") % {"total": _display_number(achievement_summary["total_count"])},
                "icon": "fa-solid fa-trophy",
            },
        ])
    stats.extend([
        {
            "label": _("Freunde"),
            "value": _display_number(friends_count),
            "hint": _("Netzwerk"),
            "icon": "fa-solid fa-user-group",
        },
        {
            "label": _("Highscores"),
            "value": _display_number(highscore_count),
            "hint": _("sichtbar im Profil"),
            "icon": "fa-solid fa-chart-simple",
        },
    ])

    if include_private:
        stats.extend([
            {
                "label": _("Notizen"),
                "value": _display_number(Note.objects.filter(user=user, is_archived=False).count()),
                "hint": _("aktive Einträge"),
                "icon": "fa-regular fa-note-sticky",
            },
            {
                "label": _("Uploads"),
                "value": _display_number(FileShare.objects.filter(owner=user).count()),
                "hint": _("Datei-Share"),
                "icon": "fa-solid fa-share-nodes",
            },
        ])

    return stats


def get_profile_game_card_settings(profile):
    raw_items = profile.profile_game_cards if isinstance(profile.profile_game_cards, list) else []
    saved = {}

    for index, item in enumerate(raw_items):
        if isinstance(item, dict):
            key = str(item.get("key", "")).strip()
            visible = bool(item.get("visible", True))
        else:
            key = str(item).strip()
            visible = True

        if key in PROFILE_GAME_CARD_DEFINITIONS_BY_KEY and key not in saved:
            saved[key] = {"order": index, "visible": visible}

    # Keep the user's explicitly configured card order at the front.
    # Newly added game cards that are not present in an older saved profile config
    # must be appended after the saved cards, otherwise adding a new default card
    # at index 0 would unexpectedly jump ahead of the user's configured order.
    fallback_order_start = len(raw_items)

    settings = []
    for index, definition in enumerate(PROFILE_GAME_CARD_DEFINITIONS):
        saved_item = saved.get(definition["key"])
        if saved_item is not None:
            order = saved_item["order"]
            visible = saved_item["visible"]
        else:
            order = fallback_order_start + index
            visible = True

        settings.append({
            **definition,
            "order": order,
            "visible": visible,
        })

    return sorted(settings, key=lambda item: item["order"])


def save_profile_game_card_settings(profile, post_data):
    ordered_keys = []
    for key in post_data.getlist("game_card_order"):
        key = str(key).strip()
        if key in PROFILE_GAME_CARD_DEFINITIONS_BY_KEY and key not in ordered_keys:
            ordered_keys.append(key)

    for definition in PROFILE_GAME_CARD_DEFINITIONS:
        if definition["key"] not in ordered_keys:
            ordered_keys.append(definition["key"])

    visible_keys = set(post_data.getlist("game_card_visible"))
    profile.profile_game_cards = [
        {"key": key, "visible": key in visible_keys}
        for key in ordered_keys
    ]
    profile.save(update_fields=["profile_game_cards", "updated_at"])


def _base_game_card(definition):
    return {
        "key": definition["key"],
        "label": definition["label"],
        "kicker": definition["label"],
        "title": _("Statistiken"),
        "icon": definition["icon"],
        "play_url": reverse(definition["url_name"]),
        "main": None,
        "metrics": [],
        "is_empty": False,
        "empty_text": _("Noch keine Statistik gespeichert."),
    }



def _game_2048_card(user, definition):
    card = _base_game_card(definition)
    card["title"] = _("Highscore")
    card["empty_text"] = _("Noch kein 2048-Highscore gespeichert.")
    highscore = get_profile_2048_highscore(user)
    if not highscore:
        card["is_empty"] = True
        return card

    card["main"] = {
        "icon": "fa-solid fa-trophy",
        "label": _("Bester Score"),
        "value": highscore.display_score,
        "detail": highscore.achieved_at.strftime("%d.%m.%Y %H:%M"),
    }
    card["metrics"] = [
        {"label": _("Beste Kachel"), "value": _display_number(highscore.best_tile), "icon": "fa-solid fa-table-cells-large"},
        {"label": _("Züge"), "value": _display_number(highscore.moves), "icon": "fa-solid fa-shuffle"},
        {"label": _("Zeit"), "value": highscore.duration_label, "icon": "fa-regular fa-clock"},
        {"label": _("Spiele"), "value": _display_number(highscore.games_played), "icon": "fa-solid fa-gamepad"},
    ]
    return card


def _cookie_game_card(user, definition):
    card = _base_game_card(definition)
    card["title"] = _("Highscore")
    card["empty_text"] = _("Noch kein Cookie-Cosmos-Highscore gespeichert.")
    highscore = get_profile_cookie_highscore(user)
    if not highscore:
        card["is_empty"] = True
        return card

    card["main"] = {
        "icon": "fa-solid fa-trophy",
        "label": _("Bester Lauf"),
        "value": highscore.display_score,
        "detail": highscore.achieved_at.strftime("%d.%m.%Y %H:%M"),
    }
    card["metrics"] = [
        {"label": "CPS", "value": f"{highscore.cps:.1f}".replace(".", ",")},
        {"label": _("Klickpower"), "value": f"{highscore.click_power:.1f}".replace(".", ",")},
        {"label": "Stardust", "value": _display_number(highscore.stardust)},
        {"label": _("Transzendenzen"), "value": _display_number(highscore.ascensions)},
        {"label": _("Upgrades"), "value": _display_number(highscore.upgrades_count)},
        {"label": _("Anlagen"), "value": _display_number(highscore.buildings_count)},
    ]
    return card


def _human_benchmark_game_card(user, definition):
    card = _base_game_card(definition)
    card["title"] = _("Highscores")
    benchmark_items = get_profile_human_benchmark_highscores(user)
    has_highscore = any(item["highscore"] for item in benchmark_items)
    card["is_empty"] = not has_highscore
    card["empty_text"] = _("Noch kein Human-Benchmark-Highscore gespeichert.")
    icons = {
        HumanBenchmarkScore.GAME_REACTION: "fa-solid fa-bolt",
        HumanBenchmarkScore.GAME_AIM: "fa-solid fa-crosshairs",
        HumanBenchmarkScore.GAME_TYPING: "fa-solid fa-keyboard",
        HumanBenchmarkScore.GAME_VISUAL: "fa-solid fa-table-cells",
    }
    card["metrics"] = [
        {
            "icon": icons.get(item["game"], "fa-solid fa-stopwatch"),
            "label": item["label"],
            "value": item["highscore"].display_score if item["highscore"] else "--",
            "detail": item["highscore"].achieved_at.strftime("%d.%m.%Y %H:%M") if item["highscore"] else _("Noch kein Highscore"),
            "is_empty": not item["highscore"],
        }
        for item in benchmark_items
    ]
    return card


def _skribble_game_card(user, definition):
    card = _base_game_card(definition)
    stats = SkribbleStats.objects.filter(user=user).first()
    if not stats:
        card["is_empty"] = True
        card["empty_text"] = _("Noch keine Skribble-Statistik gespeichert.")
        return card

    card["main"] = {"icon": "fa-solid fa-star", "label": _("Punkte"), "value": _display_number(stats.total_score), "detail": _("Gesamt")}
    card["metrics"] = [
        {"label": _("Spiele"), "value": _display_number(stats.games_played), "icon": "fa-solid fa-gamepad"},
        {"label": _("Siege"), "value": _display_number(stats.games_won), "icon": "fa-solid fa-crown"},
        {"label": _("Erraten"), "value": _display_number(stats.correct_guesses), "icon": "fa-solid fa-check"},
        {"label": _("Gezeichnet"), "value": _display_number(stats.drawings_made), "icon": "fa-solid fa-pencil"},
        {"label": _("Winrate"), "value": f"{stats.win_rate}%", "icon": "fa-solid fa-percent"},
    ]
    return card


def _duel_game_card(user, definition, model, side_a_field, side_b_field, winner_field, side_a_value, side_b_value):
    card = _base_game_card(definition)
    games = model.objects.filter(
        Q(**{side_a_field: user}) | Q(**{side_b_field: user}),
        status=model.STATUS_FINISHED,
    )
    games_played = games.count()
    wins = games.filter(
        Q(**{side_a_field: user, winner_field: side_a_value}) | Q(**{side_b_field: user, winner_field: side_b_value})
    ).count()
    draws = games.filter(**{winner_field: ""}).count()

    if not games_played:
        card["is_empty"] = True
        return card

    card["main"] = {"icon": "fa-solid fa-crown", "label": _("Siege"), "value": _display_number(wins), "detail": _("Gewonnene Spiele")}
    card["metrics"] = [
        {"label": _("Spiele"), "value": _display_number(games_played), "icon": "fa-solid fa-gamepad"},
        {"label": _("Remis"), "value": _display_number(draws), "icon": "fa-solid fa-handshake"},
    ]
    return card


def _player_score_card(user, definition, player_model, winner_model=None, winner_filter=None):
    card = _base_game_card(definition)
    players = player_model.objects.filter(user=user)
    aggregate = players.aggregate(games=Count("id"), best_score=Max("score"), total_score=Sum("score"))
    games_played = aggregate["games"] or 0

    if not games_played:
        card["is_empty"] = True
        return card

    wins = winner_model.objects.filter(**winner_filter(user)).count() if winner_model and winner_filter else 0
    card["main"] = {"icon": "fa-solid fa-star", "label": _("Bester Score"), "value": _display_number(aggregate["best_score"]), "detail": _("Persoenliche Bestleistung")}
    card["metrics"] = [
        {"label": _("Spiele"), "value": _display_number(games_played), "icon": "fa-solid fa-gamepad"},
        {"label": _("Siege"), "value": _display_number(wins), "icon": "fa-solid fa-crown"},
        {"label": _("Gesamtpunkte"), "value": _display_number(aggregate["total_score"]), "icon": "fa-solid fa-chart-line"},
    ]
    return card


def _winner_game_card(user, definition, player_model, game_model):
    card = _base_game_card(definition)
    games_played = player_model.objects.filter(user=user).count()
    wins = game_model.objects.filter(status=game_model.STATUS_FINISHED, winner_user_id=user.id).count()
    if not games_played:
        card["is_empty"] = True
        return card

    card["main"] = {"icon": "fa-solid fa-crown", "label": _("Siege"), "value": _display_number(wins), "detail": _("Gewonnene Spiele")}
    card["metrics"] = [
        {"label": _("Spiele"), "value": _display_number(games_played), "icon": "fa-solid fa-gamepad"},
        {"label": _("Winrate"), "value": f"{round((wins / games_played) * 100) if games_played else 0}%", "icon": "fa-solid fa-percent"},
    ]
    return card



def _pong_game_card(user, definition):
    card = _duel_game_card(user, definition, PongGame, "player_left", "player_right", "winner_side", PongGame.SIDE_LEFT, PongGame.SIDE_RIGHT)
    games = PongGame.objects.filter(Q(player_left=user) | Q(player_right=user), status=PongGame.STATUS_FINISHED)
    if not games.exists():
        card["empty_text"] = _("Noch keine Pong-Statistik gespeichert.")
        return card
    best_rally = games.aggregate(best=Max("best_rally"))["best"] or 0
    highest_score = 0
    for game in games:
        if game.player_left_id == user.id:
            highest_score = max(highest_score, game.score_left)
        if game.player_right_id == user.id:
            highest_score = max(highest_score, game.score_right)
    card["title"] = _("Arcade-Duell")
    card["metrics"].extend([
        {"label": _("Beste Rally"), "value": _display_number(best_rally), "icon": "fa-solid fa-arrows-left-right"},
        {"label": _("Top-Score"), "value": _display_number(highest_score), "icon": "fa-solid fa-bullseye"},
    ])
    return card

def _snake_powerups_card(user, definition):
    card = _base_game_card(definition)
    card["title"] = _("Arcade")
    card["is_empty"] = True
    card["empty_text"] = _("Snake Powerups ist bereit für deinen ersten Lauf.")
    return card


def build_profile_game_card(definition, user):
    key = definition["key"]
    if key == "game_2048":
        return _game_2048_card(user, definition)
    if key == "cookie_cosmos":
        return _cookie_game_card(user, definition)
    if key == "human_benchmark":
        return _human_benchmark_game_card(user, definition)
    if key == "skribble":
        return _skribble_game_card(user, definition)
    if key == "tictactoe":
        return _duel_game_card(user, definition, TicTacToeGame, "player_x", "player_o", "winner_symbol", TicTacToeGame.SYMBOL_X, TicTacToeGame.SYMBOL_O)
    if key == "connectfour":
        return _duel_game_card(user, definition, ConnectFourGame, "player_red", "player_yellow", "winner_disc", ConnectFourGame.DISC_RED, ConnectFourGame.DISC_YELLOW)
    if key == "battleship":
        return _duel_game_card(user, definition, BattleshipGame, "player_a", "player_b", "winner_side", BattleshipGame.SIDE_A, BattleshipGame.SIDE_B)
    if key == "stadtlandfluss":
        return _player_score_card(user, definition, StadtLandFlussPlayer)
    if key == "hangman":
        return _player_score_card(user, definition, HangmanPlayer, HangmanLobby, lambda target: {"status": HangmanLobby.STATUS_FINISHED, "winner": target})
    if key == "uno":
        return _winner_game_card(user, definition, UnoPlayer, UnoGame)
    if key == "kniffel":
        return _winner_game_card(user, definition, KniffelPlayer, KniffelGame)
    if key == "pong":
        return _pong_game_card(user, definition)
    if key == "snake_powerups":
        return _snake_powerups_card(user, definition)
    return _base_game_card(definition)


def get_profile_game_cards(user, profile, visible_only=True):
    cards = []
    for setting in get_profile_game_card_settings(profile):
        if visible_only and not setting["visible"]:
            continue
        card = build_profile_game_card(setting, user)
        card["visible"] = setting["visible"]
        cards.append(card)
    return cards


def get_friend_users(user):
    friend_ids = Friendship.friend_ids_for_user(user)

    if not friend_ids:
        return User.objects.none()

    return User.objects.filter(id__in=friend_ids, is_active=True).order_by("username")


def get_friend_profiles(user, limit=None):
    friendships = list(Friendship.accepted_for_user(user))

    if not friendships:
        return []

    friend_ids = []
    friendship_since_by_user_id = {}

    for friendship in friendships:
        friend_user = friendship.other_user(user)

        if not friend_user or not friend_user.is_active:
            continue

        friend_ids.append(friend_user.id)
        friendship_since_by_user_id[friend_user.id] = friendship.updated_at

    if not friend_ids:
        return []

    friends = list(
        User.objects
        .filter(id__in=friend_ids, is_active=True)
        .order_by("username")
    )

    if limit:
        friends = friends[:limit]

    ensure_profiles_for_users(friends)

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user__in=friends)
        .order_by("user__username")
    )
    decorate_profiles_with_presence(profiles)

    for profile in profiles:
        profile.friendship_since = friendship_since_by_user_id.get(profile.user_id)

    return profiles


def can_view_private_profile_area(viewer, profile_user):
    return viewer.is_authenticated and (viewer == profile_user or get_friendship_state(viewer, profile_user) == "friends")


def apply_profile_privacy(profile, viewer):
    owner = profile.user
    is_self = viewer.is_authenticated and viewer == owner
    is_friend = viewer.is_authenticated and get_friendship_state(viewer, owner) == "friends"
    if not (is_self or is_friend) and not profile.privacy_show_online:
        profile.is_online = False
        profile.last_seen_at = None
        profile.activity_status = ""
    if profile.status == UserProfile.STATUS_INVISIBLE and not is_self:
        profile.is_online = False
        profile.last_seen_at = None
        profile.activity_status = ""
    return profile


def get_friend_activity(profile_user, viewer):
    if not can_view_private_profile_area(viewer, profile_user):
        return []
    activity = []
    recent_chat_count = ChatRoom.objects.filter(room_memberships__user=profile_user).distinct().count()
    if recent_chat_count:
        activity.append({"icon": "fa-solid fa-comments", "label": _("Aktive Chats"), "value": recent_chat_count})
    score_count = get_total_profile_highscores(profile_user)
    if score_count:
        activity.append({"icon": "fa-solid fa-trophy", "label": _("Highscores"), "value": score_count})
    return activity


def get_profile_favorite_tools(request, profile_user, limit=6):
    favorite_keys = list(
        ToolFavorite.objects
        .filter(user=profile_user)
        .values_list("tool_key", flat=True)[: max(limit * 2, limit)]
    )

    if not favorite_keys:
        return []

    favorite_key_set = set(favorite_keys)
    tools_by_key = {
        tool["key"]: tool
        for tool in resolve_tools(request, favorite_key_set)
        if tool.get("is_favorite")
    }
    return [tools_by_key[key] for key in favorite_keys if key in tools_by_key][:limit]


def get_profile_recent_activity(request, profile_user, *, include_private=False, limit=6):
    if not include_private:
        return []

    is_self = request.user.is_authenticated and request.user == profile_user
    items = []

    for note in Note.objects.filter(user=profile_user, is_archived=False).order_by("-updated_at")[:3]:
        items.append({
            "icon": "fa-regular fa-note-sticky",
            "title": (note.title or _("Unbenannte Notiz")) if is_self else _("Notiz"),
            "meta": _("Notiz aktualisiert"),
            "time": timesince(note.updated_at),
            "timestamp": note.updated_at,
            "url": reverse("note_detail", args=[note.pk]) if is_self else "",
        })

    for share in FileShare.objects.filter(owner=profile_user).order_by("-created_at")[:3]:
        items.append({
            "icon": share.icon_class,
            "title": share.original_name if is_self else _("Datei"),
            "meta": _("Datei hochgeladen"),
            "time": timesince(share.created_at),
            "timestamp": share.created_at,
            "url": reverse("file_share") if is_self else "",
        })

    for message in (
        ChatMessage.objects
        .select_related("room")
        .filter(sender=profile_user)
        .order_by("-created_at")[:3]
    ):
        items.append({
            "icon": "fa-solid fa-comments",
            "title": message.room.title_for(profile_user) if is_self else _("Chat"),
            "meta": _("Chatnachricht geschrieben"),
            "time": timesince(message.created_at),
            "timestamp": message.created_at,
            "url": reverse("chat") if is_self else "",
        })

    favorite_tools = get_profile_favorite_tools(request, profile_user, limit=3)
    favorite_created = {
        favorite.tool_key: favorite.created_at
        for favorite in ToolFavorite.objects.filter(user=profile_user, tool_key__in=[tool["key"] for tool in favorite_tools])
    }
    for tool in favorite_tools:
        created_at = favorite_created.get(tool["key"])
        if not created_at:
            continue
        items.append({
            "icon": tool["icon"],
            "title": tool["label"],
            "meta": _("Tool favorisiert"),
            "time": timesince(created_at),
            "timestamp": created_at,
            "url": tool["url"] if is_self else "",
        })

    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items[:limit]


def get_friendship_state(viewer, profile_user):
    if not viewer.is_authenticated or viewer == profile_user:
        return "self" if viewer == profile_user else "none"

    friendship = Friendship.between(viewer, profile_user)

    if not friendship:
        return "none"

    if friendship.status == Friendship.STATUS_ACCEPTED:
        return "friends"

    if friendship.from_user_id == viewer.id:
        return "pending_sent"

    return "pending_received"


def is_blocked_between(user_a, user_b):
    if not user_a.is_authenticated or user_a == user_b:
        return False
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def _profile_presence_text(profile):
    if profile.activity_status:
        return str(profile.activity_status)

    if profile.is_online:
        return str(_("Online"))

    if profile.last_seen_at:
        return f'{_("Zuletzt online")} {timesince(profile.last_seen_at)}'

    return str(_("Offline"))


def _profile_presence_payload(profile):
    return {
        "userId": profile.user_id,
        "isOnline": bool(profile.is_online),
        "statusLine": _profile_presence_text(profile),
        "activityStatus": str(profile.activity_status or ""),
    }


@login_required
@require_GET
def user_presence_api(request):
    raw_ids = request.GET.get("ids", "")
    user_ids = []

    for raw_id in raw_ids.split(","):
        raw_id = raw_id.strip()
        if not raw_id.isdigit():
            continue

        user_id = int(raw_id)
        if user_id not in user_ids:
            user_ids.append(user_id)

        if len(user_ids) >= 50:
            break

    if not user_ids:
        return JsonResponse({"profiles": []})

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user_id__in=user_ids, user__is_active=True)
    )

    decorate_profiles_with_presence(profiles)

    for profile in profiles:
        apply_profile_privacy(profile, request.user)

    profiles_by_user_id = {profile.user_id: profile for profile in profiles}

    return JsonResponse({
        "profiles": [
            _profile_presence_payload(profiles_by_user_id[user_id])
            for user_id in user_ids
            if user_id in profiles_by_user_id
        ]
    })


@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        if request.POST.get("profile_action") == "game_cards":
            save_profile_game_card_settings(profile, request.POST)
            messages.success(request, _("Deine Profil-Spielkarten wurden gespeichert."))
            return redirect("profile")

        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        if form.is_valid():
            old_avatar = profile.avatar
            profile = form.save(commit=False)

            cropped_avatar = request.POST.get("avatar_cropped", "").strip()

            if cropped_avatar.startswith("data:image"):
                try:
                    _format_part, image_data = cropped_avatar.split(";base64,")
                    decoded_file = base64.b64decode(image_data)
                    optimized_avatar = optimize_uploaded_image(
                        ContentFile(decoded_file),
                        prefix=f"profile_{request.user.id}",
                        max_size=PROFILE_AVATAR_MAX_SIZE,
                        quality=82,
                        target_bytes=120 * 1024,
                    )

                    if profile.avatar:
                        profile.avatar.delete(save=False)

                    profile.avatar.save(
                        optimized_avatar.filename,
                        optimized_avatar.file,
                        save=False,
                    )
                except Exception:
                    messages.error(request, _("Das Profilbild konnte nicht verarbeitet werden."))
                    return redirect("profile")
            elif request.FILES.get("avatar"):
                try:
                    optimized_avatar = optimize_uploaded_image(
                        request.FILES["avatar"],
                        prefix=f"profile_{request.user.id}",
                        max_size=PROFILE_AVATAR_MAX_SIZE,
                        quality=82,
                        target_bytes=120 * 1024,
                    )

                    if old_avatar:
                        old_avatar.delete(save=False)

                    profile.avatar.save(
                        optimized_avatar.filename,
                        optimized_avatar.file,
                        save=False,
                    )
                except Exception:
                    messages.error(request, _("Das Profilbild konnte nicht verarbeitet werden."))
                    return redirect("profile")

            # Profil speichern
            profile.save()
            invalidate_notification_cache(request.user)

            # User-Daten speichern:
            # Vorname, Nachname, E-Mail und Benutzername liegen NICHT im UserProfile,
            # sondern direkt im Django-User.
            request.user.username = form.cleaned_data.get("username", "").strip()
            request.user.first_name = form.cleaned_data.get("first_name", "").strip()
            request.user.last_name = form.cleaned_data.get("last_name", "").strip()
            request.user.email = form.cleaned_data.get("email", "").strip()

            request.user.save(update_fields=[
                "username",
                "first_name",
                "last_name",
                "email",
            ])

            messages.success(request, _("Dein Profil wurde gespeichert."))
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    incoming_requests = (
        Friendship.objects
        .select_related("from_user", "from_user__profile")
        .filter(to_user=request.user, status=Friendship.STATUS_PENDING)
        .order_by("-created_at")
    )
    outgoing_requests = (
        Friendship.objects
        .select_related("to_user", "to_user__profile")
        .filter(from_user=request.user, status=Friendship.STATUS_PENDING)
        .order_by("-created_at")
    )
    friends_count = Friendship.accepted_for_user(request.user).count()
    chat_rooms_count = ChatRoom.objects.filter(room_memberships__user=request.user).distinct().count()
    total_highscores_count = get_total_profile_highscores(request.user)
    achievement_summary = get_achievement_summary(request.user)
    profile_favorite_tools = get_profile_favorite_tools(request, request.user)

    return render(request, "app/profile.html", {
        "form": form,
        "profile": profile,
        "profile_game_card_settings": get_profile_game_card_settings(profile),
        "incoming_friend_requests": incoming_requests,
        "outgoing_friend_requests": outgoing_requests,
        "friends_preview": get_friend_profiles(request.user, limit=6),
        "friends_count": friends_count,
        "chat_rooms_count": chat_rooms_count,
        "total_highscores_count": total_highscores_count,
        "profile_spotlight_stats": get_profile_spotlight_stats(
            request.user,
            achievement_summary,
            friends_count=friends_count,
            highscore_count=total_highscores_count,
            include_private=True,
        ),
        "profile_favorite_tools": profile_favorite_tools,
        "profile_recent_activity": get_profile_recent_activity(request, request.user, include_private=True),
        "gallery_form": ProfileGalleryImageForm(),
        "gallery_images": ProfileGalleryImage.objects.filter(user=request.user)[:12],
        "blocked_users": UserBlock.objects.select_related("blocked", "blocked__profile").filter(blocker=request.user)[:20],
    })


def ensure_profiles_for_users(users):
    existing_profile_user_ids = set(
        UserProfile.objects
        .filter(user__in=users)
        .values_list("user_id", flat=True)
    )

    profiles_to_create = [
        UserProfile(user=user)
        for user in users
        if user.id not in existing_profile_user_ids
    ]

    if profiles_to_create:
        UserProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)


@login_required
def users_view(request):
    query = request.GET.get("q", "").strip()

    blocked_ids = set(UserBlock.objects.filter(blocker=request.user).values_list("blocked_id", flat=True))
    blocked_ids |= set(UserBlock.objects.filter(blocked=request.user).values_list("blocker_id", flat=True))
    users_qs = User.objects.filter(is_active=True).exclude(id__in=blocked_ids)

    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__bio__icontains=query)
        ).distinct()

    users = list(users_qs.order_by("username"))
    ensure_profiles_for_users(users)

    profiles = list(
        UserProfile.objects
        .select_related("user")
        .filter(user__in=users)
        .order_by("user__username")
    )

    decorate_profiles_with_presence(profiles)

    for profile in profiles:
        profile.friendship_state = get_friendship_state(request.user, profile.user)
        apply_profile_privacy(profile, request.user)
        profile.activity_summary = get_friend_activity(profile.user, request.user)

    return render(request, "app/users.html", {
        "profiles": profiles,
        "query": query,
        "total_users": User.objects.filter(is_active=True).count(),
    })


@login_required
def public_profile_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    decorate_users_with_presence([profile_user])
    profile.is_online = getattr(profile_user, "is_online", False)
    profile.last_seen_at = getattr(profile_user, "last_seen_at", None)
    profile.activity_status = getattr(profile_user, "activity_status", "")
    apply_profile_privacy(profile, request.user)
    blocked_by_viewer = UserBlock.objects.filter(blocker=request.user, blocked=profile_user).exists()
    viewer_blocked = UserBlock.objects.filter(blocker=profile_user, blocked=request.user).exists()
    friends_count = Friendship.accepted_for_user(profile_user).count()
    chat_rooms_count = ChatRoom.objects.filter(room_memberships__user=profile_user).distinct().count()
    total_highscores_count = get_total_profile_highscores(profile_user)
    can_view_private_area = can_view_private_profile_area(request.user, profile_user)
    can_view_highscores = profile.privacy_show_highscores or can_view_private_area
    can_view_achievements = profile.privacy_show_achievements or can_view_private_area
    can_view_private_achievements = can_view_private_area
    achievement_summary = None
    if can_view_achievements:
        achievement_summary = get_achievement_summary(
            profile_user,
            include_private=can_view_private_achievements,
            include_games=can_view_highscores,
        )

    return render(request, "app/public_profile.html", {
        "profile_user": profile_user,
        "profile": profile,
        "benchmark_highscores": get_profile_human_benchmark_highscores(profile_user) if can_view_highscores else [],
        "cookie_highscore": get_profile_cookie_highscore(profile_user) if can_view_highscores else None,
        "game_2048_highscore": get_profile_2048_highscore(profile_user) if can_view_highscores else None,
        "profile_game_cards": get_profile_game_cards(profile_user, profile) if can_view_highscores else [],
        "friendship_state": get_friendship_state(request.user, profile_user),
        "friends_preview": get_friend_profiles(profile_user, limit=6) if profile.privacy_show_friends or can_view_private_area else [],
        "can_view_friends": profile.privacy_show_friends or can_view_private_area,
        "can_use_chat_button": profile.privacy_show_chat_button or can_view_private_area,
        "friend_activity": get_friend_activity(profile_user, request.user),
        "profile_favorite_tools": get_profile_favorite_tools(request, profile_user) if can_view_private_area else [],
        "profile_recent_activity": get_profile_recent_activity(request, profile_user, include_private=can_view_private_area),
        "achievement_summary": achievement_summary,
        "profile_spotlight_stats": get_profile_spotlight_stats(
            profile_user,
            achievement_summary,
            friends_count=friends_count,
            highscore_count=total_highscores_count if can_view_highscores else 0,
            include_private=False,
        ),
        "can_view_private_achievements": can_view_private_achievements,
        "can_view_achievements": can_view_achievements,
        "friends_count": friends_count,
        "chat_rooms_count": chat_rooms_count,
        "total_highscores_count": total_highscores_count,
        "blocked_by_viewer": blocked_by_viewer,
        "viewer_blocked": viewer_blocked,
        "report_form": UserReportForm(),
        "gallery_images": ProfileGalleryImage.objects.filter(user=profile_user, is_public=True)[:12] if not viewer_blocked else [],
        "skribble_stats": SkribbleStats.objects.filter(user=profile_user).first(),
    })


@login_required
def friends_list_view(request, user_id):
    profile_user = get_object_or_404(User, id=user_id, is_active=True)
    profile, created = UserProfile.objects.get_or_create(user=profile_user)
    if not (profile.privacy_show_friends or can_view_private_profile_area(request.user, profile_user)):
        messages.info(request, _("Diese Freundesliste ist privat."))
        return redirect("public_profile", user_id=profile_user.id)
    friends = get_friend_profiles(profile_user)
    for friend_profile in friends:
        friend_profile.friendship_state = get_friendship_state(request.user, friend_profile.user)
        apply_profile_privacy(friend_profile, request.user)
        friend_profile.activity_summary = get_friend_activity(friend_profile.user, request.user)

    return render(request, "app/friends.html", {
        "profile_user": profile_user,
        "profile": profile,
        "friends": friends,
        "friends_count": Friendship.accepted_for_user(profile_user).count(),
    })


@login_required
@require_POST
def friendship_action_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    action = request.POST.get("action", "").strip()
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"

    if target_user == request.user:
        messages.error(request, _("Du kannst dir selbst keine Freundschaftsanfrage senden."))
        return redirect(next_url)

    if is_blocked_between(request.user, target_user):
        messages.error(request, _("Diese Aktion ist wegen einer Blockierung nicht möglich."))
        return redirect(next_url)

    friendship = Friendship.between(request.user, target_user)

    if action == "send":
        if friendship:
            if friendship.status == Friendship.STATUS_ACCEPTED:
                messages.info(request, _("Ihr seid bereits befreundet."))
            elif friendship.from_user_id == request.user.id:
                messages.info(request, _("Deine Freundschaftsanfrage ist bereits offen."))
            else:
                friendship.status = Friendship.STATUS_ACCEPTED
                friendship.save(update_fields=["status", "updated_at"])
                messages.success(request, _("Freundschaftsanfrage angenommen."))
        else:
            Friendship.objects.create(from_user=request.user, to_user=target_user)
            target_profile, _created = UserProfile.objects.get_or_create(user=target_user)
            muted_by_dnd = target_profile.status == UserProfile.STATUS_DND and target_profile.dnd_silence_notifications
            if target_profile.notify_friend_requests and not muted_by_dnd:
                InboxItem.objects.create(
                    user=target_user,
                    item_type=InboxItem.TYPE_FRIEND,
                    title=_("Neue Freundschaftsanfrage"),
                    message=f"{request.user.username} möchte dich hinzufügen.",
                    target_url=reverse("profile") + "#friend-requests",
                    icon="fa-solid fa-user-plus",
                )
            messages.success(request, _("Freundschaftsanfrage gesendet."))

    elif action == "accept":
        if friendship and friendship.to_user_id == request.user.id and friendship.status == Friendship.STATUS_PENDING:
            friendship.status = Friendship.STATUS_ACCEPTED
            friendship.save(update_fields=["status", "updated_at"])
            messages.success(request, _("Freundschaftsanfrage angenommen."))
        else:
            messages.error(request, _("Diese Freundschaftsanfrage konnte nicht angenommen werden."))

    elif action in ["decline", "cancel"]:
        if friendship and friendship.status == Friendship.STATUS_PENDING:
            if action == "decline" and friendship.to_user_id != request.user.id:
                messages.error(request, _("Diese Freundschaftsanfrage kannst du nicht ablehnen."))
            elif action == "cancel" and friendship.from_user_id != request.user.id:
                messages.error(request, _("Diese Freundschaftsanfrage kannst du nicht zurückziehen."))
            else:
                friendship.delete()
                messages.success(request, _("Freundschaftsanfrage entfernt."))
        else:
            messages.error(request, _("Es gibt keine offene Freundschaftsanfrage."))

    elif action == "remove":
        if friendship and friendship.status == Friendship.STATUS_ACCEPTED:
            friendship.delete()
            messages.success(request, _("Freundschaft entfernt."))
        else:
            messages.error(request, _("Ihr seid aktuell nicht befreundet."))

    else:
        messages.error(request, _("Unbekannte Freundschafts-Aktion."))

    return redirect(next_url)


@login_required
@require_POST
def profile_gallery_upload_view(request):
    form = ProfileGalleryImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save(commit=False)
        image.user = request.user

        if request.FILES.get("image"):
            try:
                optimized_gallery_image = optimize_uploaded_image(
                    request.FILES["image"],
                    prefix=f"gallery_{request.user.id}",
                    max_size=GALLERY_IMAGE_MAX_SIZE,
                    quality=84,
                    target_bytes=450 * 1024,
                )
                image.image.save(
                    optimized_gallery_image.filename,
                    optimized_gallery_image.file,
                    save=False,
                )
            except Exception:
                messages.error(request, _("Das Galeriebild konnte nicht verarbeitet werden."))
                return redirect("profile")

        image.save()
        messages.success(request, _("Galeriebild hochgeladen."))
    else:
        messages.error(request, _("Das Galeriebild konnte nicht hochgeladen werden."))
    return redirect("profile")


@login_required
@require_POST
def delete_gallery_image_view(request, image_id):
    image = get_object_or_404(ProfileGalleryImage, id=image_id, user=request.user)
    image.image.delete(save=False)
    image.delete()
    messages.success(request, _("Galeriebild gelöscht."))
    return redirect("profile")


@login_required
@require_POST
def block_user_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"
    if target_user == request.user:
        messages.error(request, _("Du kannst dich nicht selbst blockieren."))
        return redirect(next_url)
    action = request.POST.get("action", "block")
    if action == "unblock":
        UserBlock.objects.filter(blocker=request.user, blocked=target_user).delete()
        messages.success(request, _("Blockierung aufgehoben."))
    else:
        UserBlock.objects.get_or_create(blocker=request.user, blocked=target_user)
        Friendship.objects.filter(Q(from_user=request.user, to_user=target_user) | Q(from_user=target_user, to_user=request.user)).delete()
        messages.success(request, _("Nutzer blockiert."))
    return redirect(next_url)


@login_required
@require_POST
def report_user_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_active=True)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "users"
    if target_user == request.user:
        messages.error(request, _("Du kannst dich nicht selbst melden."))
        return redirect(next_url)
    form = UserReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.reporter = request.user
        report.reported = target_user
        report.save()
        messages.success(request, _("Meldung wurde gespeichert."))
    else:
        messages.error(request, _("Die Meldung konnte nicht gespeichert werden."))
    return redirect(next_url)


def _is_valid_hex_color(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    if len(value) != 7 or not value.startswith('#'):
        return False
    return all(char in '0123456789abcdefABCDEF' for char in value[1:])


@login_required
def profile_card_designer_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        style_values = {choice[0] for choice in UserProfile.CARD_STYLE_CHOICES}
        pattern_values = {choice[0] for choice in UserProfile.CARD_PATTERN_CHOICES}
        pattern_strength_values = {choice[0] for choice in UserProfile.CARD_PATTERN_STRENGTH_CHOICES}
        radius_values = {choice[0] for choice in UserProfile.CARD_RADIUS_CHOICES}
        avatar_values = {choice[0] for choice in UserProfile.CARD_AVATAR_CHOICES}
        text_effect_values = {choice[0] for choice in UserProfile.CARD_TEXT_EFFECT_CHOICES}
        gradient_values = {choice[0] for choice in UserProfile.CARD_GRADIENT_CHOICES}

        style = request.POST.get("profile_card_style", profile.profile_card_style)
        pattern = request.POST.get("profile_card_pattern", profile.profile_card_pattern)
        pattern_strength = request.POST.get("profile_card_pattern_strength", profile.profile_card_pattern_strength)
        gradient_angle = request.POST.get("profile_card_gradient_angle", profile.profile_card_gradient_angle)
        radius = request.POST.get("profile_card_radius", profile.profile_card_radius)
        avatar_shape = request.POST.get("profile_card_avatar_shape", profile.profile_card_avatar_shape)
        text_effect = request.POST.get("profile_card_text_effect", profile.profile_card_text_effect)
        primary = request.POST.get("profile_card_primary", profile.profile_card_primary)
        secondary = request.POST.get("profile_card_secondary", profile.profile_card_secondary)
        tertiary = request.POST.get("profile_card_tertiary", profile.profile_card_tertiary)
        text = request.POST.get("profile_card_text", profile.profile_card_text)
        border = request.POST.get("profile_card_border", profile.profile_card_border)
        badge_bg = request.POST.get("profile_card_badge_bg", profile.profile_card_badge_bg)
        badge_icon = request.POST.get("profile_card_badge_icon", profile.profile_card_badge_icon).strip()
        badge_text = request.POST.get("profile_card_badge_text", profile.profile_card_badge_text).strip()

        if style in style_values:
            profile.profile_card_style = style
        if pattern in pattern_values:
            profile.profile_card_pattern = pattern
        if pattern_strength in pattern_strength_values:
            profile.profile_card_pattern_strength = pattern_strength
        if gradient_angle in gradient_values:
            profile.profile_card_gradient_angle = gradient_angle
        if radius in radius_values:
            profile.profile_card_radius = radius
        if avatar_shape in avatar_values:
            profile.profile_card_avatar_shape = avatar_shape
        if text_effect in text_effect_values:
            profile.profile_card_text_effect = text_effect

        color_fields = {
            "profile_card_primary": primary,
            "profile_card_secondary": secondary,
            "profile_card_tertiary": tertiary,
            "profile_card_text": text,
            "profile_card_border": border,
            "profile_card_badge_bg": badge_bg,
        }
        for field_name, color_value in color_fields.items():
            if _is_valid_hex_color(color_value):
                setattr(profile, field_name, color_value)

        if badge_icon:
            profile.profile_card_badge_icon = badge_icon[:40]
        else:
            profile.profile_card_badge_icon = "fa-solid fa-star"

        profile.profile_card_badge_text = badge_text[:28]
        profile.profile_card_glow = request.POST.get("profile_card_glow") == "on"
        profile.profile_card_shine = request.POST.get("profile_card_shine") == "on"
        profile.save(update_fields=[
            "profile_card_style",
            "profile_card_primary",
            "profile_card_secondary",
            "profile_card_tertiary",
            "profile_card_text",
            "profile_card_border",
            "profile_card_badge_bg",
            "profile_card_pattern",
            "profile_card_pattern_strength",
            "profile_card_gradient_angle",
            "profile_card_radius",
            "profile_card_avatar_shape",
            "profile_card_text_effect",
            "profile_card_glow",
            "profile_card_shine",
            "profile_card_badge_icon",
            "profile_card_badge_text",
        ])
        messages.success(request, _("Profilkarte wurde gespeichert."))
        return redirect("profile_card_designer")

    return render(request, "app/profile_card_designer.html", {
        "profile": profile,
        "style_choices": UserProfile.CARD_STYLE_CHOICES,
        "pattern_choices": UserProfile.CARD_PATTERN_CHOICES,
        "pattern_strength_choices": UserProfile.CARD_PATTERN_STRENGTH_CHOICES,
        "gradient_choices": UserProfile.CARD_GRADIENT_CHOICES,
        "radius_choices": UserProfile.CARD_RADIUS_CHOICES,
        "avatar_choices": UserProfile.CARD_AVATAR_CHOICES,
        "text_effect_choices": UserProfile.CARD_TEXT_EFFECT_CHOICES,
    })
