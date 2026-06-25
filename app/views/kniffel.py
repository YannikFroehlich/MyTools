import json
import random
import string
from collections import Counter
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import OperationalError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..models import Friendship, KniffelGame, KniffelInvite, KniffelPlayer, UserProfile


KNIFFEL_PLAYER_TIMEOUT = timedelta(seconds=45)
MAX_ROLLS = 3
TOTAL_CATEGORIES = 13

UPPER_CATEGORIES = (
    ("ones", _("Einser"), _("Nur gewürfelte Einsen"), 1),
    ("twos", _("Zweier"), _("Nur gewürfelte Zweien"), 2),
    ("threes", _("Dreier"), _("Nur gewürfelte Dreien"), 3),
    ("fours", _("Vierer"), _("Nur gewürfelte Vieren"), 4),
    ("fives", _("Fünfer"), _("Nur gewürfelte Fünfen"), 5),
    ("sixes", _("Sechser"), _("Nur gewürfelte Sechsen"), 6),
)

LOWER_CATEGORIES = (
    ("three_kind", _("Dreierpasch"), _("Mindestens drei gleiche, Summe aller Würfel")),
    ("four_kind", _("Viererpasch"), _("Mindestens vier gleiche, Summe aller Würfel")),
    ("full_house", _("Full House"), _("Ein Paar und ein Drilling")),
    ("small_straight", _("Kleine Straße"), _("Vier Zahlen in Folge")),
    ("large_straight", _("Große Straße"), _("Fünf Zahlen in Folge")),
    ("kniffel", _("Kniffel"), _("Fünf gleiche Würfel")),
    ("chance", _("Chance"), _("Summe aller Würfel")),
)

CATEGORY_ORDER = [key for key, *_rest in UPPER_CATEGORIES] + [key for key, *_rest in LOWER_CATEGORIES]


def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not KniffelGame.objects.filter(code=code).exists():
            return code


def _player_name(user):
    return user.get_full_name() or user.username if user else ""


def _database_lock_guard(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except OperationalError as exc:
            message = str(exc).lower()
            if "locked" not in message and "busy" not in message:
                raise
            return JsonResponse({
                "ok": False,
                "error": _("Das Spiel ist gerade besch\u00e4ftigt. Bitte versuche es nochmal."),
            }, status=503)

    return wrapped


def _ordered_players(game):
    return list(game.players.select_related("user", "user__profile").order_by("seat", "joined_at"))


def _profile_payload(user):
    profile = getattr(user, "profile", None)
    if profile:
        return {
            "avatarUrl": profile.avatar_url,
            "initials": profile.initials,
        }
    return {
        "avatarUrl": "",
        "initials": (user.username[:2] or "MT").upper(),
    }


def _append_log(game, text):
    log = list(game.action_log or [])
    log.append(str(text))
    game.action_log = log[-10:]


def _score_category(category, dice):
    dice = [int(value) for value in dice if 1 <= int(value) <= 6]
    counts = Counter(dice)
    total = sum(dice)

    for key, _label, _description, face in UPPER_CATEGORIES:
        if category == key:
            return counts[face] * face

    if category == "three_kind":
        return total if counts and max(counts.values()) >= 3 else 0
    if category == "four_kind":
        return total if counts and max(counts.values()) >= 4 else 0
    if category == "full_house":
        values = sorted(counts.values())
        return 25 if values == [2, 3] else 0
    if category == "small_straight":
        unique = set(dice)
        straights = ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6})
        return 30 if any(straight.issubset(unique) for straight in straights) else 0
    if category == "large_straight":
        unique = set(dice)
        return 40 if unique in ({1, 2, 3, 4, 5}, {2, 3, 4, 5, 6}) else 0
    if category == "kniffel":
        return 50 if counts and max(counts.values()) == 5 else 0
    if category == "chance":
        return total
    return 0


def _score_summary(scores):
    upper = sum(int(scores.get(key, 0) or 0) for key, *_rest in UPPER_CATEGORIES)
    bonus = 35 if upper >= 63 else 0
    lower = sum(int(scores.get(key, 0) or 0) for key, *_rest in LOWER_CATEGORIES)
    return {
        "upper": upper,
        "bonus": bonus,
        "lower": lower,
        "total": upper + bonus + lower,
        "filled": len([key for key in CATEGORY_ORDER if key in scores]),
    }


def _scores_for(game, user_id):
    scores = game.scores if isinstance(game.scores, dict) else {}
    return dict(scores.get(str(user_id), {}))


def _set_score(game, user_id, category, score):
    scores = game.scores if isinstance(game.scores, dict) else {}
    player_scores = dict(scores.get(str(user_id), {}))
    player_scores[category] = int(score)
    scores[str(user_id)] = player_scores
    game.scores = scores


def _remove_score_sheet(game, user_id):
    scores = game.scores if isinstance(game.scores, dict) else {}
    scores.pop(str(user_id), None)
    game.scores = scores


def _reset_turn(game):
    game.roll_count = 0
    game.dice = []
    game.kept_indices = []


def _seat_for_new_player(game):
    taken = set(game.players.values_list("seat", flat=True))
    for seat in range(game.max_players):
        if seat not in taken:
            return seat
    return None


def _join_game(game, user):
    player = game.player_for_user(user)
    if player:
        KniffelPlayer.objects.filter(pk=player.pk).update(last_seen=timezone.now())
        return player
    if game.status != KniffelGame.STATUS_WAITING or game.is_full:
        return None
    seat = _seat_for_new_player(game)
    if seat is None:
        return None
    return KniffelPlayer.objects.create(game=game, user=user, seat=seat)


def _start_game(game):
    players = _ordered_players(game)
    game.status = KniffelGame.STATUS_PLAYING
    game.current_player_index = 0
    game.round_number = 1
    game.scores = {str(player.user_id): {} for player in players}
    game.winner_user_id = None
    game.action_log = [_("Kniffel-Runde gestartet.")]
    game.last_move_at = timezone.now()
    _reset_turn(game)


def _game_is_complete(game, players=None):
    players = players or _ordered_players(game)
    return bool(players) and all(_score_summary(_scores_for(game, player.user_id))["filled"] >= TOTAL_CATEGORIES for player in players)


def _finish_game_if_complete(game, players=None):
    players = players or _ordered_players(game)
    if not _game_is_complete(game, players):
        return False
    ranked = sorted(
        players,
        key=lambda player: _score_summary(_scores_for(game, player.user_id))["total"],
        reverse=True,
    )
    game.status = KniffelGame.STATUS_FINISHED
    game.winner_user_id = ranked[0].user_id if ranked else None
    _reset_turn(game)
    if ranked:
        _append_log(game, _("%(name)s gewinnt die Kniffel-Runde.") % {"name": ranked[0].display_label})
    return True


def _advance_turn(game):
    players = _ordered_players(game)
    if _finish_game_if_complete(game, players):
        return

    old_index = game.current_player_index % len(players)
    next_index = old_index
    for step in range(1, len(players) + 1):
        candidate_index = (old_index + step) % len(players)
        candidate = players[candidate_index]
        if _score_summary(_scores_for(game, candidate.user_id))["filled"] < TOTAL_CATEGORIES:
            next_index = candidate_index
            if candidate_index <= old_index:
                game.round_number += 1
            break

    game.current_player_index = next_index
    _reset_turn(game)


def _reset_to_waiting_lobby(game):
    game.status = KniffelGame.STATUS_WAITING
    game.current_player_index = 0
    game.round_number = 1
    game.scores = {}
    game.winner_user_id = None
    game.last_move_at = None
    _reset_turn(game)


def _remove_player_from_game(game, user):
    players_before = _ordered_players(game)
    removed_index = next((index for index, player in enumerate(players_before) if player.user_id == user.id), None)
    current_user_id = None
    if players_before:
        current_user_id = players_before[game.current_player_index % len(players_before)].user_id

    removed_count, _ = game.players.filter(user=user).delete()
    if removed_count:
        _remove_score_sheet(game, user.id)

    players_after = _ordered_players(game)
    if not players_after:
        return removed_count, removed_index, current_user_id

    if current_user_id in [player.user_id for player in players_after]:
        game.current_player_index = next(index for index, player in enumerate(players_after) if player.user_id == current_user_id)
    elif removed_index is not None:
        game.current_player_index = min(removed_index, len(players_after) - 1)
        _reset_turn(game)
    else:
        game.current_player_index = game.current_player_index % len(players_after)

    return removed_count, removed_index, current_user_id


def _cleanup_game_players(game, keep_user_id=None):
    stale_before = timezone.now() - KNIFFEL_PLAYER_TIMEOUT
    stale_players = [
        player
        for player in _ordered_players(game)
        if player.user_id != keep_user_id and player.last_seen < stale_before
    ]
    if not stale_players:
        return False

    for player in stale_players:
        _remove_player_from_game(game, player.user)

    players_after = _ordered_players(game)
    if not players_after:
        game.delete()
        return True

    if game.owner_id not in [player.user_id for player in players_after]:
        game.owner = players_after[0].user

    if game.status == KniffelGame.STATUS_PLAYING:
        if len(players_after) >= 2:
            _append_log(game, _("Inaktive Spieler wurden entfernt. Die Runde läuft weiter."))
            _finish_game_if_complete(game, players_after)
        else:
            _reset_to_waiting_lobby(game)
            _append_log(game, _("Inaktive Spieler wurden entfernt. Warte auf weitere Spieler."))
    else:
        game.current_player_index = game.current_player_index % len(players_after)

    game.save()
    return False


def _cleanup_stale_games():
    for game in KniffelGame.objects.prefetch_related("players", "players__user").all():
        _cleanup_game_players(game)
    KniffelGame.objects.filter(players__isnull=True).delete()


def _home_games_for_user(user):
    return (
        KniffelGame.objects
        .filter(Q(owner=user) | Q(players__user=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        KniffelInvite.objects
        .select_related("game", "from_user")
        .filter(to_user=user, status=KniffelInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _serialize_home_game(game):
    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "playerCount": game.players.count(),
        "maxPlayers": game.max_players,
        "url": reverse("kniffel_lobby", args=[game.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.game.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("kniffel_invite_response", args=[invite.id]),
        "declineUrl": reverse("kniffel_invite_response", args=[invite.id]),
    }


def _friend_invite_rows(game, user):
    if game.is_full or game.status != KniffelGame.STATUS_WAITING:
        return []
    current_player_ids = list(game.players.values_list("user_id", flat=True))
    friends = (
        User.objects
        .filter(id__in=Friendship.friend_ids_for_user(user), is_active=True)
        .exclude(id__in=current_player_ids)
        .order_by("username")
    )
    UserProfile.objects.bulk_create(
        [UserProfile(user=friend) for friend in friends if not hasattr(friend, "profile")],
        ignore_conflicts=True,
    )
    invited_friend_ids = set(game.invites.filter(status=KniffelInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted_invite_ids = set(game.invites.filter(status=KniffelInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    return [
        {
            "user": friend,
            "is_invited": friend.id in invited_friend_ids,
            "was_invited": friend.id in accepted_invite_ids,
        }
        for friend in friends
    ]


def _parse_kept_indices(raw_value):
    if not raw_value:
        return []
    try:
        if raw_value.strip().startswith("["):
            values = json.loads(raw_value)
        else:
            values = [value for value in raw_value.split(",") if value.strip()]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    cleaned = []
    for value in values:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= index <= 4 and index not in cleaned:
            cleaned.append(index)
    return sorted(cleaned)


def _category_payload(game, current_user_id, players):
    dice = game.dice if isinstance(game.dice, list) else []
    has_roll = game.roll_count > 0 and len(dice) == 5
    rows = []
    for section, categories in (("upper", UPPER_CATEGORIES), ("lower", LOWER_CATEGORIES)):
        for definition in categories:
            key = definition[0]
            label = definition[1]
            description = definition[2]
            current_scores = _scores_for(game, current_user_id)
            row = {
                "key": key,
                "label": str(label),
                "description": str(description),
                "section": section,
                "used": key in current_scores,
                "preview": _score_category(key, dice) if has_roll and key not in current_scores else None,
                "scoresByPlayer": {
                    str(player.user_id): _scores_for(game, player.user_id).get(key)
                    for player in players
                },
            }
            rows.append(row)
    return rows


def _serialize_game(game, user):
    players = _ordered_players(game)
    player = next((row for row in players if row.user_id == user.id), None)
    current = players[game.current_player_index % len(players)] if players else None
    winner = next((row for row in players if row.user_id == game.winner_user_id), None)
    user_scores = _scores_for(game, user.id)
    is_current_user = bool(current and current.user_id == user.id)
    can_roll = bool(player and is_current_user and game.status == KniffelGame.STATUS_PLAYING and game.roll_count < MAX_ROLLS)
    can_score = bool(player and is_current_user and game.status == KniffelGame.STATUS_PLAYING and game.roll_count > 0)

    if game.status == KniffelGame.STATUS_WAITING:
        message = _("Warte auf Spieler. Der Host startet ab 2 Spielern.")
    elif game.status == KniffelGame.STATUS_FINISHED:
        message = _("Gewonnen: %(name)s") % {"name": winner.display_label if winner else _("Unbekannt")}
    elif is_current_user and game.roll_count == 0:
        message = _("Du bist dran. Würfle bis zu drei Mal.")
    elif is_current_user and game.roll_count < MAX_ROLLS:
        message = _("Halte passende Würfel oder trage eine Kategorie ein.")
    elif is_current_user:
        message = _("Jetzt musst du eine Kategorie eintragen.")
    else:
        message = _("Warte auf %(name)s.") % {"name": current.display_label if current else _("Spieler")}

    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "status": game.status,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "isOwner": game.owner_id == user.id,
        "maxPlayers": game.max_players,
        "currentPlayerId": current.user_id if current else None,
        "currentPlayerName": current.display_label if current else "",
        "rollCount": game.roll_count,
        "maxRolls": MAX_ROLLS,
        "dice": game.dice if isinstance(game.dice, list) else [],
        "keptIndices": game.kept_indices if isinstance(game.kept_indices, list) else [],
        "canRoll": can_roll,
        "canScore": can_score,
        "canStart": game.owner_id == user.id and game.status == KniffelGame.STATUS_WAITING and len(players) >= 2,
        "message": message,
        "winnerName": winner.display_label if winner else "",
        "winnerUserId": game.winner_user_id,
        "players": [
            {
                "id": row.user_id,
                "name": row.display_label,
                **_profile_payload(row.user),
                "seat": row.seat,
                "isCurrent": current and row.user_id == current.user_id,
                "isYou": row.user_id == user.id,
                **_score_summary(_scores_for(game, row.user_id)),
            }
            for row in players
        ],
        "categories": _category_payload(game, user.id, players),
        "ownSummary": _score_summary(user_scores),
        "actionLog": game.action_log or [],
        "updatedAt": timezone.localtime(game.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


@login_required
def kniffel_home(request):
    _cleanup_stale_games()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            try:
                max_players = int(request.POST.get("max_players", 4) or 4)
            except (TypeError, ValueError):
                max_players = 4
            max_players = min(6, max(2, max_players))
            game = KniffelGame.objects.create(
                owner=request.user,
                name=(request.POST.get("name", "").strip() or _("Kniffel"))[:80],
                code=_generate_game_code(),
                max_players=max_players,
            )
            KniffelPlayer.objects.create(game=game, user=request.user, seat=0)
            return redirect("kniffel_lobby", code=game.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("kniffel_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/kniffel_home.html", {
        "my_games": _home_games_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
    })


@login_required
@require_GET
def kniffel_home_state_api(request):
    _cleanup_stale_games()
    return JsonResponse({
        "ok": True,
        "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)],
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
    })


@login_required
def kniffel_lobby(request, code):
    game = KniffelGame.objects.select_related("owner").filter(code=code.upper()).first()
    if not game:
        messages.warning(request, _("Diese Kniffel-Lobby existiert nicht mehr."))
        return redirect("kniffel_home")
    if not _join_game(game, request.user):
        messages.error(request, _("Dieser Kniffel-Raum ist voll oder läuft bereits."))
        return redirect("kniffel_home")
    return render(request, "app/kniffel_lobby.html", {
        "game": game,
        "friend_invite_rows": _friend_invite_rows(game, request.user),
    })


@login_required
@require_POST
def kniffel_invite_friend(request, code):
    game = get_object_or_404(KniffelGame, code=code.upper())
    if not (game.owner_id == request.user.id or game.player_for_user(request.user)) or game.is_full or game.status != KniffelGame.STATUS_WAITING:
        messages.error(request, _("Dieser Raum kann keine weiteren Spieler aufnehmen."))
        return redirect("kniffel_lobby", code=game.code)
    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("kniffel_lobby", code=game.code)
    KniffelInvite.objects.update_or_create(
        game=game,
        to_user=friend,
        defaults={"from_user": request.user, "status": KniffelInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("kniffel_lobby", code=game.code)


@login_required
@require_POST
def kniffel_invite_response(request, invite_id):
    invite = get_object_or_404(KniffelInvite.objects.select_related("game"), id=invite_id, to_user=request.user)
    if request.POST.get("action") == "accept":
        if invite.game.status != KniffelGame.STATUS_WAITING and not invite.game.player_for_user(request.user):
            invite.status = KniffelInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Kniffel-Raum läuft bereits."))
            return redirect("kniffel_home")
        if invite.game.is_full and not invite.game.player_for_user(request.user):
            invite.status = KniffelInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Kniffel-Raum ist bereits voll."))
            return redirect("kniffel_home")
        invite.status = KniffelInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("kniffel_lobby", code=invite.game.code)
    invite.status = KniffelInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("kniffel_home")


@login_required
@require_GET
def kniffel_state_api(request, code):
    game = KniffelGame.objects.filter(code=code.upper()).first()
    if not game:
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Kniffel-Raum wurde gelöscht."), "redirectUrl": reverse("kniffel_home")}, status=410)
    game.players.filter(user=request.user).update(last_seen=timezone.now())
    if _cleanup_game_players(game, keep_user_id=request.user.id):
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Kniffel-Raum wurde gelöscht."), "redirectUrl": reverse("kniffel_home")}, status=410)
    game.refresh_from_db()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def kniffel_start_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(KniffelGame.objects.select_for_update(of=("self",)), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann starten.")}, status=403)
        if game.status != KniffelGame.STATUS_WAITING or game.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Du brauchst mindestens zwei Spieler.")}, status=400)
        _start_game(game)
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def kniffel_roll_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(KniffelGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        current = players[game.current_player_index % len(players)] if players else None
        if not current or current.user_id != request.user.id or game.status != KniffelGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Du bist nicht am Zug.")}, status=400)
        if game.roll_count >= MAX_ROLLS:
            return JsonResponse({"ok": False, "error": _("Du hast schon dreimal gewürfelt.")}, status=400)

        kept_indices = _parse_kept_indices(request.POST.get("kept_indices", ""))
        dice = list(game.dice or [0, 0, 0, 0, 0])
        if game.roll_count == 0 or len(dice) != 5:
            kept_indices = []
            dice = [0, 0, 0, 0, 0]

        for index in range(5):
            if index not in kept_indices:
                dice[index] = random.randint(1, 6)

        game.dice = dice
        game.kept_indices = kept_indices
        game.roll_count += 1
        game.last_move_at = timezone.now()
        _append_log(game, _("%(name)s würfelt (%(count)s/3).") % {"name": current.display_label, "count": game.roll_count})
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def kniffel_score_api(request, code):
    category = request.POST.get("category", "")
    if category not in CATEGORY_ORDER:
        return JsonResponse({"ok": False, "error": _("Unbekannte Kategorie.")}, status=400)

    with transaction.atomic():
        game = get_object_or_404(KniffelGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        current = players[game.current_player_index % len(players)] if players else None
        if not current or current.user_id != request.user.id or game.status != KniffelGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Du bist nicht am Zug.")}, status=400)
        if game.roll_count <= 0 or len(game.dice or []) != 5:
            return JsonResponse({"ok": False, "error": _("Würfle zuerst.")}, status=400)
        player_scores = _scores_for(game, request.user.id)
        if category in player_scores:
            return JsonResponse({"ok": False, "error": _("Diese Kategorie ist schon belegt.")}, status=400)

        score = _score_category(category, game.dice)
        _set_score(game, request.user.id, category, score)
        label = next((str(row[1]) for row in [*UPPER_CATEGORIES, *LOWER_CATEGORIES] if row[0] == category), category)
        _append_log(game, _("%(name)s traegt %(category)s mit %(score)s Punkten ein.") % {
            "name": current.display_label,
            "category": label,
            "score": score,
        })
        _advance_turn(game)
        game.last_move_at = timezone.now()
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def kniffel_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(KniffelGame.objects.select_for_update(of=("self",)), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann neu starten.")}, status=403)
        if game.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Du brauchst mindestens zwei Spieler.")}, status=400)
        _start_game(game)
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def kniffel_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(KniffelGame.objects.select_for_update(), code=code.upper())
        removed_count, _removed_index, _current_user_id = _remove_player_from_game(game, request.user)
        if not removed_count:
            messages.info(request, _("Du bist nicht mehr in diesem Raum."))
            return redirect("kniffel_home")

        players_after = _ordered_players(game)
        if not players_after:
            game.delete()
            messages.info(request, _("Kniffel-Raum wurde gelöscht."))
            return redirect("kniffel_home")

        if game.owner_id == request.user.id:
            game.owner = players_after[0].user

        if game.status == KniffelGame.STATUS_PLAYING:
            if len(players_after) >= 2:
                _append_log(game, _("Ein Spieler hat den Raum verlassen. Die Runde läuft weiter."))
                _finish_game_if_complete(game, players_after)
            else:
                _reset_to_waiting_lobby(game)
                _append_log(game, _("Ein Spieler hat den Raum verlassen. Warte auf weitere Spieler."))
        else:
            game.current_player_index = game.current_player_index % len(players_after)

        game.invites.filter(status=KniffelInvite.STATUS_PENDING, to_user=request.user).update(status=KniffelInvite.STATUS_DECLINED)
        game.save()
    return redirect("kniffel_home")


@login_required
@require_POST
def kniffel_delete(request, code):
    game = get_object_or_404(KniffelGame, code=code.upper())
    if game.owner_id != request.user.id:
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("kniffel_home")
    game.delete()
    messages.success(request, _("Kniffel-Raum wurde gelöscht."))
    return redirect("kniffel_home")
