import random
import string
import unicodedata
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

from .models import Friendship, HangmanInvite, HangmanLobby, HangmanPlayer, UserProfile


PLAYER_TIMEOUT = timedelta(seconds=35)
DEFAULT_WORDS = [
    ("PYTHON", "Programmiersprache"),
    ("DJANGO", "Webframework"),
    ("JAVASCRIPT", "Frontend"),
    ("DATENBANK", "IT"),
    ("SERVER", "Hosting"),
    ("KONSOLE", "Gaming"),
    ("SCHLUESSEL", "Sicherheit"),
    ("FIREWALL", "Netzwerk"),
    ("ALGORITHMUS", "Informatik"),
    ("VARIABLE", "Programmierung"),
    ("HANGMAN", "Spiel"),
    ("MEHRSPIELER", "MyTools"),
]
GERMAN_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ")


def _generate_lobby_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not HangmanLobby.objects.filter(code=code).exists():
            return code


def _player_name(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def _normalize_word(value):
    value = unicodedata.normalize("NFKC", value or "").strip().upper()
    replacements = {"ẞ": "SS", "ß": "SS"}
    for source, target in replacements.items():
        value = value.replace(source, target)
    return "".join(char for char in value if char in GERMAN_LETTERS or char in {" ", "-"})[:80]


def _normalize_letter(value):
    value = _normalize_word(value).replace(" ", "").replace("-", "")
    return value[:1]


def _custom_word_pool(text):
    words = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        if "|" in raw:
            word, hint = raw.split("|", 1)
        else:
            word, hint = raw, "Eigene Wörter"
        normalized = _normalize_word(word)
        if normalized and len(normalized.replace(" ", "").replace("-", "")) >= 3:
            words.append((normalized, hint.strip()[:120]))
    return words


def _pick_word(lobby):
    pool = _custom_word_pool(lobby.custom_words) or DEFAULT_WORDS
    return random.choice(pool)


def _masked_word(lobby):
    guessed = set(lobby.normalized_guessed_letters)
    result = []
    for char in lobby.word:
        if char in {" ", "-"}:
            result.append(char)
        elif char in guessed:
            result.append(char)
        else:
            result.append("_")
    return result


def _is_word_solved(lobby):
    masked = _masked_word(lobby)
    return "_" not in masked and bool(lobby.word)


def _mark_player_seen(lobby, user):
    HangmanPlayer.objects.filter(lobby=lobby, user=user).update(last_seen=timezone.now())


def _cleanup_stale_lobbies(keep_user_id=None):
    stale_before = timezone.now() - PLAYER_TIMEOUT
    for lobby in HangmanLobby.objects.prefetch_related("players"):
        stale_players = lobby.players.filter(last_seen__lt=stale_before)
        if keep_user_id:
            stale_players = stale_players.exclude(user_id=keep_user_id)
        if stale_players.exists():
            stale_players.delete()
        players = list(lobby.players.select_related("user").order_by("joined_at"))
        if not players:
            lobby.delete()
            continue
        if lobby.owner_id not in [player.user_id for player in players]:
            lobby.owner = players[0].user
            lobby.save(update_fields=["owner", "updated_at"])


def _join_lobby(lobby, user):
    player, _created = HangmanPlayer.objects.get_or_create(
        lobby=lobby,
        user=user,
        defaults={"display_name": _player_name(user)[:40]},
    )
    player.last_seen = timezone.now()
    if not player.display_name:
        player.display_name = _player_name(user)[:40]
    player.save(update_fields=["last_seen", "display_name"])
    return player


def _reset_to_waiting(lobby):
    lobby.status = HangmanLobby.STATUS_WAITING
    lobby.word = ""
    lobby.word_hint = ""
    lobby.guessed_letters = []
    lobby.wrong_letters = []
    lobby.winner = None
    lobby.last_guess = {}
    lobby.started_at = None
    lobby.finished_at = None


def _start_round(lobby):
    word, hint = _pick_word(lobby)
    lobby.word = word
    lobby.word_hint = hint
    lobby.status = HangmanLobby.STATUS_PLAYING
    lobby.guessed_letters = []
    lobby.wrong_letters = []
    lobby.winner = None
    lobby.last_guess = {}
    lobby.started_at = timezone.now()
    lobby.finished_at = None


def _serialize_player(player):
    return {
        "id": player.id,
        "name": player.display_label,
        "score": player.score,
        "isOwner": player.lobby.owner_id == player.user_id,
    }


def _serialize_lobby(lobby, user):
    players = list(lobby.players.select_related("user").order_by("-score", "joined_at"))
    masked = _masked_word(lobby)
    wrong_values = lobby.wrong_letters if isinstance(lobby.wrong_letters, list) else []
    mistakes = len(wrong_values)
    is_player = any(player.user_id == user.id for player in players)
    can_guess = lobby.status == HangmanLobby.STATUS_PLAYING and is_player

    if lobby.status == HangmanLobby.STATUS_WAITING:
        message = _("Warte auf den Start durch den Host.")
    elif lobby.status == HangmanLobby.STATUS_FINISHED and lobby.winner_id:
        if lobby.winner_id == user.id:
            message = _("Du hast das Wort gelöst.")
        else:
            message = _("%(user)s hat das Wort gelöst.") % {"user": _player_name(lobby.winner)}
    elif lobby.status == HangmanLobby.STATUS_FINISHED:
        message = _("Leider verloren. Das Wort wurde nicht erraten.")
    else:
        message = _("Rate einen Buchstaben oder direkt das ganze Wort.")

    return {
        "id": lobby.id,
        "name": lobby.name,
        "code": lobby.code,
        "status": lobby.status,
        "statusLabel": lobby.get_status_display(),
        "roundNumber": lobby.round_number,
        "maskedWord": masked,
        "wordLength": len([char for char in lobby.word if char not in {" ", "-"}]),
        "hint": lobby.word_hint,
        "guessedLetters": lobby.normalized_guessed_letters,
        "wrongLetters": lobby.normalized_wrong_letters + ([_("Wort")] * len([value for value in wrong_values if str(value).startswith("?")])),
        "mistakes": mistakes,
        "maxMistakes": lobby.max_mistakes,
        "lastGuess": lobby.last_guess or {},
        "word": lobby.word if lobby.status == HangmanLobby.STATUS_FINISHED else "",
        "winnerName": _player_name(lobby.winner),
        "players": [_serialize_player(player) for player in players],
        "isOwner": lobby.owner_id == user.id,
        "canGuess": can_guess,
        "message": message,
        "updatedAt": timezone.localtime(lobby.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


def _home_lobbies_for_user(user):
    return (
        HangmanLobby.objects
        .filter(Q(owner=user) | Q(players__user=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _home_invites_for_user(user):
    return (
        HangmanInvite.objects
        .select_related("lobby", "from_user")
        .filter(to_user=user, status=HangmanInvite.STATUS_PENDING)
        .order_by("-created_at")
    )


def _serialize_home_lobby(lobby):
    return {
        "id": lobby.id,
        "name": lobby.name,
        "code": lobby.code,
        "statusLabel": lobby.get_status_display(),
        "roundNumber": lobby.round_number,
        "url": reverse("hangman_lobby", args=[lobby.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.lobby.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("hangman_invite_response", args=[invite.id]),
        "declineUrl": reverse("hangman_invite_response", args=[invite.id]),
    }


def _friend_invite_rows(lobby, user):
    current_ids = list(lobby.players.values_list("user_id", flat=True))
    friends = (
        User.objects
        .filter(id__in=Friendship.friend_ids_for_user(user), is_active=True)
        .exclude(id__in=current_ids)
        .order_by("username")
    )
    UserProfile.objects.bulk_create(
        [UserProfile(user=friend) for friend in friends if not hasattr(friend, "profile")],
        ignore_conflicts=True,
    )
    pending_ids = set(lobby.invites.filter(status=HangmanInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted_ids = set(lobby.invites.filter(status=HangmanInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    return [
        {"user": friend, "is_invited": friend.id in pending_ids, "was_invited": friend.id in accepted_ids}
        for friend in friends
    ]


@login_required
def hangman_home(request):
    _cleanup_stale_lobbies(keep_user_id=request.user.id)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            max_mistakes = request.POST.get("max_mistakes") or 8
            try:
                max_mistakes = min(12, max(5, int(max_mistakes)))
            except (TypeError, ValueError):
                max_mistakes = 8
            lobby = HangmanLobby.objects.create(
                owner=request.user,
                name=(request.POST.get("name", "").strip() or _("Hangman"))[:80],
                code=_generate_lobby_code(),
                max_mistakes=max_mistakes,
                custom_words=(request.POST.get("custom_words", "") or "")[:2500],
            )
            _join_lobby(lobby, request.user)
            return redirect("hangman_lobby", code=lobby.code)
        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("hangman_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/hangman_home.html", {
        "my_lobbies": _home_lobbies_for_user(request.user),
        "invites": _home_invites_for_user(request.user),
    })


@login_required
@require_GET
def hangman_home_state_api(request):
    _cleanup_stale_lobbies(keep_user_id=request.user.id)
    return JsonResponse({
        "ok": True,
        "games": [_serialize_home_lobby(lobby) for lobby in _home_lobbies_for_user(request.user)],
        "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)],
    })


@login_required
def hangman_lobby(request, code):
    lobby = HangmanLobby.objects.select_related("owner", "winner").filter(code=code.upper()).first()
    if not lobby:
        messages.warning(request, _("Diese Hangman-Lobby existiert nicht mehr."))
        return redirect("hangman_home")

    _cleanup_stale_lobbies(keep_user_id=request.user.id)
    lobby = HangmanLobby.objects.select_related("owner", "winner").filter(code=code.upper()).first()
    if not lobby:
        messages.warning(request, _("Diese Hangman-Lobby war leer und wurde gelöscht."))
        return redirect("hangman_home")

    _join_lobby(lobby, request.user)
    return render(request, "app/hangman_lobby.html", {
        "lobby": lobby,
        "friend_invite_rows": _friend_invite_rows(lobby, request.user),
    })


@login_required
@require_POST
def hangman_invite_friend(request, code):
    lobby = get_object_or_404(HangmanLobby, code=code.upper())
    if not lobby.players.filter(user=request.user).exists() and lobby.owner_id != request.user.id:
        messages.error(request, _("Du bist nicht in diesem Raum."))
        return redirect("hangman_home")
    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("hangman_lobby", code=lobby.code)
    if lobby.players.filter(user=friend).exists():
        messages.info(request, _("Dieser Freund ist schon im Raum."))
        return redirect("hangman_lobby", code=lobby.code)
    HangmanInvite.objects.update_or_create(
        lobby=lobby,
        to_user=friend,
        defaults={"from_user": request.user, "status": HangmanInvite.STATUS_PENDING},
    )
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("hangman_lobby", code=lobby.code)


@login_required
@require_POST
def hangman_invite_response(request, invite_id):
    invite = get_object_or_404(HangmanInvite.objects.select_related("lobby"), id=invite_id, to_user=request.user)
    if request.POST.get("action") == "accept":
        invite.status = HangmanInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("hangman_lobby", code=invite.lobby.code)
    invite.status = HangmanInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("hangman_home")


@login_required
@require_GET
def hangman_state_api(request, code):
    lobby = HangmanLobby.objects.select_related("owner", "winner").filter(code=code.upper()).first()
    if not lobby:
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Hangman-Raum wurde gelöscht."), "redirectUrl": reverse("hangman_home")}, status=410)
    _mark_player_seen(lobby, request.user)
    _cleanup_stale_lobbies(keep_user_id=request.user.id)
    lobby = HangmanLobby.objects.select_related("owner", "winner").filter(code=code.upper()).first()
    if not lobby:
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Hangman-Raum wurde gelöscht."), "redirectUrl": reverse("hangman_home")}, status=410)
    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_start_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann die Runde starten.")}, status=403)
        if not lobby.players.exists():
            _join_lobby(lobby, request.user)
        _start_round(lobby)
        lobby.save()
    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_guess_api(request, code):
    guess = _normalize_word(request.POST.get("guess", ""))
    if not guess:
        return JsonResponse({"ok": False, "error": _("Bitte gib einen Buchstaben oder ein Wort ein.")}, status=400)

    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update().select_related("winner"), code=code.upper())
        player = lobby.players.select_for_update().filter(user=request.user).first()
        if not player:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Raum.")}, status=403)
        player.last_seen = timezone.now()
        player.save(update_fields=["last_seen"])
        if lobby.status != HangmanLobby.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Die Runde läuft gerade nicht.")}, status=400)

        letters = set(lobby.normalized_guessed_letters)
        wrong_values = list(lobby.wrong_letters if isinstance(lobby.wrong_letters, list) else [])
        wrong_letter_set = set(lobby.normalized_wrong_letters)
        clean_word = lobby.word
        was_correct = False
        points = 0

        if len(guess.replace(" ", "").replace("-", "")) == 1:
            letter = _normalize_letter(guess)
            if letter in letters or letter in wrong_letter_set:
                return JsonResponse({"ok": False, "error": _("Dieser Buchstabe wurde schon geraten.")}, status=400)
            if letter in clean_word:
                letters.add(letter)
                was_correct = True
                points = clean_word.count(letter) * 10
            else:
                wrong_values.append(letter)
                wrong_letter_set.add(letter)
        else:
            if guess == clean_word:
                was_correct = True
                points = 50
                letters.update([char for char in clean_word if char in GERMAN_LETTERS])
            else:
                wrong_values.append(f"?{len(wrong_values) + 1}")

        lobby.guessed_letters = sorted(letters)
        lobby.wrong_letters = wrong_values
        if points:
            player.score += points
            player.save(update_fields=["score", "last_seen"])

        if _is_word_solved(lobby):
            lobby.status = HangmanLobby.STATUS_FINISHED
            lobby.winner = request.user
            lobby.finished_at = timezone.now()
        elif len(wrong_values) >= lobby.max_mistakes:
            lobby.status = HangmanLobby.STATUS_FINISHED
            lobby.winner = None
            lobby.finished_at = timezone.now()

        lobby.last_guess = {
            "player": player.display_label,
            "guess": guess,
            "correct": was_correct,
            "points": points,
        }
        lobby.save()

    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_reset_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann eine neue Runde vorbereiten.")}, status=403)
        lobby.round_number += 1
        lobby.players.update(score=0)
        _reset_to_waiting(lobby)
        lobby.save()
    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_leave(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(), code=code.upper())
        lobby.players.filter(user=request.user).delete()
        players = list(lobby.players.select_related("user").order_by("joined_at"))
        if not players:
            lobby.delete()
            messages.info(request, _("Hangman-Raum wurde gelöscht."))
            return redirect("hangman_home")
        if lobby.owner_id == request.user.id:
            lobby.owner = players[0].user
            lobby.save(update_fields=["owner", "updated_at"])
    return redirect("hangman_home")


@login_required
@require_POST
def hangman_delete(request, code):
    lobby = get_object_or_404(HangmanLobby, code=code.upper())
    if lobby.owner_id != request.user.id:
        messages.error(request, _("Du kannst diesen Raum nicht löschen."))
        return redirect("hangman_home")
    lobby.delete()
    messages.success(request, _("Hangman-Raum wurde gelöscht."))
    return redirect("hangman_home")
