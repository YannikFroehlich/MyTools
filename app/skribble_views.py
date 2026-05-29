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

from .models import (
    DrawingGameGuess,
    DrawingGameInvite,
    DrawingGameLobby,
    DrawingGamePlayer,
    Friendship,
    UserProfile,
)

DEFAULT_WORDS = [
    "Haus", "Baum", "Auto", "Katze", "Hund", "Computer", "Pizza", "Sonne", "Mond", "Stern",
    "Drache", "Roboter", "Schloss", "Brille", "Kamera", "Flugzeug", "Zug", "Fahrrad", "Regenschirm", "Buch",
    "Gitarre", "Kopfhörer", "Schneemann", "Rakete", "Krone", "Tasse", "Banane", "Eis", "Meer", "Berg",
    "Wolke", "Schlüssel", "Lampe", "Uhr", "Maus", "Blume", "Dinosaurier", "Monster", "Piratenflagge", "Kaktus",
]

AVATAR_COLORS = ["#4f8cff", "#8b5cf6", "#22c55e", "#f97316", "#ef4444", "#06b6d4", "#ec4899", "#facc15"]
ACCENT_COLORS = ["#ffffff", "#111827", "#dbeafe", "#fef3c7", "#dcfce7", "#fee2e2"]


def _generate_lobby_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not DrawingGameLobby.objects.filter(code=code).exists():
            return code


def _get_or_create_player(lobby, user):
    player, _ = DrawingGamePlayer.objects.get_or_create(
        lobby=lobby,
        user=user,
        defaults={
            "display_name": user.get_full_name() or user.username,
            "avatar_color": random.choice(AVATAR_COLORS),
            "accent_color": "#ffffff",
        },
    )
    return player


def _user_can_enter_lobby(lobby, user):
    if lobby.owner_id == user.id:
        return True
    if lobby.players.filter(user=user).exists():
        return True
    if lobby.invites.filter(to_user=user, status__in=[DrawingGameInvite.STATUS_PENDING, DrawingGameInvite.STATUS_ACCEPTED]).exists():
        return True
    if Friendship.between(lobby.owner, user) and Friendship.between(lobby.owner, user).status == Friendship.STATUS_ACCEPTED:
        return True
    return False


def _players(lobby):
    return list(lobby.players.select_related("user", "user__profile").order_by("joined_at", "id"))


def _current_drawer(lobby, players=None):
    players = players if players is not None else _players(lobby)
    if not players:
        return None
    return players[lobby.current_turn_index % len(players)]


def _normalize_word(value):
    return "".join(ch.lower() for ch in value.strip() if ch.isalnum() or ch in "äöüß")


def _masked_word(word):
    return " ".join("_" if ch != " " else " / " for ch in word)


def _pick_word_choices(lobby):
    words = lobby.custom_word_list if lobby.use_only_custom_words and lobby.custom_word_list else DEFAULT_WORDS + lobby.custom_word_list
    words = list(dict.fromkeys([word for word in words if len(word) <= 40]))
    if len(words) < 3:
        words = DEFAULT_WORDS
    return random.sample(words, min(3, len(words)))


def _seconds_left(lobby):
    if not lobby.round_started_at or not lobby.current_word:
        return lobby.draw_time_seconds
    elapsed = (timezone.now() - lobby.round_started_at).total_seconds()
    return max(0, int(lobby.draw_time_seconds - elapsed))


def _reset_turn_state(lobby):
    lobby.current_word = ""
    lobby.current_word_choices = _pick_word_choices(lobby)
    lobby.current_drawing = []
    lobby.round_started_at = None
    lobby.players.update(has_guessed_current_word=False)


def _advance_turn(lobby):
    players_count = lobby.players.count()
    if players_count < 2:
        lobby.status = DrawingGameLobby.STATUS_WAITING
        lobby.current_word = ""
        lobby.current_word_choices = []
        lobby.round_started_at = None
        lobby.save(update_fields=["status", "current_word", "current_word_choices", "round_started_at", "updated_at"])
        return

    lobby.current_turn_index += 1
    if lobby.current_turn_index >= players_count:
        lobby.current_turn_index = 0
        lobby.current_round_number += 1

    if lobby.current_round_number > lobby.rounds_count:
        lobby.status = DrawingGameLobby.STATUS_FINISHED
        lobby.current_word = ""
        lobby.current_word_choices = []
        lobby.current_drawing = []
        lobby.round_started_at = None
        lobby.save(update_fields=[
            "status", "current_round_number", "current_turn_index", "current_word", "current_word_choices",
            "current_drawing", "round_started_at", "updated_at",
        ])
        return

    _reset_turn_state(lobby)
    lobby.save(update_fields=[
        "current_round_number", "current_turn_index", "current_word", "current_word_choices",
        "current_drawing", "round_started_at", "updated_at",
    ])


def _maybe_advance_if_time_is_over(lobby):
    if lobby.status == DrawingGameLobby.STATUS_PLAYING and lobby.current_word and _seconds_left(lobby) <= 0:
        _advance_turn(lobby)


def _handle_player_removed(lobby, removed_player_id=None, removed_index=None, was_current_drawer=False):
    players_count = lobby.players.count()
    if players_count < 2:
        lobby.status = DrawingGameLobby.STATUS_WAITING
        lobby.current_word = ""
        lobby.current_word_choices = []
        lobby.current_drawing = []
        lobby.round_started_at = None
        lobby.current_turn_index = 0
        lobby.players.update(has_guessed_current_word=False)
        lobby.save(update_fields=[
            "status", "current_word", "current_word_choices", "current_drawing",
            "round_started_at", "current_turn_index", "updated_at",
        ])
        return

    if removed_index is not None and removed_index < lobby.current_turn_index:
        lobby.current_turn_index = max(0, lobby.current_turn_index - 1)

    if lobby.current_turn_index >= players_count:
        lobby.current_turn_index = 0
        if lobby.status == DrawingGameLobby.STATUS_PLAYING:
            lobby.current_round_number += 1

    if lobby.status == DrawingGameLobby.STATUS_PLAYING and was_current_drawer:
        lobby.current_word = ""
        lobby.current_word_choices = _pick_word_choices(lobby)
        lobby.current_drawing = []
        lobby.round_started_at = None
        lobby.players.update(has_guessed_current_word=False)

    lobby.save(update_fields=[
        "status", "current_round_number", "current_turn_index", "current_word",
        "current_word_choices", "current_drawing", "round_started_at", "updated_at",
    ])


def _serialize_state(lobby, user):
    players = _players(lobby)
    drawer = _current_drawer(lobby, players)
    me = next((player for player in players if player.user_id == user.id), None)
    guesses = lobby.guesses.select_related("user").filter(
        round_number=lobby.current_round_number,
        turn_index=lobby.current_turn_index,
    ).order_by("created_at")[:80]

    return {
        "lobby": {
            "name": lobby.name,
            "code": lobby.code,
            "status": lobby.status,
            "round": lobby.current_round_number,
            "rounds": lobby.rounds_count,
            "drawTime": lobby.draw_time_seconds,
            "secondsLeft": _seconds_left(lobby),
            "word": lobby.current_word if drawer and drawer.user_id == user.id else "",
            "maskedWord": _masked_word(lobby.current_word) if lobby.current_word else "",
            "hasWord": bool(lobby.current_word),
            "wordChoices": lobby.current_word_choices if drawer and drawer.user_id == user.id and not lobby.current_word else [],
            "currentDrawerId": drawer.user_id if drawer else None,
            "currentDrawerName": drawer.display_label if drawer else "",
            "isOwner": lobby.owner_id == user.id,
        },
        "me": {
            "isDrawer": bool(drawer and drawer.user_id == user.id),
            "hasGuessed": bool(me and me.has_guessed_current_word),
        },
        "players": [
            {
                "id": player.user_id,
                "name": player.display_label,
                "score": player.score,
                "avatarBase": player.avatar_base,
                "avatarColor": player.avatar_color,
                "accentColor": player.accent_color,
                "isDrawer": bool(drawer and drawer.id == player.id),
                "hasGuessed": player.has_guessed_current_word,
            }
            for player in players
        ],
        "drawing": lobby.current_drawing or [],
        "guesses": [
            {
                "user": guess.user.username,
                "message": _("hat das Wort erraten!") if guess.is_correct else guess.message,
                "isCorrect": guess.is_correct,
            }
            for guess in guesses
        ],
    }


@login_required
def skribble_home(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip() or _("Zeichen-Lobby")
        rounds_count = min(max(int(request.POST.get("rounds_count", 3) or 3), 1), 10)
        draw_time_seconds = min(max(int(request.POST.get("draw_time_seconds", 80) or 80), 30), 240)
        max_players = min(max(int(request.POST.get("max_players", 8) or 8), 2), 12)
        custom_words = request.POST.get("custom_words", "").strip()
        use_only_custom_words = request.POST.get("use_only_custom_words") == "on"

        lobby = DrawingGameLobby.objects.create(
            owner=request.user,
            name=name[:80],
            code=_generate_lobby_code(),
            rounds_count=rounds_count,
            draw_time_seconds=draw_time_seconds,
            max_players=max_players,
            custom_words=custom_words,
            use_only_custom_words=use_only_custom_words,
        )
        _get_or_create_player(lobby, request.user)
        messages.success(request, _("Lobby wurde erstellt."))
        return redirect("skribble_lobby", code=lobby.code)

    my_lobbies = DrawingGameLobby.objects.filter(players__user=request.user).distinct().order_by("-updated_at")[:12]
    invites = DrawingGameInvite.objects.select_related("lobby", "from_user").filter(
        to_user=request.user,
        status=DrawingGameInvite.STATUS_PENDING,
    )
    return render(request, "app/skribble_home.html", {
        "my_lobbies": my_lobbies,
        "invites": invites,
    })


@login_required
def skribble_lobby(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper())
    if not _user_can_enter_lobby(lobby, request.user):
        messages.error(request, _("Du bist nicht für diese Lobby eingeladen."))
        return redirect("skribble_home")

    if lobby.players.count() >= lobby.max_players and not lobby.players.filter(user=request.user).exists():
        messages.error(request, _("Diese Lobby ist bereits voll."))
        return redirect("skribble_home")

    _get_or_create_player(lobby, request.user)
    DrawingGameInvite.objects.filter(lobby=lobby, to_user=request.user).update(status=DrawingGameInvite.STATUS_ACCEPTED)

    friend_ids = Friendship.friend_ids_for_user(request.user)
    friends = User.objects.filter(id__in=friend_ids, is_active=True).exclude(id__in=lobby.players.values_list("user_id", flat=True)).order_by("username")
    UserProfile.objects.bulk_create([UserProfile(user=friend) for friend in friends if not hasattr(friend, "profile")], ignore_conflicts=True)
    invited_friend_ids = set(lobby.invites.filter(status=DrawingGameInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted_invite_ids = set(lobby.invites.filter(status=DrawingGameInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    friend_invite_rows = [
        {
            "user": friend,
            "is_invited": friend.id in invited_friend_ids,
            "was_invited": friend.id in accepted_invite_ids,
        }
        for friend in friends
    ]

    return render(request, "app/skribble_lobby.html", {
        "lobby": lobby,
        "friends": friends,
        "friend_invite_rows": friend_invite_rows,
        "avatar_bases": DrawingGamePlayer.AVATAR_BASE_CHOICES,
        "avatar_colors": AVATAR_COLORS,
        "accent_colors": ACCENT_COLORS,
    })


@login_required
@require_POST
def skribble_invite_friend(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper())
    if lobby.owner_id != request.user.id and not lobby.players.filter(user=request.user).exists():
        messages.error(request, _("Du kannst aus dieser Lobby keine Einladungen senden."))
        return redirect("skribble_home")

    friend_id = request.POST.get("friend_id")
    friend = get_object_or_404(User, id=friend_id, is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("skribble_lobby", code=lobby.code)

    DrawingGameInvite.objects.update_or_create(
        lobby=lobby,
        to_user=friend,
        defaults={"from_user": request.user, "status": DrawingGameInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("skribble_lobby", code=lobby.code)


@login_required
@require_POST
def skribble_invite_response(request, invite_id):
    invite = get_object_or_404(DrawingGameInvite, id=invite_id, to_user=request.user)
    action = request.POST.get("action")
    if action == "accept":
        invite.status = DrawingGameInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        _get_or_create_player(invite.lobby, request.user)
        return redirect("skribble_lobby", code=invite.lobby.code)
    invite.status = DrawingGameInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("skribble_home")


@login_required
@require_POST
def skribble_leave_lobby(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        players = _players(lobby)
        player = next((item for item in players if item.user_id == request.user.id), None)
        if not player:
            messages.info(request, _("Du bist nicht mehr in dieser Lobby."))
            return redirect("skribble_home")

        removed_index = next((index for index, item in enumerate(players) if item.id == player.id), None)
        was_current_drawer = removed_index == lobby.current_turn_index
        player.delete()

        if was_current_drawer or lobby.status == DrawingGameLobby.STATUS_PLAYING:
            _handle_player_removed(lobby, removed_player_id=request.user.id, removed_index=removed_index, was_current_drawer=was_current_drawer)
        else:
            lobby.save(update_fields=["updated_at"])

    messages.info(request, _("Du hast die Lobby verlassen. Du kannst über eine Einladung oder als Freund wieder beitreten."))
    return redirect("skribble_home")


@login_required
@require_POST
def skribble_delete_lobby(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper(), owner=request.user)
    lobby_name = lobby.name
    lobby.delete()
    messages.success(request, _("Lobby '%(name)s' wurde gelöscht.") % {"name": lobby_name})
    return redirect("skribble_home")


@login_required
@require_POST
def skribble_update_avatar(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper())
    player = get_object_or_404(DrawingGamePlayer, lobby=lobby, user=request.user)
    player.display_name = (request.POST.get("display_name", "").strip() or request.user.username)[:40]
    player.avatar_base = request.POST.get("avatar_base") if request.POST.get("avatar_base") in dict(DrawingGamePlayer.AVATAR_BASE_CHOICES) else player.avatar_base
    if request.POST.get("avatar_color") in AVATAR_COLORS:
        player.avatar_color = request.POST.get("avatar_color")
    if request.POST.get("accent_color") in ACCENT_COLORS:
        player.accent_color = request.POST.get("accent_color")
    player.save(update_fields=["display_name", "avatar_base", "avatar_color", "accent_color", "last_seen"])
    messages.success(request, _("Avatar wurde gespeichert."))
    return redirect("skribble_lobby", code=lobby.code)


@login_required
@require_POST
def skribble_start(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann starten.")}, status=403)
        if lobby.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Du brauchst mindestens 2 Spieler.")}, status=400)
        lobby.players.update(score=0, has_guessed_current_word=False)
        lobby.status = DrawingGameLobby.STATUS_PLAYING
        lobby.current_round_number = 1
        lobby.current_turn_index = 0
        lobby.current_word = ""
        lobby.current_word_choices = _pick_word_choices(lobby)
        lobby.current_drawing = []
        lobby.round_started_at = None
        lobby.guesses.all().delete()
        lobby.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def skribble_restart(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper(), owner=request.user)
    lobby.status = DrawingGameLobby.STATUS_WAITING
    lobby.current_round_number = 1
    lobby.current_turn_index = 0
    lobby.current_word = ""
    lobby.current_word_choices = []
    lobby.current_drawing = []
    lobby.round_started_at = None
    lobby.players.update(score=0, has_guessed_current_word=False)
    lobby.guesses.all().delete()
    lobby.save()
    return JsonResponse({"ok": True})


@login_required
@require_GET
def skribble_state_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        if not lobby.players.filter(user=request.user).exists():
            return JsonResponse({"ok": False, "error": _("Kein Zugriff.")}, status=403)
        _maybe_advance_if_time_is_over(lobby)
        lobby.refresh_from_db()
        player = lobby.players.filter(user=request.user).first()
        if player:
            player.save(update_fields=["last_seen"])
    return JsonResponse({"ok": True, "state": _serialize_state(lobby, request.user)})


@login_required
@require_POST
def skribble_choose_word_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        players = _players(lobby)
        drawer = _current_drawer(lobby, players)
        if not drawer or drawer.user_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Du bist gerade nicht am Zeichnen.")}, status=403)
        if lobby.current_word:
            return JsonResponse({"ok": False, "error": _("Das Wort wurde schon gewählt.")}, status=400)
        word = request.POST.get("word", "").strip()
        if word not in lobby.current_word_choices:
            return JsonResponse({"ok": False, "error": _("Ungültiges Wort.")}, status=400)
        lobby.current_word = word
        lobby.round_started_at = timezone.now()
        lobby.current_drawing = []
        lobby.players.update(has_guessed_current_word=False)
        lobby.save(update_fields=["current_word", "round_started_at", "current_drawing", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def skribble_draw_api(request, code):
    lobby = get_object_or_404(DrawingGameLobby, code=code.upper())
    drawer = _current_drawer(lobby)
    if not drawer or drawer.user_id != request.user.id or not lobby.current_word:
        return JsonResponse({"ok": False}, status=403)

    action = request.POST.get("action", "stroke")
    if action == "clear":
        lobby.current_drawing = []
    else:
        stroke = {
            "points": request.POST.get("points", ""),
            "color": request.POST.get("color", "#111827")[:20],
            "size": min(max(int(request.POST.get("size", 5) or 5), 1), 40),
        }
        drawing = lobby.current_drawing or []
        if len(drawing) < 1200 and stroke["points"]:
            drawing.append(stroke)
        lobby.current_drawing = drawing
    lobby.save(update_fields=["current_drawing", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def skribble_guess_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        _maybe_advance_if_time_is_over(lobby)
        player = get_object_or_404(DrawingGamePlayer.objects.select_for_update(), lobby=lobby, user=request.user)
        drawer = _current_drawer(lobby)
        message = request.POST.get("message", "").strip()[:160]
        if not message or lobby.status != DrawingGameLobby.STATUS_PLAYING or not lobby.current_word:
            return JsonResponse({"ok": False}, status=400)
        if drawer and drawer.user_id == request.user.id:
            return JsonResponse({"ok": False, "error": _("Der Zeichner darf nicht raten.")}, status=403)

        is_correct = _normalize_word(message) == _normalize_word(lobby.current_word)
        if player.has_guessed_current_word and is_correct:
            is_correct = False

        DrawingGameGuess.objects.create(
            lobby=lobby,
            user=request.user,
            round_number=lobby.current_round_number,
            turn_index=lobby.current_turn_index,
            message=message,
            is_correct=is_correct,
        )

        if is_correct:
            player.has_guessed_current_word = True
            player.score += max(25, _seconds_left(lobby) * 5)
            player.save(update_fields=["has_guessed_current_word", "score", "last_seen"])
            if drawer:
                drawer.score += 50
                drawer.save(update_fields=["score", "last_seen"])

            remaining = lobby.players.exclude(user_id=drawer.user_id if drawer else None).filter(has_guessed_current_word=False).count()
            if remaining == 0:
                _advance_turn(lobby)

    return JsonResponse({"ok": True})
