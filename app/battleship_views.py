import json
import random
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .models import BattleshipGame, BattleshipInvite, Friendship, UserProfile


BOARD_SIZE = 8
FLEET = [4, 3, 3, 2, 2]
FLEET_CONFIG = [
    {"id": "carrier", "name": _("Träger"), "length": 4},
    {"id": "cruiser", "name": _("Kreuzer"), "length": 3},
    {"id": "submarine", "name": _("U-Boot"), "length": 3},
    {"id": "destroyer", "name": _("Zerstörer"), "length": 2},
    {"id": "patrol", "name": _("Patrouille"), "length": 2},
]


def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not BattleshipGame.objects.filter(code=code).exists():
            return code


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _all_cells(fleet):
    cells = []
    for ship in (fleet if isinstance(fleet, list) else []):
        cells.extend(int(cell) for cell in ship.get("cells", []) if isinstance(cell, int) or str(cell).isdigit())
    return cells


def _generate_fleet():
    ships = []
    occupied = set()

    for index, length in enumerate(FLEET):
        for _attempt in range(400):
            horizontal = random.choice([True, False])
            row = random.randrange(BOARD_SIZE)
            col = random.randrange(BOARD_SIZE)
            if horizontal and col + length > BOARD_SIZE:
                continue
            if not horizontal and row + length > BOARD_SIZE:
                continue

            cells = [
                (row * BOARD_SIZE) + col + offset if horizontal else ((row + offset) * BOARD_SIZE) + col
                for offset in range(length)
            ]
            if occupied.intersection(cells):
                continue
            occupied.update(cells)
            ships.append({
                "id": f"ship-{index + 1}",
                "name": _("Schiff %(number)s") % {"number": index + 1},
                "length": length,
                "cells": cells,
            })
            break

    return ships


def _normalize_fleet(raw_fleet):
    if not isinstance(raw_fleet, list):
        raise ValueError(_("Ungültige Flotte."))

    required = {ship["id"]: ship for ship in FLEET_CONFIG}
    seen_ids = set()
    occupied = set()
    normalized = []

    for raw_ship in raw_fleet:
        if not isinstance(raw_ship, dict):
            raise ValueError(_("Ungültige Flotte."))

        ship_id = str(raw_ship.get("id", "")).strip()
        if ship_id not in required or ship_id in seen_ids:
            raise ValueError(_("Ungültige Schiffsauswahl."))
        seen_ids.add(ship_id)

        expected = required[ship_id]
        try:
            cells = [int(cell) for cell in raw_ship.get("cells", [])]
        except (TypeError, ValueError):
            raise ValueError(_("Ungültige Schiffsfelder."))

        if len(cells) != expected["length"] or len(set(cells)) != expected["length"]:
            raise ValueError(_("Ein Schiff hat die falsche Länge."))
        if any(cell < 0 or cell >= BOARD_SIZE * BOARD_SIZE for cell in cells):
            raise ValueError(_("Ein Schiff liegt außerhalb des Spielfelds."))
        if occupied.intersection(cells):
            raise ValueError(_("Schiffe dürfen sich nicht überlappen."))

        rows = {cell // BOARD_SIZE for cell in cells}
        cols = {cell % BOARD_SIZE for cell in cells}
        sorted_cells = sorted(cells)
        if len(rows) == 1:
            expected_cells = list(range(sorted_cells[0], sorted_cells[0] + expected["length"]))
        elif len(cols) == 1:
            expected_cells = [sorted_cells[0] + (BOARD_SIZE * offset) for offset in range(expected["length"])]
        else:
            raise ValueError(_("Schiffe müssen gerade platziert werden."))

        if sorted(expected_cells) != sorted_cells:
            raise ValueError(_("Schiffe müssen zusammenhängend platziert werden."))

        occupied.update(cells)
        normalized.append({
            "id": ship_id,
            "name": expected["name"],
            "length": expected["length"],
            "cells": sorted_cells,
        })

    if seen_ids != set(required.keys()):
        raise ValueError(_("Platziere alle Schiffe."))

    return normalized


def _is_fleet_sunk(fleet, shots):
    ship_cells = set(_all_cells(fleet))
    return bool(ship_cells) and ship_cells.issubset(set(shots or []))


def _sunk_ship_cells(fleet, shots):
    shot_set = set(shots or [])
    sunk = set()
    for ship in (fleet if isinstance(fleet, list) else []):
        cells = set(ship.get("cells", []))
        if cells and cells.issubset(shot_set):
            sunk.update(cells)
    return sorted(sunk)


def _reset_waiting_game(game):
    game.status = BattleshipGame.STATUS_WAITING
    game.fleet_a = []
    game.fleet_b = []
    game.shots_a = []
    game.shots_b = []
    game.ready_a = False
    game.ready_b = False
    game.current_turn = BattleshipGame.SIDE_A
    game.winner_side = ""
    game.last_move_at = None


def _home_games_for_user(user):
    return (
        BattleshipGame.objects
        .filter(Q(owner=user) | Q(player_a=user) | Q(player_b=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        BattleshipInvite.objects
        .select_related("game", "from_user")
        .filter(to_user=user, status=BattleshipInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _serialize_home_game(game):
    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "url": reverse("battleship_lobby", args=[game.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.game.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("battleship_invite_response", args=[invite.id]),
        "declineUrl": reverse("battleship_invite_response", args=[invite.id]),
    }


def _friend_invite_rows(game, user):
    if game.is_full:
        return []

    current_player_ids = [user_id for user_id in [game.player_a_id, game.player_b_id] if user_id]
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
    invited_friend_ids = set(
        game.invites
        .filter(status=BattleshipInvite.STATUS_PENDING)
        .values_list("to_user_id", flat=True)
    )
    accepted_invite_ids = set(
        game.invites
        .filter(status=BattleshipInvite.STATUS_ACCEPTED)
        .values_list("to_user_id", flat=True)
    )
    return [
        {
            "user": friend,
            "is_invited": friend.id in invited_friend_ids,
            "was_invited": friend.id in accepted_invite_ids,
        }
        for friend in friends
    ]


def _serialize_game(game, user):
    side = game.side_for_user(user)
    own_fleet = game.fleet_a if side == BattleshipGame.SIDE_A else game.fleet_b
    enemy_fleet = game.fleet_b if side == BattleshipGame.SIDE_A else game.fleet_a
    own_shots_received = game.shots_b if side == BattleshipGame.SIDE_A else game.shots_a
    own_shots_fired = game.shots_a if side == BattleshipGame.SIDE_A else game.shots_b
    own_ready = game.ready_a if side == BattleshipGame.SIDE_A else game.ready_b
    enemy_ready = game.ready_b if side == BattleshipGame.SIDE_A else game.ready_a
    enemy_ship_cells = set(_all_cells(enemy_fleet))
    own_ship_cells = set(_all_cells(own_fleet))
    can_attack = game.status == BattleshipGame.STATUS_PLAYING and side == game.current_turn

    if not game.is_full:
        message = _("Warte auf einen zweiten Kapitän.")
    elif game.status == BattleshipGame.STATUS_SETUP and not own_ready:
        message = _("Platziere deine Flotte.")
    elif game.status == BattleshipGame.STATUS_SETUP and not enemy_ready:
        message = _("Warte auf die gegnerische Flotte.")
    elif game.status == BattleshipGame.STATUS_FINISHED and game.winner_side == side:
        message = _("Du hast die Flotte versenkt.")
    elif game.status == BattleshipGame.STATUS_FINISHED:
        message = _("Deine Flotte wurde versenkt.")
    elif can_attack:
        message = _("Wähle ein Feld auf dem Radar.")
    else:
        message = _("Der Gegner ist am Zug.")

    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "status": game.status,
        "statusLabel": game.get_status_display(),
        "side": side,
        "boardSize": BOARD_SIZE,
        "roundNumber": game.round_number,
        "currentTurn": game.current_turn,
        "winnerSide": game.winner_side,
        "isOwner": game.owner_id == user.id,
        "fleetConfig": FLEET_CONFIG,
        "canAttack": can_attack,
        "canPlace": game.is_full and game.status in {BattleshipGame.STATUS_SETUP, BattleshipGame.STATUS_WAITING} and side and not own_ready,
        "message": message,
        "players": {
            "A": _player_name(game.player_a),
            "B": _player_name(game.player_b),
        },
        "readiness": {
            "A": game.ready_a,
            "B": game.ready_b,
        },
        "own": {
            "ships": sorted(own_ship_cells),
            "shotsReceived": own_shots_received or [],
            "hitsReceived": sorted(set(own_shots_received or []).intersection(own_ship_cells)),
            "sunk": _sunk_ship_cells(own_fleet, own_shots_received),
        },
        "enemy": {
            "shots": own_shots_fired or [],
            "hits": sorted(set(own_shots_fired or []).intersection(enemy_ship_cells)),
            "sunk": _sunk_ship_cells(enemy_fleet, own_shots_fired),
        },
    }


@login_required
def battleship_home(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            name = request.POST.get("name", "").strip() or _("Schiffe versenken")
            game = BattleshipGame.objects.create(
                owner=request.user,
                player_a=request.user,
                name=name[:80],
                code=_generate_game_code(),
            )
            return redirect("battleship_lobby", code=game.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("battleship_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/battleship_home.html", {
        "my_games": _home_games_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
    })


@login_required
@require_GET
def battleship_home_state_api(request):
    return JsonResponse({
        "ok": True,
        "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)],
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
    })


@login_required
def battleship_lobby(request, code):
    game = get_object_or_404(
        BattleshipGame.objects.select_related("owner", "player_a", "player_b"),
        code=code.upper(),
    )

    if not game.side_for_user(request.user) and not game.player_b_id:
        game.player_b = request.user
        game.status = BattleshipGame.STATUS_SETUP
        game.save(update_fields=["player_b", "status", "updated_at"])
    elif not game.side_for_user(request.user):
        messages.error(request, _("Dieser Schiffe-versenken-Raum ist bereits voll."))
        return redirect("battleship_home")

    if game.is_full and game.status == BattleshipGame.STATUS_WAITING:
        game.status = BattleshipGame.STATUS_SETUP
        game.save(update_fields=["status", "updated_at"])

    return render(request, "app/battleship_lobby.html", {
        "game": game,
        "friend_invite_rows": _friend_invite_rows(game, request.user),
    })


@login_required
@require_POST
def battleship_invite_friend(request, code):
    game = get_object_or_404(BattleshipGame, code=code.upper())
    if not (game.owner_id == request.user.id or game.side_for_user(request.user)) or game.is_full:
        messages.error(request, _("Dieser Raum hat bereits zwei Spieler."))
        return redirect("battleship_lobby", code=game.code)

    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("battleship_lobby", code=game.code)

    BattleshipInvite.objects.update_or_create(
        game=game,
        to_user=friend,
        defaults={"from_user": request.user, "status": BattleshipInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("battleship_lobby", code=game.code)


@login_required
@require_POST
def battleship_invite_response(request, invite_id):
    invite = get_object_or_404(
        BattleshipInvite.objects.select_related("game"),
        id=invite_id,
        to_user=request.user,
    )
    action = request.POST.get("action")
    if action == "accept":
        if invite.game.is_full and not invite.game.side_for_user(request.user):
            invite.status = BattleshipInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Schiffe-versenken-Raum ist bereits voll."))
            return redirect("battleship_home")
        invite.status = BattleshipInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("battleship_lobby", code=invite.game.code)

    invite.status = BattleshipInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("battleship_home")


@login_required
@require_GET
def battleship_state_api(request, code):
    game = BattleshipGame.objects.select_related("owner", "player_a", "player_b").filter(code=code.upper()).first()
    if not game:
        return JsonResponse({
            "ok": False,
            "gameDeleted": True,
            "error": _("Dieser Schiffe-versenken-Raum wurde gelöscht."),
            "redirectUrl": reverse("battleship_home"),
        }, status=410)

    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def battleship_place_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(
            BattleshipGame.objects.select_for_update().select_related("owner", "player_a", "player_b"),
            code=code.upper(),
        )
        side = game.side_for_user(request.user)
        if not side:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Raum.")}, status=403)
        if not game.is_full:
            return JsonResponse({"ok": False, "error": _("Warte auf einen zweiten Spieler.")}, status=400)

        fleet_payload = request.POST.get("fleet", "").strip()
        if fleet_payload:
            try:
                fleet = _normalize_fleet(json.loads(fleet_payload))
            except (json.JSONDecodeError, ValueError) as exc:
                return JsonResponse({"ok": False, "error": str(exc) or _("Ungültige Flotte.")}, status=400)
        else:
            fleet = _generate_fleet()

        if side == BattleshipGame.SIDE_A:
            game.fleet_a = fleet
            game.ready_a = True
        else:
            game.fleet_b = fleet
            game.ready_b = True

        if game.ready_a and game.ready_b:
            game.status = BattleshipGame.STATUS_PLAYING
            game.current_turn = BattleshipGame.SIDE_A
        else:
            game.status = BattleshipGame.STATUS_SETUP

        game.save()

    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def battleship_attack_api(request, code):
    try:
        index = int(request.POST.get("index"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": _("Ungültiges Feld.")}, status=400)
    if index < 0 or index >= BOARD_SIZE * BOARD_SIZE:
        return JsonResponse({"ok": False, "error": _("Ungültiges Feld.")}, status=400)

    with transaction.atomic():
        game = get_object_or_404(
            BattleshipGame.objects.select_for_update().select_related("owner", "player_a", "player_b"),
            code=code.upper(),
        )
        side = game.side_for_user(request.user)
        if game.status != BattleshipGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Das Gefecht läuft gerade nicht.")}, status=400)
        if side != game.current_turn:
            return JsonResponse({"ok": False, "error": _("Du bist noch nicht am Zug.")}, status=400)

        shots = list(game.shots_a if side == BattleshipGame.SIDE_A else game.shots_b)
        if index in shots:
            return JsonResponse({"ok": False, "error": _("Dieses Feld wurde schon beschossen.")}, status=400)
        shots.append(index)

        if side == BattleshipGame.SIDE_A:
            game.shots_a = shots
            enemy_fleet = game.fleet_b
            enemy_cells = set(_all_cells(enemy_fleet))
            if index not in enemy_cells:
                game.current_turn = BattleshipGame.SIDE_B
        else:
            game.shots_b = shots
            enemy_fleet = game.fleet_a
            enemy_cells = set(_all_cells(enemy_fleet))
            if index not in enemy_cells:
                game.current_turn = BattleshipGame.SIDE_A

        if _is_fleet_sunk(enemy_fleet, shots):
            game.status = BattleshipGame.STATUS_FINISHED
            game.winner_side = side

        game.last_move_at = timezone.now()
        game.save()

    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def battleship_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(BattleshipGame.objects.select_for_update(), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann eine neue Runde starten.")}, status=403)
        game.fleet_a = []
        game.fleet_b = []
        game.shots_a = []
        game.shots_b = []
        game.ready_a = False
        game.ready_b = False
        game.current_turn = BattleshipGame.SIDE_A
        game.winner_side = ""
        game.round_number += 1
        game.status = BattleshipGame.STATUS_SETUP if game.is_full else BattleshipGame.STATUS_WAITING
        game.last_move_at = None
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def battleship_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(BattleshipGame.objects.select_for_update(), code=code.upper())
        if game.player_a_id == request.user.id:
            game.player_a = None
        if game.player_b_id == request.user.id:
            game.player_b = None

        if not game.player_a_id and not game.player_b_id:
            game.delete()
            messages.info(request, _("Schiffe-versenken-Raum wurde gelöscht."))
            return redirect("battleship_home")

        if not game.player_a_id and game.player_b_id:
            game.player_a = game.player_b
            game.player_b = None

        _reset_waiting_game(game)
        game.invites.filter(status=BattleshipInvite.STATUS_PENDING).update(status=BattleshipInvite.STATUS_DECLINED)
        game.save()

    return redirect("battleship_home")


@login_required
@require_POST
def battleship_delete(request, code):
    game = get_object_or_404(BattleshipGame, code=code.upper())
    if game.owner_id != request.user.id and not game.side_for_user(request.user):
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("battleship_home")
    game.delete()
    messages.success(request, _("Schiffe-versenken-Raum wurde gelöscht."))
    return redirect("battleship_home")
