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

from ..models import Friendship, HangmanInvite, HangmanLobby, HangmanPlayer, UserProfile


PLAYER_TIMEOUT = timedelta(seconds=35)
TOTAL_ROUNDS = 4
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


def _players_for_roles(lobby):
    return list(lobby.players.select_related("user").order_by("joined_at", "id"))


def _role_user_ids(lobby, players=None):
    players = players if players is not None else _players_for_roles(lobby)
    if len(players) != 2:
        return None, None
    setter_index = (max(1, int(lobby.round_number or 1)) - 1) % 2
    setter = players[setter_index]
    guesser = players[1 - setter_index]
    return setter.user_id, guesser.user_id


def _round_phase(lobby):
    data = lobby.last_guess if isinstance(lobby.last_guess, dict) else {}
    phase = data.get("phase")
    if phase:
        return phase
    if lobby.status == HangmanLobby.STATUS_WAITING:
        return "waiting"
    if lobby.status == HangmanLobby.STATUS_FINISHED:
        return "game_over"
    if lobby.word:
        return "guessing"
    return "word_setup"


def _public_pending_guess(lobby):
    data = lobby.last_guess if isinstance(lobby.last_guess, dict) else {}
    if not data.get("pending"):
        return {}
    return {
        "player": data.get("player", ""),
        "guess": data.get("guess", ""),
        "guessType": data.get("guessType", "letter"),
    }


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
    lobby.last_guess = {"phase": "waiting"}
    lobby.started_at = None
    lobby.finished_at = None


def _prepare_word_setup(lobby):
    lobby.status = HangmanLobby.STATUS_PLAYING
    lobby.word = ""
    lobby.word_hint = ""
    lobby.guessed_letters = []
    lobby.wrong_letters = []
    lobby.winner = None
    lobby.last_guess = {"phase": "word_setup"}
    lobby.started_at = timezone.now()
    lobby.finished_at = None


def _finish_game(lobby):
    players = list(lobby.players.select_related("user").order_by("-score", "joined_at", "id"))
    winner = None
    if players:
        top_score = players[0].score
        if top_score > 0 and len([player for player in players if player.score == top_score]) == 1:
            winner = players[0].user
    lobby.status = HangmanLobby.STATUS_FINISHED
    lobby.winner = winner
    lobby.finished_at = timezone.now()
    data = dict(lobby.last_guess or {})
    data.update({
        "phase": "game_over",
        "pending": False,
        "gameComplete": True,
        "finalWinnerName": _player_name(winner) if winner else "",
    })
    lobby.last_guess = data


def _serialize_player(player, setter_id=None, guesser_id=None):
    if player.user_id == setter_id:
        role = _("Wortgeber")
    elif player.user_id == guesser_id:
        role = _("Rater")
    else:
        role = _("Spieler")
    return {
        "id": player.id,
        "name": player.display_label,
        "score": player.score,
        "isOwner": player.lobby.owner_id == player.user_id,
        "role": role,
        "isSetter": player.user_id == setter_id,
        "isGuesser": player.user_id == guesser_id,
    }


def _serialize_lobby(lobby, user):
    return _serialize_lobby_manual(lobby, user)


def _serialize_lobby_manual(lobby, user):
    players = _players_for_roles(lobby)
    setter_id, guesser_id = _role_user_ids(lobby, players)
    phase = _round_phase(lobby)
    setter = next((player for player in players if player.user_id == setter_id), None)
    guesser = next((player for player in players if player.user_id == guesser_id), None)
    masked = _masked_word(lobby)
    wrong_values = lobby.wrong_letters if isinstance(lobby.wrong_letters, list) else []
    mistakes = len(wrong_values)
    is_setter = setter_id == user.id
    is_guesser = guesser_id == user.id
    has_two_players = len(players) == 2
    can_start = (
        lobby.status in {HangmanLobby.STATUS_WAITING, HangmanLobby.STATUS_FINISHED}
        and lobby.owner_id == user.id
        and has_two_players
    )
    can_set_word = lobby.status == HangmanLobby.STATUS_PLAYING and phase == "word_setup" and is_setter
    can_guess = lobby.status == HangmanLobby.STATUS_PLAYING and phase == "guessing" and is_guesser
    can_review_guess = lobby.status == HangmanLobby.STATUS_PLAYING and phase == "review" and is_setter
    can_advance_round = (
        lobby.status == HangmanLobby.STATUS_PLAYING
        and phase == "round_over"
        and lobby.owner_id == user.id
        and lobby.round_number < TOTAL_ROUNDS
    )
    can_reset_game = lobby.status == HangmanLobby.STATUS_FINISHED and lobby.owner_id == user.id

    if lobby.status == HangmanLobby.STATUS_WAITING:
        if len(players) < 2:
            message = _("Hangman startet erst mit genau 2 Spielern.")
        else:
            message = _("Bereit. Der Host kann Runde 1 starten.")
    elif phase == "word_setup":
        if is_setter:
            message = _("Gib ein Wort ein. Der andere Spieler sieht es nicht.")
        else:
            message = _("%(user)s gibt gerade ein Wort ein.") % {"user": setter.display_label if setter else _("Der Wortgeber")}
    elif phase == "review":
        pending = _public_pending_guess(lobby)
        if is_setter:
            message = _("Bewerte den Tipp: %(guess)s") % {"guess": pending.get("guess", "")}
        else:
            message = _("Warte auf die Bewertung durch den Wortgeber.")
    elif phase == "round_over":
        message = _("Runde beendet. Der Host kann die naechste Runde starten.")
    elif lobby.status == HangmanLobby.STATUS_FINISHED and lobby.winner_id:
        if lobby.winner_id == user.id:
            message = _("Du hast nach 4 Runden gewonnen.")
        else:
            message = _("%(user)s hat nach 4 Runden gewonnen.") % {"user": _player_name(lobby.winner)}
    elif lobby.status == HangmanLobby.STATUS_FINISHED:
        message = _("Unentschieden nach 4 Runden.")
    elif is_setter:
        message = _("Warte auf den Tipp des Raters.")
    else:
        message = _("Rate einen Buchstaben oder direkt das ganze Wort.")

    visible_word = ""
    if lobby.status == HangmanLobby.STATUS_FINISHED or phase in {"round_over", "game_over"}:
        visible_word = lobby.word

    return {
        "id": lobby.id,
        "name": lobby.name,
        "code": lobby.code,
        "status": lobby.status,
        "statusLabel": lobby.get_status_display(),
        "roundNumber": lobby.round_number,
        "maxRounds": TOTAL_ROUNDS,
        "roundPhase": phase,
        "maskedWord": masked,
        "wordLength": len([char for char in lobby.word if char not in {" ", "-"}]),
        "hint": lobby.word_hint,
        "guessedLetters": lobby.normalized_guessed_letters,
        "wrongLetters": lobby.normalized_wrong_letters + ([_("Wort")] * len([value for value in wrong_values if str(value).startswith("?")])),
        "mistakes": mistakes,
        "maxMistakes": lobby.max_mistakes,
        "lastGuess": lobby.last_guess or {},
        "word": visible_word,
        "secretWord": lobby.word if is_setter and lobby.status == HangmanLobby.STATUS_PLAYING else "",
        "winnerName": _player_name(lobby.winner),
        "players": [_serialize_player(player, setter_id, guesser_id) for player in players],
        "isOwner": lobby.owner_id == user.id,
        "isSetter": is_setter,
        "isGuesser": is_guesser,
        "setterName": setter.display_label if setter else "",
        "guesserName": guesser.display_label if guesser else "",
        "canStart": can_start,
        "canSetWord": can_set_word,
        "canGuess": can_guess,
        "canReviewGuess": can_review_guess,
        "canAdvanceRound": can_advance_round,
        "canResetGame": can_reset_game,
        "pendingGuess": _public_pending_guess(lobby),
        "message": message,
        "updatedAt": timezone.localtime(lobby.updated_at).strftime("%d.%m.%Y %H:%M"),
    }

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
    if len(current_ids) >= 2:
        return []
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
    _cleanup_stale_lobbies()
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
    _cleanup_stale_lobbies()
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

    if not lobby.players.filter(user=request.user).exists() and lobby.players.count() >= 2:
        messages.error(request, _("Hangman geht nur zu zweit. Dieser Raum ist schon voll."))
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
    if lobby.players.count() >= 2:
        messages.error(request, _("Hangman geht nur zu zweit. Der Raum ist schon voll."))
        return redirect("hangman_lobby", code=lobby.code)
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
        if lobby.players.count() != 2:
            return JsonResponse({"ok": False, "error": _("Hangman startet nur mit genau 2 Spielern.")}, status=400)
        if lobby.status == HangmanLobby.STATUS_FINISHED:
            lobby.players.update(score=0)
            lobby.round_number = 1
        elif lobby.status != HangmanLobby.STATUS_WAITING:
            return JsonResponse({"ok": False, "error": _("Diese Runde laeuft schon.")}, status=400)
        _prepare_word_setup(lobby)
        lobby.save()
    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_word_api(request, code):
    word = _normalize_word(request.POST.get("word", ""))
    hint = (request.POST.get("hint", "") or "").strip()[:120]
    if len(word.replace(" ", "").replace("-", "")) < 3:
        return JsonResponse({"ok": False, "error": _("Bitte gib ein Wort mit mindestens 3 Buchstaben ein.")}, status=400)

    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(), code=code.upper())
        player = lobby.players.select_for_update().filter(user=request.user).first()
        if not player:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Raum.")}, status=403)
        player.last_seen = timezone.now()
        player.save(update_fields=["last_seen"])
        setter_id, _guesser_id = _role_user_ids(lobby)
        if setter_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Wortgeber kann das Wort setzen.")}, status=403)
        if lobby.status != HangmanLobby.STATUS_PLAYING or _round_phase(lobby) != "word_setup":
            return JsonResponse({"ok": False, "error": _("Gerade kann kein Wort gesetzt werden.")}, status=400)

        lobby.word = word
        lobby.word_hint = hint
        lobby.guessed_letters = []
        lobby.wrong_letters = []
        lobby.last_guess = {"phase": "guessing"}
        lobby.save()

    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_guess_api(request, code):
    guess = _normalize_word(request.POST.get("guess", ""))
    if not guess:
        return JsonResponse({"ok": False, "error": _("Bitte gib einen Buchstaben oder ein Wort ein.")}, status=400)

    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(of=("self",)).select_related("winner"), code=code.upper())
        player = lobby.players.select_for_update().filter(user=request.user).first()
        if not player:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Raum.")}, status=403)
        player.last_seen = timezone.now()
        player.save(update_fields=["last_seen"])
        if lobby.status != HangmanLobby.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Die Runde läuft gerade nicht.")}, status=400)

        if _round_phase(lobby) != "guessing":
            return JsonResponse({"ok": False, "error": _("Warte erst auf den Wortgeber.")}, status=400)
        _setter_id, guesser_id = _role_user_ids(lobby)
        if guesser_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Rater kann tippen.")}, status=403)
        if not lobby.word:
            return JsonResponse({"ok": False, "error": _("Es wurde noch kein Wort gesetzt.")}, status=400)

        letters = set(lobby.normalized_guessed_letters)
        wrong_letter_set = set(lobby.normalized_wrong_letters)
        compact_guess = guess.replace(" ", "").replace("-", "")
        if len(compact_guess) == 1:
            guess = _normalize_letter(guess)
            guess_type = "letter"
            if guess in letters or guess in wrong_letter_set:
                return JsonResponse({"ok": False, "error": _("Dieser Buchstabe wurde schon geraten.")}, status=400)
        else:
            guess_type = "word"

        lobby.last_guess = {
            "phase": "review",
            "pending": True,
            "player": player.display_label,
            "playerId": request.user.id,
            "guess": guess,
            "guessType": guess_type,
            "correct": None,
            "points": 0,
        }
        lobby.save()
        return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})

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
def hangman_review_api(request, code):
    result = (request.POST.get("result") or "").strip().lower()
    if result not in {"correct", "wrong"}:
        return JsonResponse({"ok": False, "error": _("Bitte waehle richtig oder falsch.")}, status=400)
    mark_correct = result == "correct"

    with transaction.atomic():
        lobby = get_object_or_404(
            HangmanLobby.objects.select_for_update(of=("self",)).select_related("winner"),
            code=code.upper(),
        )
        player = lobby.players.select_for_update().filter(user=request.user).first()
        if not player:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Raum.")}, status=403)
        player.last_seen = timezone.now()
        player.save(update_fields=["last_seen"])
        setter_id, guesser_id = _role_user_ids(lobby)
        if setter_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Wortgeber kann den Tipp bewerten.")}, status=403)
        pending = dict(lobby.last_guess or {})
        if lobby.status != HangmanLobby.STATUS_PLAYING or _round_phase(lobby) != "review" or not pending.get("pending"):
            return JsonResponse({"ok": False, "error": _("Es wartet kein Tipp auf Bewertung.")}, status=400)

        guess = _normalize_word(pending.get("guess", ""))
        guess_type = pending.get("guessType") or "letter"
        letters = set(lobby.normalized_guessed_letters)
        wrong_values = list(lobby.wrong_letters if isinstance(lobby.wrong_letters, list) else [])
        points = 0
        round_winner_id = None
        round_winner_name = ""

        guesser_player = lobby.players.select_for_update().filter(user_id=guesser_id).first()
        setter_player = lobby.players.select_for_update().filter(user_id=setter_id).first()

        if guess_type == "letter":
            letter = _normalize_letter(guess)
            occurrences = lobby.word.count(letter)
            if mark_correct and not occurrences:
                return JsonResponse({"ok": False, "error": _("Der Buchstabe kommt im Wort nicht vor.")}, status=400)
            if not mark_correct and occurrences:
                return JsonResponse({"ok": False, "error": _("Der Buchstabe ist im Wort. Markiere ihn als richtig.")}, status=400)
            if mark_correct:
                letters.add(letter)
                points = occurrences * 10
                if guesser_player and points:
                    guesser_player.score += points
                    guesser_player.save(update_fields=["score", "last_seen"])
            else:
                wrong_values.append(letter)
        else:
            is_word_match = guess == lobby.word
            if mark_correct and not is_word_match:
                return JsonResponse({"ok": False, "error": _("Das ist nicht das gesuchte Wort.")}, status=400)
            if not mark_correct and is_word_match:
                return JsonResponse({"ok": False, "error": _("Das ist das Wort. Markiere es als richtig.")}, status=400)
            if mark_correct:
                letters.update([char for char in lobby.word if char in GERMAN_LETTERS])
                points = 50
                if guesser_player:
                    guesser_player.score += points
                    guesser_player.save(update_fields=["score", "last_seen"])
            else:
                wrong_values.append(f"?{len(wrong_values) + 1}")

        lobby.guessed_letters = sorted(letters)
        lobby.wrong_letters = wrong_values

        if _is_word_solved(lobby):
            round_winner_id = guesser_id
            round_winner_name = guesser_player.display_label if guesser_player else ""
            if guesser_player:
                guesser_player.score += 50
                guesser_player.save(update_fields=["score", "last_seen"])
                points += 50
        elif len(wrong_values) >= lobby.max_mistakes:
            round_winner_id = setter_id
            round_winner_name = setter_player.display_label if setter_player else ""
            if setter_player:
                setter_player.score += 50
                setter_player.save(update_fields=["score", "last_seen"])

        next_phase = "guessing"
        if round_winner_id:
            next_phase = "round_over"

        lobby.last_guess = {
            "phase": next_phase,
            "pending": False,
            "player": pending.get("player", ""),
            "playerId": pending.get("playerId"),
            "guess": guess,
            "guessType": guess_type,
            "correct": mark_correct,
            "points": points,
            "roundWinnerId": round_winner_id,
            "roundWinnerName": round_winner_name,
        }

        if round_winner_id and lobby.round_number >= TOTAL_ROUNDS:
            _finish_game(lobby)

        lobby.save()

    return JsonResponse({"ok": True, "game": _serialize_lobby(lobby, request.user)})


@login_required
@require_POST
def hangman_reset_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(HangmanLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann eine neue Runde vorbereiten.")}, status=403)
        if lobby.players.count() != 2:
            return JsonResponse({"ok": False, "error": _("Hangman braucht genau 2 Spieler.")}, status=400)
        phase = _round_phase(lobby)
        if lobby.status == HangmanLobby.STATUS_FINISHED:
            lobby.round_number = 1
            lobby.players.update(score=0)
            _reset_to_waiting(lobby)
        elif phase == "round_over" and lobby.round_number < TOTAL_ROUNDS:
            lobby.round_number += 1
            _prepare_word_setup(lobby)
        else:
            lobby.round_number = 1
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
