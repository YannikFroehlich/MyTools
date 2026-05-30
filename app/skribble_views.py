import random
import string
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
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
    SkribbleStats,
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


def _stroke_point_count(points):
    return len([point for point in str(points or "").split(";") if point.strip()])


def _int_from_request(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_segment(raw_segment):
    if not isinstance(raw_segment, dict):
        return None
    segment_id = str(raw_segment.get("id", "")).strip()[:60]
    points = str(raw_segment.get("points", "")).strip()
    if not segment_id or _stroke_point_count(points) < 2:
        return None
    try:
        size = min(max(int(raw_segment.get("size", 5) or 5), 1), 40)
    except (TypeError, ValueError):
        size = 5
    order = _int_from_request(raw_segment.get("order"))
    return {
        "id": segment_id,
        "order": order,
        "points": points,
        "color": str(raw_segment.get("color", "#111827"))[:20],
        "size": size,
    }


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
    if lobby.status == DrawingGameLobby.STATUS_ROUND_SUMMARY:
        return 0
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


def _build_round_summary(lobby, next_round_number, next_turn_index, is_game_over=False):
    players = _players(lobby)
    drawer = _current_drawer(lobby, players)
    correct_guesses = list(lobby.guesses.select_related("user").filter(
        round_number=lobby.current_round_number,
        turn_index=lobby.current_turn_index,
        is_correct=True,
    ))
    points_by_user = {player.user_id: 0 for player in players}
    for guess in correct_guesses:
        points_by_user[guess.user_id] = points_by_user.get(guess.user_id, 0) + int(guess.points_awarded or 0)
        if drawer:
            points_by_user[drawer.user_id] = points_by_user.get(drawer.user_id, 0) + int(guess.drawer_points_awarded or 0)

    rows = [
        {
            "id": player.user_id,
            "name": player.display_label,
            "score": player.score,
            "points": points_by_user.get(player.user_id, 0),
            "isDrawer": bool(drawer and drawer.id == player.id),
            "hasGuessed": player.has_guessed_current_word,
        }
        for player in players
    ]
    rows.sort(key=lambda item: (-item["score"], item["name"].lower()))

    return {
        "round": lobby.current_round_number,
        "rounds": lobby.rounds_count,
        "turnIndex": lobby.current_turn_index,
        "word": lobby.current_word,
        "drawerName": drawer.display_label if drawer else "",
        "isGameOver": is_game_over,
        "nextRound": next_round_number,
        "nextTurnIndex": next_turn_index,
        "rows": rows,
    }


def _store_finished_lobby_stats(lobby):
    players = list(lobby.players.select_related("user").order_by("-score", "joined_at"))
    if not players:
        return
    top_score = players[0].score
    winner_ids = {player.user_id for player in players if player.score == top_score and top_score > 0}
    correct_guess_counts = dict(
        DrawingGameGuess.objects.filter(lobby=lobby, is_correct=True)
        .values_list("user_id")
        .annotate(total=Count("id"))
    )
    for player in players:
        stats, _ = SkribbleStats.objects.get_or_create(user=player.user)
        stats.games_played += 1
        if player.user_id in winner_ids:
            stats.games_won += 1
        stats.correct_guesses += int(correct_guess_counts.get(player.user_id, 0))
        stats.total_score += int(player.score or 0)
        stats.save(update_fields=["games_played", "games_won", "correct_guesses", "total_score", "updated_at"])


def _show_round_summary(lobby):
    players_count = lobby.players.count()
    if players_count < 2:
        lobby.status = DrawingGameLobby.STATUS_WAITING
        lobby.current_word = ""
        lobby.current_word_choices = []
        lobby.round_started_at = None
        lobby.round_summary = {}
        lobby.summary_started_at = None
        lobby.save(update_fields=[
            "status", "current_word", "current_word_choices", "round_started_at",
            "round_summary", "summary_started_at", "updated_at",
        ])
        return

    next_turn_index = lobby.current_turn_index + 1
    next_round_number = lobby.current_round_number
    if next_turn_index >= players_count:
        next_turn_index = 0
        next_round_number += 1

    is_game_over = next_round_number > lobby.rounds_count
    lobby.status = DrawingGameLobby.STATUS_ROUND_SUMMARY
    lobby.current_word_choices = []
    lobby.round_started_at = None
    lobby.round_summary = _build_round_summary(lobby, next_round_number, next_turn_index, is_game_over)
    lobby.summary_started_at = timezone.now()
    lobby.save(update_fields=[
        "status", "current_word_choices", "round_started_at",
        "round_summary", "summary_started_at", "updated_at",
    ])


def _continue_after_round_summary(lobby):
    if lobby.status != DrawingGameLobby.STATUS_ROUND_SUMMARY:
        return

    summary = lobby.round_summary or {}
    if summary.get("isGameOver"):
        _store_finished_lobby_stats(lobby)
        lobby.status = DrawingGameLobby.STATUS_FINISHED
        lobby.current_word = ""
        lobby.current_word_choices = []
        lobby.current_drawing = []
        lobby.round_started_at = None
        lobby.round_summary = {}
        lobby.summary_started_at = None
        lobby.save(update_fields=[
            "status", "current_word", "current_word_choices", "current_drawing",
            "round_started_at", "round_summary", "summary_started_at", "updated_at",
        ])
        return

    lobby.current_round_number = int(summary.get("nextRound") or lobby.current_round_number)
    lobby.current_turn_index = int(summary.get("nextTurnIndex") or 0)
    lobby.status = DrawingGameLobby.STATUS_PLAYING
    _reset_turn_state(lobby)
    lobby.round_summary = {}
    lobby.summary_started_at = None
    lobby.save(update_fields=[
        "status", "current_round_number", "current_turn_index", "current_word",
        "current_word_choices", "current_drawing", "round_started_at",
        "round_summary", "summary_started_at", "updated_at",
    ])


def _maybe_advance_if_time_is_over(lobby):
    if lobby.status == DrawingGameLobby.STATUS_PLAYING and lobby.current_word and _seconds_left(lobby) <= 0:
        _show_round_summary(lobby)


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


def _friend_invite_rows(lobby, user):
    friend_ids = Friendship.friend_ids_for_user(user)
    current_player_ids = lobby.players.values_list("user_id", flat=True)
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
        lobby.invites
        .filter(status=DrawingGameInvite.STATUS_PENDING)
        .values_list("to_user_id", flat=True)
    )
    accepted_invite_ids = set(
        lobby.invites
        .filter(status=DrawingGameInvite.STATUS_ACCEPTED)
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


def _serialize_friend_invites(lobby, user):
    rows = _friend_invite_rows(lobby, user)
    return [
        {
            "id": row["user"].id,
            "name": row["user"].get_full_name() or row["user"].username,
            "username": row["user"].username,
            "initial": (row["user"].username[:1] or "?").upper(),
            "isInvited": row["is_invited"],
            "wasInvited": row["was_invited"],
        }
        for row in rows
    ]


def _serialize_state(lobby, user, drawing_after=0):
    players = _players(lobby)
    drawer = _current_drawer(lobby, players)
    me = next((player for player in players if player.user_id == user.id), None)
    guesses = lobby.guesses.select_related("user").filter(
        round_number=lobby.current_round_number,
        turn_index=lobby.current_turn_index,
    ).order_by("created_at")[:80]

    drawing = lobby.current_drawing or []
    try:
        drawing_after = max(0, int(drawing_after or 0))
    except (TypeError, ValueError):
        drawing_after = 0
    if drawing_after > len(drawing):
        drawing_after = 0

    return {
        "lobby": {
            "name": lobby.name,
            "code": lobby.code,
            "status": lobby.status,
            "round": lobby.current_round_number,
            "rounds": lobby.rounds_count,
            "drawTime": lobby.draw_time_seconds,
            "secondsLeft": _seconds_left(lobby),
            "word": lobby.current_word if (drawer and drawer.user_id == user.id) or lobby.status == DrawingGameLobby.STATUS_ROUND_SUMMARY else "",
            "maskedWord": _masked_word(lobby.current_word) if lobby.current_word else "",
            "hasWord": bool(lobby.current_word),
            "wordChoices": lobby.current_word_choices if lobby.status == DrawingGameLobby.STATUS_PLAYING and drawer and drawer.user_id == user.id and not lobby.current_word else [],
            "currentDrawerId": drawer.user_id if drawer else None,
            "currentDrawerName": drawer.display_label if drawer else "",
            "isOwner": lobby.owner_id == user.id,
            "roundSummary": lobby.round_summary or {},
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
        "friendInvites": _serialize_friend_invites(lobby, user),
        "drawing": drawing if drawing_after <= 0 else [],
        "drawingDelta": drawing[drawing_after:] if drawing_after > 0 else [],
        "drawingRevision": len(drawing),
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

    friend_ids = Friendship.friend_ids_for_user(request.user)
    my_lobbies = (
        DrawingGameLobby.objects
        .filter(players__user=request.user)
        .annotate(players_count=Count("players", distinct=True))
        .distinct()
        .order_by("-updated_at")[:12]
    )
    invites = DrawingGameInvite.objects.select_related("lobby", "from_user").filter(
        to_user=request.user,
        status=DrawingGameInvite.STATUS_PENDING,
    )
    discover_lobbies = (
        DrawingGameLobby.objects
        .filter(status__in=[DrawingGameLobby.STATUS_WAITING, DrawingGameLobby.STATUS_PLAYING])
        .filter(Q(owner_id__in=friend_ids) | Q(invites__to_user=request.user) | Q(players__user=request.user))
        .select_related("owner")
        .annotate(players_count=Count("players", distinct=True))
        .distinct()
        .order_by("-updated_at")[:16]
    )
    return render(request, "app/skribble_home.html", {
        "my_lobbies": my_lobbies,
        "invites": invites,
        "discover_lobbies": discover_lobbies,
    })


@login_required
def skribble_lobby(request, code):
    lobby = DrawingGameLobby.objects.filter(code=code.upper()).first()
    if not lobby:
        messages.info(request, _("Diese Lobby wurde gelöscht."))
        return redirect("skribble_home")

    if not _user_can_enter_lobby(lobby, request.user):
        messages.error(request, _("Du bist nicht für diese Lobby eingeladen."))
        return redirect("skribble_home")

    if lobby.players.count() >= lobby.max_players and not lobby.players.filter(user=request.user).exists():
        messages.error(request, _("Diese Lobby ist bereits voll."))
        return redirect("skribble_home")

    _get_or_create_player(lobby, request.user)
    DrawingGameInvite.objects.filter(lobby=lobby, to_user=request.user).update(status=DrawingGameInvite.STATUS_ACCEPTED)

    friend_invite_rows = _friend_invite_rows(lobby, request.user)

    return render(request, "app/skribble_lobby.html", {
        "lobby": lobby,
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
        lobby.round_summary = {}
        lobby.summary_started_at = None
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
    lobby.round_summary = {}
    lobby.summary_started_at = None
    lobby.players.update(score=0, has_guessed_current_word=False)
    lobby.guesses.all().delete()
    lobby.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def skribble_continue_round(request, code):
    with transaction.atomic():
        lobby = DrawingGameLobby.objects.select_for_update().filter(code=code.upper()).first()
        if not lobby:
            return JsonResponse({
                "ok": False,
                "lobbyDeleted": True,
                "redirectUrl": reverse("skribble_home"),
                "error": _("Diese Lobby wurde gelöscht."),
            }, status=410)

        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann fortfahren.")}, status=403)
        _continue_after_round_summary(lobby)
    return JsonResponse({"ok": True})


@login_required
@require_GET
def skribble_state_api(request, code):
    with transaction.atomic():
        lobby = DrawingGameLobby.objects.select_for_update().filter(code=code.upper()).first()
        if not lobby:
            return JsonResponse({
                "ok": False,
                "lobbyDeleted": True,
                "redirectUrl": reverse("skribble_home"),
                "error": _("Diese Lobby wurde gelöscht."),
            }, status=410)

        if not lobby.players.filter(user=request.user).exists():
            return JsonResponse({"ok": False, "error": _("Kein Zugriff.")}, status=403)
        _maybe_advance_if_time_is_over(lobby)
        lobby.refresh_from_db()
        player = lobby.players.filter(user=request.user).first()
        if player:
            player.save(update_fields=["last_seen"])
    return JsonResponse({
        "ok": True,
        "state": _serialize_state(lobby, request.user, request.GET.get("after", 0)),
    })


@login_required
@require_POST
def skribble_choose_word_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        players = _players(lobby)
        drawer = _current_drawer(lobby, players)
        if not drawer or drawer.user_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Du bist gerade nicht am Zeichnen.")}, status=403)
        if lobby.status != DrawingGameLobby.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Die Runde laeuft gerade nicht.")}, status=400)
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
    with transaction.atomic():
        lobby = get_object_or_404(DrawingGameLobby.objects.select_for_update(), code=code.upper())
        drawer = _current_drawer(lobby)
        if lobby.status != DrawingGameLobby.STATUS_PLAYING or not drawer or drawer.user_id != request.user.id or not lobby.current_word:
            return JsonResponse({"ok": False}, status=403)

        action = request.POST.get("action", "stroke")
        if action == "clear":
            lobby.current_drawing = []
        elif action == "segments":
            try:
                raw_segments = json.loads(request.POST.get("segments", "[]"))
            except ValueError:
                raw_segments = []
            drawing = lobby.current_drawing or []
            existing_ids = {item.get("id") for item in drawing if item.get("id")}
            for raw_segment in raw_segments[:80]:
                segment = _normalize_segment(raw_segment)
                if segment and segment["id"] not in existing_ids and len(drawing) < 8000:
                    drawing.append(segment)
                    existing_ids.add(segment["id"])
            drawing.sort(key=lambda item: (_int_from_request(item.get("order")), str(item.get("id", ""))))
            lobby.current_drawing = drawing
        else:
            stroke_id = request.POST.get("stroke_id", "").strip()[:40]
            stroke_version = max(0, _int_from_request(request.POST.get("stroke_version")))
            stroke = {
                "id": stroke_id,
                "version": stroke_version,
                "points": request.POST.get("points", ""),
                "color": request.POST.get("color", "#111827")[:20],
                "size": min(max(int(request.POST.get("size", 5) or 5), 1), 40),
            }
            drawing = lobby.current_drawing or []
            existing_index = next(
                (index for index, item in enumerate(drawing) if stroke_id and item.get("id") == stroke_id),
                None,
            )
            if stroke["points"] and existing_index is not None:
                existing = drawing[existing_index]
                existing_version = _int_from_request(existing.get("version"))
                existing_points = existing.get("points", "")
                if (
                    stroke_version > existing_version
                    or (
                        stroke_version == existing_version
                        and _stroke_point_count(stroke["points"]) >= _stroke_point_count(existing_points)
                    )
                ):
                    drawing[existing_index] = stroke
            elif len(drawing) < 2000 and stroke["points"]:
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

        guess = DrawingGameGuess.objects.create(
            lobby=lobby,
            user=request.user,
            round_number=lobby.current_round_number,
            turn_index=lobby.current_turn_index,
            message=message,
            is_correct=is_correct,
        )

        if is_correct:
            player.has_guessed_current_word = True
            points_awarded = max(25, _seconds_left(lobby) * 5)
            drawer_points_awarded = 50
            player.score += points_awarded
            player.save(update_fields=["has_guessed_current_word", "score", "last_seen"])
            if drawer:
                drawer.score += drawer_points_awarded
                drawer.save(update_fields=["score", "last_seen"])
            guess.points_awarded = points_awarded
            guess.drawer_points_awarded = drawer_points_awarded if drawer else 0
            guess.save(update_fields=["points_awarded", "drawer_points_awarded"])

            remaining = lobby.players.exclude(user_id=drawer.user_id if drawer else None).filter(has_guessed_current_word=False).count()
            if remaining == 0:
                _show_round_summary(lobby)

    return JsonResponse({"ok": True})
