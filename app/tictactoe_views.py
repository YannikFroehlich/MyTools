import random
import string
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

from .models import Friendship, TicTacToeGame, TicTacToeInvite, UserProfile


GAME_PLAYER_TIMEOUT = timedelta(seconds=30)
PLAYER_SEEN_UPDATE_INTERVAL = timedelta(seconds=5)


WINNING_LINES = [
    [0, 1, 2],
    [3, 4, 5],
    [6, 7, 8],
    [0, 3, 6],
    [1, 4, 7],
    [2, 5, 8],
    [0, 4, 8],
    [2, 4, 6],
]


def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not TicTacToeGame.objects.filter(code=code).exists():
            return code


def _winner_for_board(board):
    for line in WINNING_LINES:
        values = [board[index] for index in line]
        if values[0] and values.count(values[0]) == 3:
            return values[0], line
    return "", []


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


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


def _ensure_game_ready(game):
    if game.status == TicTacToeGame.STATUS_WAITING and game.player_x_id and game.player_o_id:
        game.status = TicTacToeGame.STATUS_PLAYING
        game.save(update_fields=["status", "updated_at"])


def _user_can_send_invites(game, user):
    return (game.owner_id == user.id or game.symbol_for_user(user)) and not game.player_o_id


def _reset_waiting_game(game):
    game.board = [""] * 9
    game.current_symbol = TicTacToeGame.SYMBOL_X
    game.winner_symbol = ""
    game.winning_line = []
    game.status = TicTacToeGame.STATUS_WAITING
    game.last_move_at = None


def _transfer_owner_if_needed(game, leaving_user):
    if game.owner_id != leaving_user.id:
        return
    game.owner = game.player_x or game.player_o


def _mark_player_seen(game, user):
    now = timezone.now()
    update_fields = []
    recent_cutoff = now - PLAYER_SEEN_UPDATE_INTERVAL
    if game.player_x_id == user.id and (not game.player_x_last_seen or game.player_x_last_seen < recent_cutoff):
        game.player_x_last_seen = now
        update_fields.append("player_x_last_seen")
    if game.player_o_id == user.id and (not game.player_o_last_seen or game.player_o_last_seen < recent_cutoff):
        game.player_o_last_seen = now
        update_fields.append("player_o_last_seen")
    if update_fields:
        game.save(update_fields=update_fields)


def _player_slot_is_stale(last_seen, updated_at, now):
    if last_seen:
        return last_seen < now - GAME_PLAYER_TIMEOUT
    return updated_at < now - GAME_PLAYER_TIMEOUT


def _cleanup_game_players(game, keep_user_id=None):
    now = timezone.now()
    changed = False

    if game.player_x_id and game.player_x_id != keep_user_id and _player_slot_is_stale(game.player_x_last_seen, game.updated_at, now):
        game.player_x = None
        game.player_x_last_seen = None
        changed = True
    if game.player_o_id and game.player_o_id != keep_user_id and _player_slot_is_stale(game.player_o_last_seen, game.updated_at, now):
        game.player_o = None
        game.player_o_last_seen = None
        changed = True

    if not changed:
        return False

    if not game.player_x_id and not game.player_o_id:
        game.delete()
        return True

    if not game.player_x_id and game.player_o_id:
        game.player_x = game.player_o
        game.player_x_last_seen = game.player_o_last_seen
        game.player_o = None
        game.player_o_last_seen = None

    if game.owner_id not in [game.player_x_id, game.player_o_id]:
        game.owner = game.player_x or game.player_o

    _reset_waiting_game(game)
    game.invites.filter(status=TicTacToeInvite.STATUS_PENDING).update(status=TicTacToeInvite.STATUS_DECLINED)
    game.save(update_fields=[
        "owner", "player_x", "player_o", "player_x_last_seen", "player_o_last_seen",
        "board", "current_symbol", "winner_symbol", "winning_line", "status",
        "last_move_at", "updated_at",
    ])
    return False


def _cleanup_stale_games():
    for game in TicTacToeGame.objects.select_related("owner", "player_x", "player_o"):
        _cleanup_game_players(game)
    TicTacToeGame.objects.filter(player_x__isnull=True, player_o__isnull=True).delete()


def _delete_empty_games():
    _cleanup_stale_games()


def _friend_invite_rows(game, user):
    if game.player_o_id:
        return []

    friend_ids = Friendship.friend_ids_for_user(user)
    current_player_ids = [user_id for user_id in [game.player_x_id, game.player_o_id] if user_id]
    friends = (
        User.objects
        .filter(id__in=friend_ids, is_active=True)
        .exclude(id__in=current_player_ids)
        .order_by("username")
    )
    UserProfile.objects.bulk_create(
        [UserProfile(user=friend) for friend in friends if not hasattr(friend, "profile")],
        ignore_conflicts=True,
    )
    invited_friend_ids = set(
        game.invites
        .filter(status=TicTacToeInvite.STATUS_PENDING)
        .values_list("to_user_id", flat=True)
    )
    accepted_invite_ids = set(
        game.invites
        .filter(status=TicTacToeInvite.STATUS_ACCEPTED)
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
    board = game.normalized_board
    player_symbol = game.symbol_for_user(user)
    opponent = game.opponent_for_user(user)
    is_players_turn = game.status == TicTacToeGame.STATUS_PLAYING and player_symbol == game.current_symbol

    if game.status == TicTacToeGame.STATUS_WAITING:
        message = _("Warte auf einen zweiten Spieler.")
    elif game.status == TicTacToeGame.STATUS_FINISHED and game.winner_symbol:
        if game.winner_symbol == player_symbol:
            message = _("Du hast gewonnen.")
        elif player_symbol:
            message = _("Dein Freund hat gewonnen.")
        else:
            message = _("%(symbol)s hat gewonnen.") % {"symbol": game.winner_symbol}
    elif game.status == TicTacToeGame.STATUS_FINISHED:
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
        "currentSymbol": game.current_symbol,
        "winnerSymbol": game.winner_symbol,
        "winningLine": game.winning_line or [],
        "roundNumber": game.round_number,
        "playerSymbol": player_symbol,
        "canMove": is_players_turn,
        "message": message,
        "players": {
            "X": _player_name(game.player_x),
            "O": _player_name(game.player_o),
        },
        "opponentName": _player_name(opponent),
        "isOwner": game.owner_id == user.id,
        "updatedAt": timezone.localtime(game.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


def _home_games_for_user(user):
    return (
        TicTacToeGame.objects
        .filter(Q(owner=user) | Q(player_x=user) | Q(player_o=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        TicTacToeInvite.objects
        .select_related("game", "from_user")
        .filter(to_user=user, status=TicTacToeInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _serialize_home_game(game):
    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "url": reverse("tictactoe_lobby", args=[game.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.game.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("tictactoe_invite_response", args=[invite.id]),
        "declineUrl": reverse("tictactoe_invite_response", args=[invite.id]),
    }


@login_required
def tictactoe_home(request):
    _delete_empty_games()
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name", "").strip() or _("Tic Tac Toe")
            game = TicTacToeGame.objects.create(
                owner=request.user,
                player_x=request.user,
                player_x_last_seen=timezone.now(),
                name=name[:80],
                code=_generate_game_code(),
                board=[""] * 9,
            )
            return redirect("tictactoe_lobby", code=game.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("tictactoe_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/tictactoe_home.html", {
        "my_games": _home_games_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
    })


@login_required
@require_GET
def tictactoe_home_state_api(request):
    _delete_empty_games()
    return JsonResponse({
        "ok": True,
        "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)],
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
    })


@login_required
def tictactoe_lobby(request, code):
    game = (
        TicTacToeGame.objects
        .select_related("owner", "player_x", "player_o")
        .filter(code=code.upper())
        .first()
    )
    if not game:
        messages.warning(request, _("Diese Tic-Tac-Toe-Lobby existiert nicht mehr."))
        return redirect("tictactoe_home")

    if game.symbol_for_user(request.user):
        _mark_player_seen(game, request.user)
    if _cleanup_game_players(game, keep_user_id=request.user.id):
        messages.warning(request, _("Diese Tic-Tac-Toe-Lobby existiert nicht mehr."))
        return redirect("tictactoe_home")
    game.refresh_from_db()

    if not game.symbol_for_user(request.user) and game.player_o_id is None:
        game.player_o = request.user
        game.player_o_last_seen = timezone.now()
        game.status = TicTacToeGame.STATUS_PLAYING
        game.save(update_fields=["player_o", "player_o_last_seen", "status", "updated_at"])
    elif not game.symbol_for_user(request.user):
        messages.error(request, _("Dieser Tic-Tac-Toe-Raum ist bereits voll."))
        return redirect("tictactoe_home")

    _mark_player_seen(game, request.user)
    _ensure_game_ready(game)

    return render(request, "app/tictactoe_lobby.html", {
        "game": game,
        "friend_invite_rows": _friend_invite_rows(game, request.user),
    })


@login_required
@require_POST
def tictactoe_invite_friend(request, code):
    game = get_object_or_404(TicTacToeGame, code=code.upper())
    if not _user_can_send_invites(game, request.user):
        messages.error(request, _("Dieser Raum hat bereits zwei Spieler."))
        return redirect("tictactoe_lobby", code=game.code)

    friend_id = request.POST.get("friend_id")
    friend = get_object_or_404(User, id=friend_id, is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("tictactoe_lobby", code=game.code)

    if game.symbol_for_user(friend):
        messages.info(request, _("Dieser Freund ist schon im Raum."))
        return redirect("tictactoe_lobby", code=game.code)

    TicTacToeInvite.objects.update_or_create(
        game=game,
        to_user=friend,
        defaults={"from_user": request.user, "status": TicTacToeInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("tictactoe_lobby", code=game.code)


@login_required
@require_POST
def tictactoe_invite_response(request, invite_id):
    invite = get_object_or_404(
        TicTacToeInvite.objects.select_related("game"),
        id=invite_id,
        to_user=request.user,
    )
    action = request.POST.get("action")

    if action == "accept":
        if invite.game.player_o_id and not invite.game.symbol_for_user(request.user):
            invite.status = TicTacToeInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Tic-Tac-Toe-Raum ist bereits voll."))
            return redirect("tictactoe_home")

        invite.status = TicTacToeInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("tictactoe_lobby", code=invite.game.code)

    invite.status = TicTacToeInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("tictactoe_home")


@login_required
@require_GET
def tictactoe_state_api(request, code):
    game = TicTacToeGame.objects.select_related("owner", "player_x", "player_o").filter(code=code.upper()).first()
    if not game:
        return JsonResponse({
            "ok": False,
            "gameDeleted": True,
            "error": _("Dieser Tic-Tac-Toe-Raum wurde gelöscht."),
            "redirectUrl": reverse("tictactoe_home"),
        }, status=410)
    _mark_player_seen(game, request.user)
    if _cleanup_game_players(game, keep_user_id=request.user.id):
        return JsonResponse({
            "ok": False,
            "gameDeleted": True,
            "error": _("Dieser Tic-Tac-Toe-Raum wurde gelöscht."),
            "redirectUrl": reverse("tictactoe_home"),
        }, status=410)
    _ensure_game_ready(game)
    game.refresh_from_db()
    return JsonResponse({
        "ok": True,
        "game": _serialize_game(game, request.user),
    })


@login_required
@require_POST
@_database_lock_guard
def tictactoe_move_api(request, code):
    try:
        index = int(request.POST.get("index"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": _("Ungültiges Feld.")}, status=400)

    if index < 0 or index > 8:
        return JsonResponse({"ok": False, "error": _("Ungültiges Feld.")}, status=400)

    with transaction.atomic():
        game = get_object_or_404(
            TicTacToeGame.objects.select_for_update(of=("self",)),
            code=code.upper(),
        )
        player_symbol = game.symbol_for_user(request.user)
        board = game.normalized_board

        if game.status != TicTacToeGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Das Spiel läuft gerade nicht.")}, status=400)
        if not player_symbol:
            return JsonResponse({"ok": False, "error": _("Du bist in diesem Raum nur Zuschauer.")}, status=403)
        if player_symbol != game.current_symbol:
            return JsonResponse({"ok": False, "error": _("Du bist noch nicht am Zug.")}, status=400)
        if board[index]:
            return JsonResponse({"ok": False, "error": _("Dieses Feld ist schon belegt.")}, status=400)

        board[index] = player_symbol
        winner_symbol, winning_line = _winner_for_board(board)
        game.board = board
        game.last_move_at = timezone.now()
        update_fields = ["board", "last_move_at", "updated_at"]

        if winner_symbol:
            game.status = TicTacToeGame.STATUS_FINISHED
            game.winner_symbol = winner_symbol
            game.winning_line = winning_line
            update_fields += ["status", "winner_symbol", "winning_line"]
        elif all(board):
            game.status = TicTacToeGame.STATUS_FINISHED
            game.winner_symbol = ""
            game.winning_line = []
            update_fields += ["status", "winner_symbol", "winning_line"]
        else:
            game.current_symbol = TicTacToeGame.SYMBOL_O if player_symbol == TicTacToeGame.SYMBOL_X else TicTacToeGame.SYMBOL_X
            update_fields.append("current_symbol")

        game.save(update_fields=update_fields)

    return JsonResponse({
        "ok": True,
        "game": _serialize_game(game, request.user),
    })


@login_required
@require_POST
@_database_lock_guard
def tictactoe_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(
            TicTacToeGame.objects.select_for_update(of=("self",)),
            code=code.upper(),
        )
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann eine neue Runde starten.")}, status=403)

        game.board = [""] * 9
        game.current_symbol = TicTacToeGame.SYMBOL_X
        game.winner_symbol = ""
        game.winning_line = []
        game.round_number += 1
        game.status = TicTacToeGame.STATUS_PLAYING if game.player_x_id and game.player_o_id else TicTacToeGame.STATUS_WAITING
        game.last_move_at = None
        game.save()

    return JsonResponse({
        "ok": True,
        "game": _serialize_game(game, request.user),
    })


@login_required
@require_POST
def tictactoe_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(TicTacToeGame.objects.select_for_update(), code=code.upper())

        if not game.symbol_for_user(request.user):
            messages.info(request, _("Du bist nicht mehr in diesem Raum."))
            return redirect(reverse("tictactoe_home"))

        if game.player_x_id == request.user.id:
            game.player_x = None
            game.player_x_last_seen = None
        if game.player_o_id == request.user.id:
            game.player_o = None
            game.player_o_last_seen = None

        _transfer_owner_if_needed(game, request.user)

        if not game.player_x_id and not game.player_o_id:
            game.delete()
            messages.info(request, _("Tic-Tac-Toe-Raum wurde gelöscht."))
            return redirect(reverse("tictactoe_home"))

        if not game.player_x_id and game.player_o_id:
            game.player_x = game.player_o
            game.player_x_last_seen = game.player_o_last_seen
            game.player_o = None
            game.player_o_last_seen = None

        _reset_waiting_game(game)
        game.invites.filter(status=TicTacToeInvite.STATUS_PENDING).update(status=TicTacToeInvite.STATUS_DECLINED)
        game.save(update_fields=[
            "owner", "player_x", "player_o", "player_x_last_seen", "player_o_last_seen",
            "board", "current_symbol", "winner_symbol", "winning_line", "status",
            "last_move_at", "updated_at",
        ])

    return redirect(reverse("tictactoe_home"))


@login_required
@require_POST
def tictactoe_delete(request, code):
    game = get_object_or_404(TicTacToeGame, code=code.upper())
    if game.owner_id != request.user.id:
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("tictactoe_home")

    game.delete()
    messages.success(request, _("Tic-Tac-Toe-Raum wurde gelöscht."))
    return redirect("tictactoe_home")
