import math
import random
import string
from datetime import timedelta

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

from .models import Friendship, PongGame, PongInvite, UserPresence, UserProfile


GAME_PLAYER_TIMEOUT = timedelta(seconds=35)
FIELD_W = 100.0
FIELD_H = 100.0
PADDLE_H = 20.0
PADDLE_W = 2.4
BALL_R = 1.7
LEFT_PADDLE_X = 5.0
RIGHT_PADDLE_X = 95.0
MAX_DT = 1 / 120
RESET_SPEED_X = 38.0
RESET_SPEED_Y = 14.0
MAX_SPEED_X = 68.0


def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not PongGame.objects.filter(code=code).exists():
            return code


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _clamp(value, low, high):
    return max(low, min(high, value))


def _reset_ball(game, direction=None):
    direction = direction or random.choice([-1, 1])
    game.ball_x = 50.0
    game.ball_y = 50.0
    game.ball_vx = RESET_SPEED_X * direction
    game.ball_vy = random.choice([-1, 1]) * random.uniform(RESET_SPEED_Y, RESET_SPEED_Y + 10)
    game.last_hit_side = ""
    game.rally_hits = 0
    game.last_tick_at = timezone.now()


def _reset_waiting_game(game):
    game.status = PongGame.STATUS_WAITING
    game.score_left = 0
    game.score_right = 0
    game.winner_side = ""
    game.paddle_left_y = 50.0
    game.paddle_right_y = 50.0
    game.best_rally = max(game.best_rally or 0, game.rally_hits or 0)
    _reset_ball(game)


def _ensure_game_ready(game):
    if game.status == PongGame.STATUS_WAITING and game.player_left_id and game.player_right_id:
        game.status = PongGame.STATUS_PLAYING
        _reset_ball(game)
        game.save(update_fields=[
            "status", "ball_x", "ball_y", "ball_vx", "ball_vy", "last_hit_side", "rally_hits", "last_tick_at", "updated_at",
        ])


def _mark_player_seen(game, user):
    now = timezone.now()
    update_fields = []
    if game.player_left_id == user.id:
        game.player_left_last_seen = now
        update_fields.append("player_left_last_seen")
    if game.player_right_id == user.id:
        game.player_right_last_seen = now
        update_fields.append("player_right_last_seen")
    if update_fields:
        game.save(update_fields=update_fields)
        UserPresence.objects.update_or_create(
            user=user,
            defaults={
                "active_game": "pong",
                "active_game_label": str(_("spielt Pong")),
                "active_game_updated_at": now,
                "last_seen": now,
            },
        )


def _player_slot_is_stale(last_seen, updated_at, now):
    if last_seen:
        return last_seen < now - GAME_PLAYER_TIMEOUT
    return updated_at < now - GAME_PLAYER_TIMEOUT


def _transfer_owner_if_needed(game, leaving_user):
    if game.owner_id != leaving_user.id:
        return
    game.owner = game.player_left or game.player_right


def _cleanup_game_players(game, keep_user_id=None):
    now = timezone.now()
    changed = False

    if game.player_left_id and game.player_left_id != keep_user_id and _player_slot_is_stale(game.player_left_last_seen, game.updated_at, now):
        game.player_left = None
        game.player_left_last_seen = None
        changed = True
    if game.player_right_id and game.player_right_id != keep_user_id and _player_slot_is_stale(game.player_right_last_seen, game.updated_at, now):
        game.player_right = None
        game.player_right_last_seen = None
        changed = True

    if not changed:
        return False

    if not game.player_left_id and not game.player_right_id:
        game.delete()
        return True

    if not game.player_left_id and game.player_right_id:
        game.player_left = game.player_right
        game.player_left_last_seen = game.player_right_last_seen
        game.player_right = None
        game.player_right_last_seen = None

    if game.owner_id not in [game.player_left_id, game.player_right_id]:
        game.owner = game.player_left or game.player_right

    _reset_waiting_game(game)
    game.invites.filter(status=PongInvite.STATUS_PENDING).update(status=PongInvite.STATUS_DECLINED)
    game.save(update_fields=[
        "owner", "player_left", "player_right", "player_left_last_seen", "player_right_last_seen",
        "status", "score_left", "score_right", "winner_side", "paddle_left_y", "paddle_right_y",
        "ball_x", "ball_y", "ball_vx", "ball_vy", "last_hit_side", "rally_hits", "best_rally",
        "last_tick_at", "updated_at",
    ])
    return False


def _cleanup_stale_games():
    for game in PongGame.objects.select_related("owner", "player_left", "player_right"):
        _cleanup_game_players(game)
    PongGame.objects.filter(player_left__isnull=True, player_right__isnull=True).delete()


def _delete_empty_games():
    _cleanup_stale_games()


def _tick_game(game):
    if game.status != PongGame.STATUS_PLAYING:
        return False
    now = timezone.now()
    if not game.last_tick_at:
        game.last_tick_at = now
        return True
    dt = (now - game.last_tick_at).total_seconds()
    if dt <= 0:
        return False
    remaining = min(dt, 0.8)
    changed = False
    while remaining > 0:
        step = min(MAX_DT, remaining)
        remaining -= step
        prev_x = game.ball_x
        prev_y = game.ball_y
        game.ball_x += game.ball_vx * step
        game.ball_y += game.ball_vy * step

        if game.ball_y - BALL_R <= 0:
            game.ball_y = BALL_R
            game.ball_vy = abs(game.ball_vy)
        elif game.ball_y + BALL_R >= FIELD_H:
            game.ball_y = FIELD_H - BALL_R
            game.ball_vy = -abs(game.ball_vy)

        left_top = game.paddle_left_y - PADDLE_H / 2
        left_bottom = game.paddle_left_y + PADDLE_H / 2
        right_top = game.paddle_right_y - PADDLE_H / 2
        right_bottom = game.paddle_right_y + PADDLE_H / 2

        left_collision_x = LEFT_PADDLE_X + PADDLE_W + BALL_R
        right_collision_x = RIGHT_PADDLE_X - PADDLE_W - BALL_R

        if game.ball_vx < 0 and prev_x >= left_collision_x and game.ball_x <= left_collision_x:
            travel = prev_x - game.ball_x
            progress = 0 if travel <= 0 else (prev_x - left_collision_x) / travel
            collision_y = prev_y + (game.ball_y - prev_y) * progress
            if left_top - BALL_R <= collision_y <= left_bottom + BALL_R:
                hit_offset = _clamp((collision_y - game.paddle_left_y) / (PADDLE_H / 2), -1.15, 1.15)
                game.ball_x = left_collision_x
                game.ball_y = _clamp(collision_y, BALL_R, FIELD_H - BALL_R)
                game.ball_vx = min(abs(game.ball_vx) * 1.035 + 0.9, MAX_SPEED_X)
                game.ball_vy = _clamp(game.ball_vy + hit_offset * 24, -58, 58)
                game.last_hit_side = PongGame.SIDE_LEFT
                game.rally_hits += 1
        elif game.ball_vx > 0 and prev_x <= right_collision_x and game.ball_x >= right_collision_x:
            travel = game.ball_x - prev_x
            progress = 0 if travel <= 0 else (right_collision_x - prev_x) / travel
            collision_y = prev_y + (game.ball_y - prev_y) * progress
            if right_top - BALL_R <= collision_y <= right_bottom + BALL_R:
                hit_offset = _clamp((collision_y - game.paddle_right_y) / (PADDLE_H / 2), -1.15, 1.15)
                game.ball_x = right_collision_x
                game.ball_y = _clamp(collision_y, BALL_R, FIELD_H - BALL_R)
                game.ball_vx = -min(abs(game.ball_vx) * 1.035 + 0.9, MAX_SPEED_X)
                game.ball_vy = _clamp(game.ball_vy + hit_offset * 24, -58, 58)
                game.last_hit_side = PongGame.SIDE_RIGHT
                game.rally_hits += 1

        game.ball_vy = _clamp(game.ball_vy, -62, 62)

        if game.ball_x < -BALL_R:
            game.score_right += 1
            game.best_rally = max(game.best_rally or 0, game.rally_hits or 0)
            game.last_scored_at = now
            if game.score_right >= game.target_score:
                game.status = PongGame.STATUS_FINISHED
                game.winner_side = PongGame.SIDE_RIGHT
            else:
                _reset_ball(game, direction=-1)
            break
        if game.ball_x > FIELD_W + BALL_R:
            game.score_left += 1
            game.best_rally = max(game.best_rally or 0, game.rally_hits or 0)
            game.last_scored_at = now
            if game.score_left >= game.target_score:
                game.status = PongGame.STATUS_FINISHED
                game.winner_side = PongGame.SIDE_LEFT
            else:
                _reset_ball(game, direction=1)
            break
        changed = True

    game.last_tick_at = now
    return changed or True


def _user_can_send_invites(game, user):
    return (game.owner_id == user.id or game.side_for_user(user)) and not game.player_right_id


def _friend_invite_rows(game, user):
    if game.player_right_id:
        return []
    friend_ids = Friendship.friend_ids_for_user(user)
    current_player_ids = [user_id for user_id in [game.player_left_id, game.player_right_id] if user_id]
    friends = User.objects.filter(id__in=friend_ids, is_active=True).exclude(id__in=current_player_ids).order_by("username")
    UserProfile.objects.bulk_create([UserProfile(user=friend) for friend in friends if not hasattr(friend, "profile")], ignore_conflicts=True)
    invited_friend_ids = set(game.invites.filter(status=PongInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted_invite_ids = set(game.invites.filter(status=PongInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    return [{"user": friend, "is_invited": friend.id in invited_friend_ids, "was_invited": friend.id in accepted_invite_ids} for friend in friends]


def _serialize_game(game, user):
    side = game.side_for_user(user)
    opponent = game.opponent_for_user(user)
    if game.status == PongGame.STATUS_WAITING:
        message = _("Warte auf einen zweiten Spieler.")
    elif game.status == PongGame.STATUS_FINISHED and game.winner_side:
        if game.winner_side == side:
            message = _("Du hast gewonnen.")
        elif side:
            message = _("Dein Freund hat gewonnen.")
        else:
            message = _("%(side)s hat gewonnen.") % {"side": game.get_winner_side_display()}
    elif game.status == PongGame.STATUS_PLAYING:
        message = _("Match läuft. Bewege deinen Schläger und halte den Ball im Spiel.")
    else:
        message = _("Spiel pausiert.")

    return {
        "id": game.id,
        "name": game.name,
        "code": game.code,
        "status": game.status,
        "statusLabel": game.get_status_display(),
        "roundNumber": game.round_number,
        "targetScore": game.target_score,
        "playerSide": side,
        "winnerSide": game.winner_side,
        "winnerName": _player_name(game.winner_user),
        "message": message,
        "isOwner": game.owner_id == user.id,
        "players": {"left": _player_name(game.player_left), "right": _player_name(game.player_right)},
        "opponentName": _player_name(opponent),
        "score": {"left": game.score_left, "right": game.score_right},
        "paddles": {"left": game.paddle_left_y, "right": game.paddle_right_y},
        "ball": {"x": game.ball_x, "y": game.ball_y, "vx": game.ball_vx, "vy": game.ball_vy},
        "rallyHits": game.rally_hits,
        "bestRally": game.best_rally,
        "updatedAt": timezone.localtime(game.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


def _home_games_for_user(user):
    return PongGame.objects.filter(Q(owner=user) | Q(player_left=user) | Q(player_right=user)).distinct().order_by("-updated_at")[:12]


def _home_invites_for_user(user):
    return PongInvite.objects.select_related("game", "from_user").filter(to_user=user, status=PongInvite.STATUS_PENDING).order_by("-created_at")


def _serialize_home_game(game):
    return {"id": game.id, "name": game.name, "code": game.code, "statusLabel": game.get_status_display(), "roundNumber": game.round_number, "url": reverse("pong_lobby", args=[game.code])}


def _serialize_home_invite(invite):
    return {"id": invite.id, "gameName": invite.game.name, "fromUser": invite.from_user.username, "acceptUrl": reverse("pong_invite_response", args=[invite.id]), "declineUrl": reverse("pong_invite_response", args=[invite.id])}


@login_required
def pong_home(request):
    _delete_empty_games()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            name = request.POST.get("name", "").strip() or _("Pong")
            try:
                target_score = int(request.POST.get("target_score") or 7)
            except (TypeError, ValueError):
                target_score = 7
            target_score = int(_clamp(target_score, 3, 21))
            game = PongGame.objects.create(
                owner=request.user,
                player_left=request.user,
                player_left_last_seen=timezone.now(),
                name=name[:80],
                code=_generate_game_code(),
                target_score=target_score,
                last_tick_at=timezone.now(),
            )
            _reset_ball(game, direction=1)
            game.save()
            return redirect("pong_lobby", code=game.code)
        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("pong_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/pong_home.html", {"my_games": _home_games_for_user(request.user), "invites": _home_invites_for_user(request.user)})


@login_required
@require_GET
def pong_home_state_api(request):
    _delete_empty_games()
    return JsonResponse({"ok": True, "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)], "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)]})


@login_required
def pong_lobby(request, code):
    game = PongGame.objects.select_related("owner", "player_left", "player_right").filter(code=code.upper()).first()
    if not game:
        messages.warning(request, _("Diese Pong-Lobby existiert nicht mehr."))
        return redirect("pong_home")

    if game.side_for_user(request.user):
        _mark_player_seen(game, request.user)
    if _cleanup_game_players(game, keep_user_id=request.user.id):
        messages.warning(request, _("Diese Pong-Lobby existiert nicht mehr."))
        return redirect("pong_home")
    game.refresh_from_db()

    if not game.side_for_user(request.user) and game.player_right_id is None:
        game.player_right = request.user
        game.player_right_last_seen = timezone.now()
        game.status = PongGame.STATUS_PLAYING
        _reset_ball(game, direction=random.choice([-1, 1]))
        game.save(update_fields=["player_right", "player_right_last_seen", "status", "ball_x", "ball_y", "ball_vx", "ball_vy", "last_hit_side", "rally_hits", "last_tick_at", "updated_at"])
    elif not game.side_for_user(request.user):
        messages.error(request, _("Dieser Pong-Raum ist bereits voll."))
        return redirect("pong_home")

    _mark_player_seen(game, request.user)
    _ensure_game_ready(game)
    return render(request, "app/pong_lobby.html", {"game": game, "friend_invite_rows": _friend_invite_rows(game, request.user)})


@login_required
@require_POST
def pong_invite_friend(request, code):
    game = get_object_or_404(PongGame, code=code.upper())
    if not _user_can_send_invites(game, request.user):
        messages.error(request, _("Dieser Raum hat bereits zwei Spieler."))
        return redirect("pong_lobby", code=game.code)
    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("pong_lobby", code=game.code)
    if game.side_for_user(friend):
        messages.info(request, _("Dieser Freund ist schon im Raum."))
        return redirect("pong_lobby", code=game.code)
    PongInvite.objects.update_or_create(game=game, to_user=friend, defaults={"from_user": request.user, "status": PongInvite.STATUS_PENDING})
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("pong_lobby", code=game.code)


@login_required
@require_POST
def pong_invite_response(request, invite_id):
    invite = get_object_or_404(PongInvite.objects.select_related("game"), id=invite_id, to_user=request.user)
    action = request.POST.get("action")
    if action == "accept":
        if invite.game.player_right_id and not invite.game.side_for_user(request.user):
            invite.status = PongInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Pong-Raum ist bereits voll."))
            return redirect("pong_home")
        invite.status = PongInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("pong_lobby", code=invite.game.code)
    invite.status = PongInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("pong_home")


@login_required
@require_GET
def pong_state_api(request, code):
    with transaction.atomic():
        game = PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right").filter(code=code.upper()).first()
        if not game:
            return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Pong-Raum wurde gelöscht."), "redirectUrl": reverse("pong_home")}, status=410)
        _mark_player_seen(game, request.user)
        if _cleanup_game_players(game, keep_user_id=request.user.id):
            return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Pong-Raum wurde gelöscht."), "redirectUrl": reverse("pong_home")}, status=410)
        _ensure_game_ready(game)
        _tick_game(game)
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def pong_paddle_api(request, code):
    try:
        y = float(request.POST.get("y"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": _("Ungültige Position.")}, status=400)
    y = _clamp(y, PADDLE_H / 2, FIELD_H - PADDLE_H / 2)
    with transaction.atomic():
        game = get_object_or_404(PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right"), code=code.upper())
        side = game.side_for_user(request.user)
        if not side:
            return JsonResponse({"ok": False, "error": _("Du bist in diesem Raum nur Zuschauer.")}, status=403)
        _tick_game(game)
        if side == PongGame.SIDE_LEFT:
            game.paddle_left_y = y
            game.player_left_last_seen = timezone.now()
        else:
            game.paddle_right_y = y
            game.player_right_last_seen = timezone.now()
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def pong_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right"), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann eine neue Runde starten.")}, status=403)
        game.score_left = 0
        game.score_right = 0
        game.winner_side = ""
        game.paddle_left_y = 50.0
        game.paddle_right_y = 50.0
        game.round_number += 1
        game.status = PongGame.STATUS_PLAYING if game.player_left_id and game.player_right_id else PongGame.STATUS_WAITING
        _reset_ball(game, direction=random.choice([-1, 1]))
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def pong_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(PongGame.objects.select_for_update(), code=code.upper())
        if not game.side_for_user(request.user):
            messages.info(request, _("Du bist nicht mehr in diesem Raum."))
            return redirect(reverse("pong_home"))
        if game.player_left_id == request.user.id:
            game.player_left = None
            game.player_left_last_seen = None
        if game.player_right_id == request.user.id:
            game.player_right = None
            game.player_right_last_seen = None
        _transfer_owner_if_needed(game, request.user)
        if not game.player_left_id and not game.player_right_id:
            game.delete()
            messages.info(request, _("Pong-Raum wurde gelöscht."))
            return redirect(reverse("pong_home"))
        if not game.player_left_id and game.player_right_id:
            game.player_left = game.player_right
            game.player_left_last_seen = game.player_right_last_seen
            game.player_right = None
            game.player_right_last_seen = None
        _reset_waiting_game(game)
        game.invites.filter(status=PongInvite.STATUS_PENDING).update(status=PongInvite.STATUS_DECLINED)
        game.save(update_fields=[
            "owner", "player_left", "player_right", "player_left_last_seen", "player_right_last_seen", "status",
            "score_left", "score_right", "winner_side", "paddle_left_y", "paddle_right_y", "ball_x", "ball_y",
            "ball_vx", "ball_vy", "last_hit_side", "rally_hits", "best_rally", "last_tick_at", "updated_at",
        ])
    return redirect(reverse("pong_home"))


@login_required
@require_POST
def pong_delete(request, code):
    game = get_object_or_404(PongGame, code=code.upper())
    if game.owner_id != request.user.id:
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("pong_home")
    game.delete()
    messages.success(request, _("Pong-Raum wurde gelöscht."))
    return redirect("pong_home")
