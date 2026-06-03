import random
import string

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
    Friendship,
    StadtLandFlussInvite,
    StadtLandFlussLobby,
    StadtLandFlussPlayer,
    StadtLandFlussRoundAnswer,
    UserProfile,
)


DEFAULT_CATEGORIES = ["Stadt", "Land", "Fluss", "Name", "Tier", "Beruf"]
LETTER_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _generate_lobby_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not StadtLandFlussLobby.objects.filter(code=code).exists():
            return code


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _normalize_categories(value):
    if isinstance(value, list):
        raw_categories = value
    else:
        raw_categories = str(value or "").replace(";", ",").split(",")
    categories = []
    for category in raw_categories:
        clean = str(category).strip()
        if clean and clean.lower() not in {item.lower() for item in categories}:
            categories.append(clean[:40])
    return categories[:10] or DEFAULT_CATEGORIES


def _clamp_int(value, fallback, min_value, max_value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(min_value, min(parsed, max_value))


def _join_lobby(lobby, user):
    player, created = StadtLandFlussPlayer.objects.get_or_create(
        lobby=lobby,
        user=user,
        defaults={"display_name": _player_name(user)[:40]},
    )
    if not created:
        player.last_seen = timezone.now()
        player.save(update_fields=["last_seen"])
    return player


def _delete_empty_lobbies():
    StadtLandFlussLobby.objects.filter(players__isnull=True).delete()

def _next_letter(lobby):
    used = [str(letter).upper() for letter in (lobby.used_letters if isinstance(lobby.used_letters, list) else [])]
    available = [letter for letter in LETTER_POOL if letter not in used]
    if not available:
        used = []
        available = LETTER_POOL[:]
    letter = random.choice(available)
    lobby.used_letters = used + [letter]
    return letter


def _start_next_round(lobby):
    lobby.current_round_number += 1
    lobby.current_letter = _next_letter(lobby)
    lobby.round_started_at = timezone.now()
    lobby.round_summary = {}
    lobby.status = StadtLandFlussLobby.STATUS_PLAYING
    lobby.save()

    for player in lobby.players.all():
        StadtLandFlussRoundAnswer.objects.update_or_create(
            lobby=lobby,
            player=player,
            round_number=lobby.current_round_number,
            defaults={
                "letter": lobby.current_letter,
                "answers": {},
                "points": {},
                "total_points": 0,
                "is_submitted": False,
                "submitted_at": None,
            },
        )


def _seconds_left(lobby):
    if lobby.status != StadtLandFlussLobby.STATUS_PLAYING or not lobby.round_started_at:
        return None
    elapsed = (timezone.now() - lobby.round_started_at).total_seconds()
    return max(0, int(lobby.round_time_seconds - elapsed))


def _normalize_answer(value):
    return " ".join(str(value or "").strip().split())[:80]


def _answer_is_valid(answer, letter):
    return answer and answer.casefold().startswith(letter.casefold())


def _sync_player_scores(lobby):
    for player in lobby.players.all():
        player.score = sum(
            answer.total_points
            for answer in StadtLandFlussRoundAnswer.objects.filter(lobby=lobby, player=player)
        )
        player.save(update_fields=["score"])


def _compute_round_points(lobby, answers, votes):
    categories = lobby.normalized_categories
    valid_by_category = {category: {} for category in categories}

    for row in answers:
        row.answers = {
            category: _normalize_answer((row.answers or {}).get(category, ""))
            for category in categories
        }
        for category, value in row.answers.items():
            accepted = bool(votes.get(category, {}).get(str(row.player_id), False))
            if accepted and value:
                valid_by_category[category].setdefault(value.casefold(), []).append(row.player_id)

    points_by_player = {row.player_id: {} for row in answers}
    for category in categories:
        accepted_player_ids = [
            row.player_id
            for row in answers
            if bool(votes.get(category, {}).get(str(row.player_id), False))
            and (row.answers or {}).get(category, "")
        ]
        single_valid_answer = len(accepted_player_ids) == 1

        for row in answers:
            value = (row.answers or {}).get(category, "")
            accepted = bool(votes.get(category, {}).get(str(row.player_id), False))
            if not accepted or not value:
                points = 0
            elif single_valid_answer:
                points = 20
            else:
                duplicates = valid_by_category[category].get(value.casefold(), [])
                points = 10 if len(duplicates) == 1 else 5
            points_by_player[row.player_id][category] = points

    return points_by_player


def _build_round_summary(lobby, answers, reason, votes=None):
    categories = lobby.normalized_categories
    votes = votes or {}
    for row in answers:
        clean_answers = {
            category: _normalize_answer((row.answers or {}).get(category, ""))
            for category in categories
        }
        row.answers = clean_answers
        for category, value in clean_answers.items():
            votes.setdefault(category, {})
            votes[category].setdefault(str(row.player_id), False)

    points_by_player = _compute_round_points(lobby, answers, votes)
    categories_summary = []
    player_rows = []

    for row in answers:
        row.points = points_by_player.get(row.player_id, {})
        row.total_points = sum(row.points.values())
        row.is_submitted = True
        if not row.submitted_at:
            row.submitted_at = timezone.now()
        row.save(update_fields=["answers", "points", "total_points", "is_submitted", "submitted_at", "updated_at"])
        player_rows.append({
            "playerId": row.player_id,
            "name": row.player.display_label,
            "answers": row.answers,
            "points": row.points,
            "roundPoints": row.total_points,
            "score": row.player.score,
        })

    _sync_player_scores(lobby)
    refreshed_players = {
        player.id: player.score
        for player in lobby.players.all()
    }
    for row in player_rows:
        row["score"] = refreshed_players.get(row["playerId"], row["score"])

    for category in categories:
        entries = []
        for answer in answers:
            entries.append({
                "playerId": answer.player_id,
                "name": answer.player.display_label,
                "answer": (answer.answers or {}).get(category, ""),
                "accepted": bool(votes.get(category, {}).get(str(answer.player_id), False)),
                "points": (answer.points or {}).get(category, 0),
            })
        categories_summary.append({
            "name": category,
            "entries": entries,
        })

    return {
        "reason": reason,
        "round": lobby.current_round_number,
        "rounds": lobby.rounds_count,
        "letter": lobby.current_letter,
        "categories": categories,
        "categoryResults": categories_summary,
        "rows": sorted(player_rows, key=lambda item: item["score"], reverse=True),
        "votes": votes,
        "isGameOver": lobby.current_round_number >= lobby.rounds_count,
    }


def _final_ranking(lobby):
    players = list(lobby.players.select_related("user").order_by("-score", "joined_at"))
    ranking = []
    previous_score = None
    previous_place = 0
    for index, player in enumerate(players, start=1):
        place = previous_place if previous_score == player.score else index
        ranking.append({
            "place": place,
            "playerId": player.id,
            "name": player.display_label,
            "score": player.score,
        })
        previous_score = player.score
        previous_place = place
    return ranking


def _ensure_round_finished_if_needed(lobby):
    if lobby.status != StadtLandFlussLobby.STATUS_PLAYING:
        return
    if _seconds_left(lobby) == 0:
        _score_round(lobby, "timer")


def _score_round(lobby, reason="manual"):
    answers = list(
        StadtLandFlussRoundAnswer.objects
        .select_related("player", "player__user")
        .filter(lobby=lobby, round_number=lobby.current_round_number)
        .order_by("player__joined_at")
    )
    existing_summary = lobby.round_summary if isinstance(lobby.round_summary, dict) else {}
    votes = existing_summary.get("votes") if existing_summary.get("round") == lobby.current_round_number else None
    lobby.round_summary = _build_round_summary(lobby, answers, reason, votes=votes)
    lobby.status = StadtLandFlussLobby.STATUS_ROUND_SUMMARY
    lobby.round_started_at = None
    lobby.save(update_fields=["round_summary", "status", "round_started_at", "updated_at"])


def _friend_invite_rows(lobby, user):
    current_player_ids = list(lobby.players.values_list("user_id", flat=True))
    if lobby.players.count() >= lobby.max_players:
        return []
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
        lobby.invites
        .filter(status=StadtLandFlussInvite.STATUS_PENDING)
        .values_list("to_user_id", flat=True)
    )
    accepted_invite_ids = set(
        lobby.invites
        .filter(status=StadtLandFlussInvite.STATUS_ACCEPTED)
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
    return [
        {
            "id": row["user"].id,
            "name": _player_name(row["user"]),
            "initial": row["user"].username[:1].upper(),
            "isInvited": row["is_invited"],
            "wasInvited": row["was_invited"],
        }
        for row in _friend_invite_rows(lobby, user)
    ]


def _serialize_lobby(lobby, user):
    _ensure_round_finished_if_needed(lobby)
    lobby.refresh_from_db()
    player = lobby.players.filter(user=user).first()
    current_answer = None
    if player and lobby.current_round_number:
        current_answer = StadtLandFlussRoundAnswer.objects.filter(
            lobby=lobby,
            player=player,
            round_number=lobby.current_round_number,
        ).first()

    return {
        "id": lobby.id,
        "name": lobby.name,
        "code": lobby.code,
        "status": lobby.status,
        "statusLabel": lobby.get_status_display(),
        "isOwner": lobby.owner_id == user.id,
        "categories": lobby.normalized_categories,
        "round": lobby.current_round_number,
        "rounds": lobby.rounds_count,
        "letter": lobby.current_letter,
        "secondsLeft": _seconds_left(lobby),
        "roundTime": lobby.round_time_seconds,
        "summary": lobby.round_summary or {},
        "finalRanking": _final_ranking(lobby) if lobby.status == StadtLandFlussLobby.STATUS_FINISHED else [],
        "me": {
            "playerId": player.id if player else None,
            "isSubmitted": bool(current_answer and current_answer.is_submitted),
            "answers": current_answer.answers if current_answer else {},
        },
        "players": [
            {
                "id": p.id,
                "name": p.display_label,
                "score": p.score,
                "isMe": p.user_id == user.id,
                "isOwner": p.user_id == lobby.owner_id,
                "submitted": StadtLandFlussRoundAnswer.objects.filter(
                    lobby=lobby,
                    player=p,
                    round_number=lobby.current_round_number,
                    is_submitted=True,
                ).exists() if lobby.current_round_number else False,
            }
            for p in lobby.players.select_related("user").all()
        ],
        "friendInvites": _serialize_friend_invites(lobby, user),
    }


def _home_lobbies_for_user(user):
    return (
        StadtLandFlussLobby.objects
        .filter(Q(owner=user) | Q(players__user=user))
        .annotate(players_count=Count("players", distinct=True))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        StadtLandFlussInvite.objects
        .select_related("lobby", "from_user")
        .filter(to_user=user, status=StadtLandFlussInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _discover_lobbies_for_user(user):
    friend_ids = Friendship.friend_ids_for_user(user)
    return (
        StadtLandFlussLobby.objects
        .filter(
            Q(owner=user) | Q(owner_id__in=friend_ids) | Q(players__user=user),
            status__in=[StadtLandFlussLobby.STATUS_WAITING, StadtLandFlussLobby.STATUS_PLAYING, StadtLandFlussLobby.STATUS_ROUND_SUMMARY],
        )
        .annotate(players_count=Count("players", distinct=True))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _serialize_home_lobby(lobby):
    return {
        "id": lobby.id,
        "name": lobby.name,
        "code": lobby.code,
        "statusLabel": lobby.get_status_display(),
        "owner": lobby.owner.username,
        "playersCount": getattr(lobby, "players_count", lobby.players.count()),
        "maxPlayers": lobby.max_players,
        "rounds": lobby.rounds_count,
        "seconds": lobby.round_time_seconds,
        "url": reverse("stadtlandfluss_lobby", args=[lobby.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "lobbyName": invite.lobby.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("stadtlandfluss_invite_response", args=[invite.id]),
        "declineUrl": reverse("stadtlandfluss_invite_response", args=[invite.id]),
    }


@login_required
def stadtlandfluss_home(request):
    _delete_empty_lobbies()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            lobby = StadtLandFlussLobby.objects.create(
                owner=request.user,
                name=(request.POST.get("name", "").strip() or _("Stadt Land Fluss"))[:80],
                code=_generate_lobby_code(),
                categories=_normalize_categories(request.POST.get("categories", "")),
                rounds_count=_clamp_int(request.POST.get("rounds_count"), 5, 1, 12),
                round_time_seconds=_clamp_int(request.POST.get("round_time_seconds"), 90, 30, 240),
                max_players=_clamp_int(request.POST.get("max_players"), 8, 2, 16),
            )
            _join_lobby(lobby, request.user)
            return redirect("stadtlandfluss_lobby", code=lobby.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("stadtlandfluss_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/stadtlandfluss_home.html", {
        "my_lobbies": _home_lobbies_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
        "discover_lobbies": _discover_lobbies_for_user(request.user),
        "default_categories": ", ".join(DEFAULT_CATEGORIES),
    })


@login_required
@require_GET
def stadtlandfluss_home_state_api(request):
    _delete_empty_lobbies()
    return JsonResponse({
        "ok": True,
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
        "discoverLobbies": [_serialize_home_lobby(lobby) for lobby in _discover_lobbies_for_user(request.user)],
        "myLobbies": [_serialize_home_lobby(lobby) for lobby in _home_lobbies_for_user(request.user)],
    })


@login_required
def stadtlandfluss_lobby(request, code):
    lobby = (
        StadtLandFlussLobby.objects
        .select_related("owner")
        .prefetch_related("players")
        .filter(code=code.upper())
        .first()
    )
    if not lobby:
        messages.warning(request, _("Diese Stadt-Land-Fluss-Lobby existiert nicht mehr."))
        return redirect("stadtlandfluss_home")
    is_member = lobby.players.filter(user=request.user).exists()
    if not is_member and lobby.players.count() >= lobby.max_players:
        messages.error(request, _("Diese Stadt-Land-Fluss-Lobby ist bereits voll."))
        return redirect("stadtlandfluss_home")
    if not is_member and lobby.status != StadtLandFlussLobby.STATUS_WAITING:
        messages.error(request, _("Diese Runde läuft bereits. Warte auf die nächste Lobby."))
        return redirect("stadtlandfluss_home")
    _join_lobby(lobby, request.user)
    return render(request, "app/stadtlandfluss_lobby.html", {
        "lobby": lobby,
        "friend_invite_rows": _friend_invite_rows(lobby, request.user),
    })


@login_required
@require_POST
def stadtlandfluss_invite_friend(request, code):
    lobby = get_object_or_404(StadtLandFlussLobby, code=code.upper())
    if not (lobby.owner_id == request.user.id or lobby.players.filter(user=request.user).exists()):
        messages.error(request, _("Du bist nicht in dieser Lobby."))
        return redirect("stadtlandfluss_home")
    if lobby.players.count() >= lobby.max_players:
        messages.error(request, _("Diese Lobby ist bereits voll."))
        return redirect("stadtlandfluss_lobby", code=lobby.code)

    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("stadtlandfluss_lobby", code=lobby.code)

    StadtLandFlussInvite.objects.update_or_create(
        lobby=lobby,
        to_user=friend,
        defaults={"from_user": request.user, "status": StadtLandFlussInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("stadtlandfluss_lobby", code=lobby.code)


@login_required
@require_POST
def stadtlandfluss_invite_response(request, invite_id):
    invite = get_object_or_404(
        StadtLandFlussInvite.objects.select_related("lobby"),
        id=invite_id,
        to_user=request.user,
    )
    if request.POST.get("action") == "accept":
        invite.status = StadtLandFlussInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("stadtlandfluss_lobby", code=invite.lobby.code)

    invite.status = StadtLandFlussInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("stadtlandfluss_home")


@login_required
@require_GET
def stadtlandfluss_state_api(request, code):
    lobby = StadtLandFlussLobby.objects.filter(code=code.upper()).first()
    if not lobby:
        return JsonResponse({
            "ok": False,
            "lobbyDeleted": True,
            "error": _("Diese Stadt-Land-Fluss-Lobby wurde gelöscht."),
            "redirectUrl": reverse("stadtlandfluss_home"),
        }, status=410)
    if not lobby.players.filter(user=request.user).exists():
        return JsonResponse({"ok": False, "error": _("Du bist nicht in dieser Lobby.")}, status=403)
    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_start(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann starten.")}, status=403)
        if lobby.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Stadt Land Fluss braucht mindestens zwei Spieler.")}, status=400)
        if lobby.status not in [StadtLandFlussLobby.STATUS_WAITING, StadtLandFlussLobby.STATUS_FINISHED]:
            return JsonResponse({"ok": False, "error": _("Diese Lobby läuft bereits.")}, status=400)
        if lobby.status == StadtLandFlussLobby.STATUS_FINISHED:
            lobby.players.update(score=0)
            lobby.current_round_number = 0
            lobby.used_letters = []
            lobby.answers.all().delete()
        _start_next_round(lobby)
    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_submit_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        player = get_object_or_404(StadtLandFlussPlayer, lobby=lobby, user=request.user)
        _ensure_round_finished_if_needed(lobby)
        lobby.refresh_from_db()
        if lobby.status != StadtLandFlussLobby.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Diese Runde ist bereits vorbei.")}, status=400)

        answer_row, _created = StadtLandFlussRoundAnswer.objects.get_or_create(
            lobby=lobby,
            player=player,
            round_number=lobby.current_round_number,
            defaults={"letter": lobby.current_letter},
        )
        if answer_row.is_submitted:
            return JsonResponse({"ok": False, "error": _("Du hast diese Runde schon abgegeben.")}, status=400)

        submitted_answers = {
            category: _normalize_answer(request.POST.get(f"answer_{index}", ""))
            for index, category in enumerate(lobby.normalized_categories)
        }
        answer_row.answers = submitted_answers
        answer_row.letter = lobby.current_letter
        answer_row.is_submitted = True
        answer_row.submitted_at = timezone.now()
        answer_row.save(update_fields=["answers", "letter", "is_submitted", "submitted_at", "updated_at"])
        _score_round(lobby, "stopped")

    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_draft_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        player = get_object_or_404(StadtLandFlussPlayer, lobby=lobby, user=request.user)
        _ensure_round_finished_if_needed(lobby)
        lobby.refresh_from_db()
        if lobby.status != StadtLandFlussLobby.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Diese Runde ist bereits vorbei.")}, status=400)

        answer_row, _created = StadtLandFlussRoundAnswer.objects.get_or_create(
            lobby=lobby,
            player=player,
            round_number=lobby.current_round_number,
            defaults={"letter": lobby.current_letter},
        )
        if answer_row.is_submitted:
            return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})

        answer_row.answers = {
            category: _normalize_answer(request.POST.get(f"answer_{index}", ""))
            for index, category in enumerate(lobby.normalized_categories)
        }
        answer_row.letter = lobby.current_letter
        answer_row.save(update_fields=["answers", "letter", "updated_at"])

    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_vote_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        if not lobby.players.filter(user=request.user).exists():
            return JsonResponse({"ok": False, "error": _("Du bist nicht in dieser Lobby.")}, status=403)
        if lobby.status != StadtLandFlussLobby.STATUS_ROUND_SUMMARY:
            return JsonResponse({"ok": False, "error": _("Es gibt gerade keine Auswertung.")}, status=400)

        category = request.POST.get("category", "").strip()
        player_id = request.POST.get("player_id", "").strip()
        accepted = request.POST.get("accepted") == "true"
        if category not in lobby.normalized_categories:
            return JsonResponse({"ok": False, "error": _("Unbekannte Kategorie.")}, status=400)

        answers = list(
            StadtLandFlussRoundAnswer.objects
            .select_related("player", "player__user")
            .filter(lobby=lobby, round_number=lobby.current_round_number)
            .order_by("player__joined_at")
        )
        if not any(str(answer.player_id) == player_id for answer in answers):
            return JsonResponse({"ok": False, "error": _("Unbekannter Spieler.")}, status=400)

        summary = lobby.round_summary if isinstance(lobby.round_summary, dict) else {}
        votes = summary.get("votes") if isinstance(summary.get("votes"), dict) else {}
        votes.setdefault(category, {})
        answer = next(answer for answer in answers if str(answer.player_id) == player_id)
        if not _normalize_answer((answer.answers or {}).get(category, "")):
            accepted = False
        votes[category][player_id] = accepted

        lobby.round_summary = _build_round_summary(lobby, answers, summary.get("reason", "voted"), votes=votes)
        lobby.save(update_fields=["round_summary", "updated_at"])

    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_continue(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann fortsetzen.")}, status=403)
        if lobby.status == StadtLandFlussLobby.STATUS_FINISHED:
            return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})
        if lobby.status != StadtLandFlussLobby.STATUS_ROUND_SUMMARY:
            return JsonResponse({"ok": False, "error": _("Es gibt gerade keine Auswertung.")}, status=400)
        if lobby.current_round_number >= lobby.rounds_count:
            summary = lobby.round_summary if isinstance(lobby.round_summary, dict) else {}
            summary["finalRanking"] = _final_ranking(lobby)
            summary["isGameOver"] = True
            lobby.round_summary = summary
            lobby.status = StadtLandFlussLobby.STATUS_FINISHED
            lobby.save(update_fields=["round_summary", "status", "updated_at"])
        else:
            _start_next_round(lobby)
    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_restart(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann zurücksetzen.")}, status=403)
        lobby.answers.all().delete()
        lobby.players.update(score=0)
        lobby.status = StadtLandFlussLobby.STATUS_WAITING
        lobby.current_round_number = 0
        lobby.current_letter = ""
        lobby.used_letters = []
        lobby.round_started_at = None
        lobby.round_summary = {}
        lobby.save()
    return JsonResponse({"ok": True, "state": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def stadtlandfluss_leave(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(StadtLandFlussLobby.objects.select_for_update(), code=code.upper())
        player = lobby.players.filter(user=request.user).first()
        if player:
            player.delete()
        if not lobby.players.exists():
            lobby.delete()
            messages.info(request, _("Stadt-Land-Fluss-Lobby wurde gelöscht."))
            return redirect("stadtlandfluss_home")
        if lobby.owner_id == request.user.id:
            next_owner = lobby.players.select_related("user").order_by("joined_at").first()
            lobby.owner = next_owner.user
        if lobby.status == StadtLandFlussLobby.STATUS_PLAYING:
            _score_round(lobby, "player_left")
        lobby.save()
    return redirect("stadtlandfluss_home")


@login_required
@require_POST
def stadtlandfluss_delete(request, code):
    lobby = get_object_or_404(StadtLandFlussLobby, code=code.upper())
    if lobby.owner_id != request.user.id:
        messages.error(request, _("Nur der Host kann diese Lobby löschen."))
        return redirect("stadtlandfluss_lobby", code=lobby.code)
    lobby.delete()
    messages.success(request, _("Stadt-Land-Fluss-Lobby wurde gelöscht."))
    return redirect("stadtlandfluss_home")
