from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import UserPresence

ONLINE_WINDOW_MINUTES = 3
TOUCH_THROTTLE_SECONDS = 45


GAME_ACTIVITY_LABELS = {
    "uno": _("spielt Uno"),
    "tictactoe": _("spielt Tic Tac Toe"),
    "connectfour": _("spielt Vier gewinnt"),
    "battleship": _("spielt Schiffe versenken"),
    "stadtlandfluss": _("spielt Stadt Land Fluss"),
    "skribble": _("spielt Skribble"),
    "kniffel": _("spielt Kniffel"),
    "hangman": _("spielt Hangman"),
    "pong": _("spielt Pong"),
    "2048": _("spielt 2048"),
    "cookie_cosmos": _("spielt Cookie Cosmos"),
    "cookie_cosmos_v2": _("spielt Cookie Cosmos V2"),
    "nebula_forge_tycoon": _("spielt Nebula Forge Tycoon"),
    "drift_circuit": _("spielt Racing Game"),
    "human_benchmark": _("spielt Human Benchmark"),
    "snake_powerups": _("spielt Snake Powerups"),
}


ACTIVE_GAME_STATUSES = {"waiting", "setup", "playing", "round_summary"}


def touch_user_presence(user):
    if not getattr(user, "is_authenticated", False):
        return

    now = timezone.now()
    try:
        presence, created = UserPresence.objects.get_or_create(user=user)
        if created or presence.last_seen <= now - timezone.timedelta(seconds=TOUCH_THROTTLE_SECONDS):
            presence.last_seen = now
            presence.save(update_fields=["last_seen"])
    except Exception:
        pass


def mark_active_game(user, game_key, label=None):
    if not getattr(user, "is_authenticated", False):
        return

    label = label or GAME_ACTIVITY_LABELS.get(game_key, "")
    if not label:
        return

    now = timezone.now()
    try:
        UserPresence.objects.update_or_create(
            user=user,
            defaults={
                "last_seen": now,
                "active_game": game_key,
                "active_game_label": str(label),
                "active_game_updated_at": now,
            },
        )
    except Exception:
        pass


def online_cutoff():
    return timezone.now() - timezone.timedelta(minutes=ONLINE_WINDOW_MINUTES)


def _set_activity(activity_by_user_id, user_id, label, updated_at):
    if not user_id:
        return

    current = activity_by_user_id.get(user_id)
    if current and current["updated_at"] >= updated_at:
        return

    activity_by_user_id[user_id] = {
        "label": label,
        "updated_at": updated_at,
    }


def _collect_game_activity_for_users(user_ids):
    if not user_ids:
        return {}

    # Import here so basic presence updates cannot fail because of game-model import cycles.
    from .models import (
        BattleshipGame,
        ConnectFourGame,
        DrawingGameLobby,
        HangmanLobby,
        KniffelPlayer,
        PongGame,
        StadtLandFlussLobby,
        TicTacToeGame,
        UnoPlayer,
    )

    user_ids = set(user_ids)
    activity_by_user_id = {}

    for game in TicTacToeGame.objects.filter(
        Q(player_x_id__in=user_ids) | Q(player_o_id__in=user_ids),
        status__in=ACTIVE_GAME_STATUSES,
    ).only("player_x_id", "player_o_id", "status", "updated_at"):
        for user_id in (game.player_x_id, game.player_o_id):
            if user_id in user_ids:
                _set_activity(activity_by_user_id, user_id, GAME_ACTIVITY_LABELS["tictactoe"], game.updated_at)

    for game in ConnectFourGame.objects.filter(
        Q(player_red_id__in=user_ids) | Q(player_yellow_id__in=user_ids),
        status__in=ACTIVE_GAME_STATUSES,
    ).only("player_red_id", "player_yellow_id", "status", "updated_at"):
        for user_id in (game.player_red_id, game.player_yellow_id):
            if user_id in user_ids:
                _set_activity(activity_by_user_id, user_id, GAME_ACTIVITY_LABELS["connectfour"], game.updated_at)

    for game in BattleshipGame.objects.filter(
        Q(player_a_id__in=user_ids) | Q(player_b_id__in=user_ids),
        status__in=ACTIVE_GAME_STATUSES,
    ).only("player_a_id", "player_b_id", "status", "updated_at"):
        for user_id in (game.player_a_id, game.player_b_id):
            if user_id in user_ids:
                _set_activity(activity_by_user_id, user_id, GAME_ACTIVITY_LABELS["battleship"], game.updated_at)

    for player in UnoPlayer.objects.filter(
        user_id__in=user_ids,
        game__status__in=ACTIVE_GAME_STATUSES,
    ).select_related("game").only("user_id", "game__status", "game__updated_at"):
        _set_activity(activity_by_user_id, player.user_id, GAME_ACTIVITY_LABELS["uno"], player.game.updated_at)

    for player in KniffelPlayer.objects.filter(
        user_id__in=user_ids,
        game__status__in=ACTIVE_GAME_STATUSES,
    ).select_related("game").only("user_id", "game__status", "game__updated_at"):
        _set_activity(activity_by_user_id, player.user_id, GAME_ACTIVITY_LABELS["kniffel"], player.game.updated_at)

    for lobby in StadtLandFlussLobby.objects.filter(
        players__user_id__in=user_ids,
        status__in=ACTIVE_GAME_STATUSES,
    ).prefetch_related("players").only("status", "updated_at").distinct():
        for player in lobby.players.all():
            if player.user_id in user_ids:
                _set_activity(activity_by_user_id, player.user_id, GAME_ACTIVITY_LABELS["stadtlandfluss"], lobby.updated_at)

    for lobby in DrawingGameLobby.objects.filter(
        players__user_id__in=user_ids,
        status__in=ACTIVE_GAME_STATUSES,
    ).prefetch_related("players").only("status", "updated_at").distinct():
        for player in lobby.players.all():
            if player.user_id in user_ids:
                _set_activity(activity_by_user_id, player.user_id, GAME_ACTIVITY_LABELS["skribble"], lobby.updated_at)

    for lobby in HangmanLobby.objects.filter(
        players__user_id__in=user_ids,
        status__in=ACTIVE_GAME_STATUSES,
    ).prefetch_related("players").only("status", "updated_at").distinct():
        for player in lobby.players.all():
            if player.user_id in user_ids:
                _set_activity(activity_by_user_id, player.user_id, GAME_ACTIVITY_LABELS["hangman"], lobby.updated_at)

    for game in PongGame.objects.filter(
        Q(player_left_id__in=user_ids) | Q(player_right_id__in=user_ids),
        status__in=ACTIVE_GAME_STATUSES,
    ).only("player_left_id", "player_right_id", "status", "updated_at"):
        for user_id in (game.player_left_id, game.player_right_id):
            if user_id in user_ids:
                _set_activity(activity_by_user_id, user_id, GAME_ACTIVITY_LABELS["pong"], game.updated_at)

    recent_activity_cutoff = timezone.now() - timezone.timedelta(minutes=5)
    for presence in UserPresence.objects.filter(
        user_id__in=user_ids,
        active_game__isnull=False,
        active_game_updated_at__gte=recent_activity_cutoff,
    ).exclude(active_game="").only("user_id", "active_game", "active_game_label", "active_game_updated_at"):
        label = presence.active_game_label or GAME_ACTIVITY_LABELS.get(presence.active_game, "")
        if label:
            _set_activity(activity_by_user_id, presence.user_id, label, presence.active_game_updated_at)

    return activity_by_user_id


def decorate_users_with_presence(users):
    user_list = list(users)
    ids = [user.id for user in user_list if getattr(user, "id", None)]
    presences = {
        presence.user_id: presence
        for presence in UserPresence.objects.filter(user_id__in=ids)
    }
    cutoff = online_cutoff()
    activity_by_user_id = _collect_game_activity_for_users(ids)

    for user in user_list:
        presence = presences.get(user.id)
        user.is_online = bool(presence and presence.last_seen >= cutoff)
        user.last_seen_at = presence.last_seen if presence else None
        activity = activity_by_user_id.get(user.id)
        user.activity_status = activity["label"] if user.is_online and activity else ""

    return user_list


def decorate_profiles_with_presence(profiles):
    profile_list = list(profiles)
    decorate_users_with_presence([profile.user for profile in profile_list])
    for profile in profile_list:
        profile.is_online = getattr(profile.user, "is_online", False)
        profile.last_seen_at = getattr(profile.user, "last_seen_at", None)
        profile.activity_status = getattr(profile.user, "activity_status", "")
    return profile_list
