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

from .models import ConnectFourGame, ConnectFourInvite, Friendship, UserProfile


ROWS = 6
COLUMNS = 7
BOARD_SIZE = ROWS * COLUMNS
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]


def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not ConnectFourGame.objects.filter(code=code).exists():
            return code


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _index(row, column):
    return (row * COLUMNS) + column


def _winner_for_board(board):
    for row in range(ROWS):
        for column in range(COLUMNS):
            disc = board[_index(row, column)]
            if not disc:
                continue
            for row_delta, col_delta in DIRECTIONS:
                line = []
                for offset in range(4):
                    next_row = row + (row_delta * offset)
                    next_col = column + (col_delta * offset)
                    if next_row < 0 or next_row >= ROWS or next_col < 0 or next_col >= COLUMNS:
                        break
                    next_index = _index(next_row, next_col)
                    if board[next_index] != disc:
                        break
                    line.append(next_index)
                if len(line) == 4:
                    return disc, line
    return "", []


def _drop_row_for_column(board, column):
    for row in range(ROWS - 1, -1, -1):
        if not board[_index(row, column)]:
            return row
    return None


def _ensure_game_ready(game):
    if game.status == ConnectFourGame.STATUS_WAITING and game.player_red_id and game.player_yellow_id:
        game.status = ConnectFourGame.STATUS_PLAYING
        game.save(update_fields=["status", "updated_at"])


def _reset_waiting_game(game):
    game.board = [""] * BOARD_SIZE
    game.current_disc = ConnectFourGame.DISC_RED
    game.winner_disc = ""
    game.winning_line = []
    game.last_move = {}
    game.status = ConnectFourGame.STATUS_WAITING
    game.last_move_at = None


def _home_games_for_user(user):
    return (
        ConnectFourGame.objects
        .filter(Q(owner=user) | Q(player_red=user) | Q(player_yellow=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        ConnectFourInvite.objects
        .select_related("game", "from_user")
        .filter(to_user=user, status=ConnectFourInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _serialize_home_game(game):
    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "url": reverse("connectfour_lobby", args=[game.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.game.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("connectfour_invite_response", args=[invite.id]),
        "declineUrl": reverse("connectfour_invite_response", args=[invite.id]),
    }


def _friend_invite_rows(game, user):
    if game.player_yellow_id:
        return []
    current_player_ids = [user_id for user_id in [game.player_red_id, game.player_yellow_id] if user_id]
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
        .filter(status=ConnectFourInvite.STATUS_PENDING)
        .values_list("to_user_id", flat=True)
    )
    accepted_invite_ids = set(
        game.invites
        .filter(status=ConnectFourInvite.STATUS_ACCEPTED)
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


def _user_can_send_invites(game, user):
    return (game.owner_id == user.id or game.disc_for_user(user)) and not game.player_yellow_id


def _serialize_game(game, user):
    board = game.normalized_board
    player_disc = game.disc_for_user(user)
    is_players_turn = game.status == ConnectFourGame.STATUS_PLAYING and player_disc == game.current_disc

    if game.status == ConnectFourGame.STATUS_WAITING:
        message = _("Warte auf einen zweiten Spieler.")
    elif game.status == ConnectFourGame.STATUS_FINISHED and game.winner_disc:
        if game.winner_disc == player_disc:
            message = _("Du hast gewonnen.")
        elif player_disc:
            message = _("Dein Gegner hat gewonnen.")
        else:
            message = _("Spiel beendet.")
    elif game.status == ConnectFourGame.STATUS_FINISHED:
        message = _("Unentschieden.")
    elif is_players_turn:
        message = _("Du bist am Zug.")
    else:
        message = _("Warte auf den Zug deines Gegners.")

    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "status": game.status,
        "statusLabel": game.get_status_display(),
        "board": board,
        "rows": ROWS,
        "columns": COLUMNS,
        "currentDisc": game.current_disc,
        "winnerDisc": game.winner_disc,
        "winningLine": game.winning_line or [],
        "lastMove": game.last_move or {},
        "roundNumber": game.round_number,
        "playerDisc": player_disc,
        "canMove": is_players_turn,
        "message": message,
        "players": {
            "R": _player_name(game.player_red),
            "Y": _player_name(game.player_yellow),
        },
        "isOwner": game.owner_id == user.id,
        "updatedAt": timezone.localtime(game.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


@login_required
def connectfour_home(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            game = ConnectFourGame.objects.create(
                owner=request.user,
                player_red=request.user,
                name=(request.POST.get("name", "").strip() or _("Vier gewinnt"))[:80],
                code=_generate_game_code(),
                board=[""] * BOARD_SIZE,
            )
            return redirect("connectfour_lobby", code=game.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("connectfour_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/connectfour_home.html", {
        "my_games": _home_games_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
    })


@login_required
@require_GET
def connectfour_home_state_api(request):
    return JsonResponse({
        "ok": True,
        "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)],
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
    })


@login_required
def connectfour_lobby(request, code):
    game = get_object_or_404(
        ConnectFourGame.objects.select_related("owner", "player_red", "player_yellow"),
        code=code.upper(),
    )

    if not game.disc_for_user(request.user) and game.player_yellow_id is None:
        game.player_yellow = request.user
        game.status = ConnectFourGame.STATUS_PLAYING
        game.save(update_fields=["player_yellow", "status", "updated_at"])
    elif not game.disc_for_user(request.user):
        messages.error(request, _("Dieser Vier-gewinnt-Raum ist bereits voll."))
        return redirect("connectfour_home")

    _ensure_game_ready(game)
    return render(request, "app/connectfour_lobby.html", {
        "game": game,
        "friend_invite_rows": _friend_invite_rows(game, request.user),
    })


@login_required
@require_POST
def connectfour_invite_friend(request, code):
    game = get_object_or_404(ConnectFourGame, code=code.upper())
    if not _user_can_send_invites(game, request.user):
        messages.error(request, _("Dieser Raum hat bereits zwei Spieler."))
        return redirect("connectfour_lobby", code=game.code)

    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("connectfour_lobby", code=game.code)
    if game.disc_for_user(friend):
        messages.info(request, _("Dieser Freund ist schon im Raum."))
        return redirect("connectfour_lobby", code=game.code)

    ConnectFourInvite.objects.update_or_create(
        game=game,
        to_user=friend,
        defaults={"from_user": request.user, "status": ConnectFourInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("connectfour_lobby", code=game.code)


@login_required
@require_POST
def connectfour_invite_response(request, invite_id):
    invite = get_object_or_404(
        ConnectFourInvite.objects.select_related("game"),
        id=invite_id,
        to_user=request.user,
    )
    if request.POST.get("action") == "accept":
        if invite.game.player_yellow_id and not invite.game.disc_for_user(request.user):
            invite.status = ConnectFourInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Vier-gewinnt-Raum ist bereits voll."))
            return redirect("connectfour_home")
        invite.status = ConnectFourInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("connectfour_lobby", code=invite.game.code)

    invite.status = ConnectFourInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("connectfour_home")


@login_required
@require_GET
def connectfour_state_api(request, code):
    game = get_object_or_404(
        ConnectFourGame.objects.select_related("owner", "player_red", "player_yellow"),
        code=code.upper(),
    )
    _ensure_game_ready(game)
    game.refresh_from_db()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def connectfour_move_api(request, code):
    try:
        column = int(request.POST.get("column"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": _("Ungültige Spalte.")}, status=400)
    if column < 0 or column >= COLUMNS:
        return JsonResponse({"ok": False, "error": _("Ungültige Spalte.")}, status=400)

    with transaction.atomic():
        game = get_object_or_404(
            ConnectFourGame.objects.select_for_update().select_related("owner", "player_red", "player_yellow"),
            code=code.upper(),
        )
        player_disc = game.disc_for_user(request.user)
        board = game.normalized_board

        if game.status != ConnectFourGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Das Spiel läuft gerade nicht.")}, status=400)
        if not player_disc:
            return JsonResponse({"ok": False, "error": _("Du bist in diesem Raum nur Zuschauer.")}, status=403)
        if player_disc != game.current_disc:
            return JsonResponse({"ok": False, "error": _("Du bist noch nicht am Zug.")}, status=400)

        row = _drop_row_for_column(board, column)
        if row is None:
            return JsonResponse({"ok": False, "error": _("Diese Spalte ist voll.")}, status=400)

        move_index = _index(row, column)
        board[move_index] = player_disc
        winner_disc, winning_line = _winner_for_board(board)
        game.board = board
        game.last_move = {"row": row, "column": column, "index": move_index, "disc": player_disc}
        game.last_move_at = timezone.now()

        if winner_disc:
            game.status = ConnectFourGame.STATUS_FINISHED
            game.winner_disc = winner_disc
            game.winning_line = winning_line
        elif all(board):
            game.status = ConnectFourGame.STATUS_FINISHED
            game.winner_disc = ""
            game.winning_line = []
        else:
            game.current_disc = ConnectFourGame.DISC_YELLOW if player_disc == ConnectFourGame.DISC_RED else ConnectFourGame.DISC_RED

        game.save()

    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def connectfour_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(ConnectFourGame.objects.select_for_update(), code=code.upper())
        if not game.disc_for_user(request.user):
            return JsonResponse({"ok": False, "error": _("Nur Spieler können neu starten.")}, status=403)
        game.board = [""] * BOARD_SIZE
        game.current_disc = ConnectFourGame.DISC_RED
        game.winner_disc = ""
        game.winning_line = []
        game.last_move = {}
        game.round_number += 1
        game.status = ConnectFourGame.STATUS_PLAYING if game.player_red_id and game.player_yellow_id else ConnectFourGame.STATUS_WAITING
        game.last_move_at = None
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def connectfour_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(ConnectFourGame.objects.select_for_update(), code=code.upper())
        if game.player_red_id == request.user.id:
            game.player_red = None
        if game.player_yellow_id == request.user.id:
            game.player_yellow = None
        if not game.player_red_id and not game.player_yellow_id:
            game.delete()
            messages.info(request, _("Vier-gewinnt-Raum wurde gelöscht."))
            return redirect("connectfour_home")
        if not game.player_red_id and game.player_yellow_id:
            game.player_red = game.player_yellow
            game.player_yellow = None
        _reset_waiting_game(game)
        game.invites.filter(status=ConnectFourInvite.STATUS_PENDING).update(status=ConnectFourInvite.STATUS_DECLINED)
        game.save()
    return redirect("connectfour_home")


@login_required
@require_POST
def connectfour_delete(request, code):
    game = get_object_or_404(ConnectFourGame, code=code.upper())
    if game.owner_id != request.user.id and not game.disc_for_user(request.user):
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("connectfour_home")
    game.delete()
    messages.success(request, _("Vier-gewinnt-Raum wurde gelöscht."))
    return redirect("connectfour_home")
