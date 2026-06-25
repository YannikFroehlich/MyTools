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

from ..models import Friendship, UnoGame, UnoInvite, UnoPlayer, UserProfile


COLORS = ["red", "yellow", "green", "blue"]
COLOR_LABELS = {
    "red": _("Rot"),
    "yellow": _("Gelb"),
    "green": _("Gr\u00fcn"),
    "blue": _("Blau"),
    "wild": _("Joker"),
}
VALUE_LABELS = {
    "skip": _("Aussetzen"),
    "reverse": _("Richtungswechsel"),
    "draw2": "+2",
    "wild": _("Farbwahl"),
    "wild4": "+4",
}



UNO_PLAYER_TIMEOUT = timedelta(seconds=30)

def _generate_game_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not UnoGame.objects.filter(code=code).exists():
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


def _card(card_id, color, value):
    card_type = "number" if str(value).isdigit() else "action"
    if color == "wild":
        card_type = "wild"
    label = str(value) if card_type == "number" else VALUE_LABELS.get(value, value)
    return {"id": card_id, "color": color, "value": str(value), "type": card_type, "label": str(label)}


def _build_deck():
    cards = []
    for color in COLORS:
        cards.append(_card(f"{color}-0-0", color, "0"))
        for number in range(1, 10):
            cards.append(_card(f"{color}-{number}-a", color, number))
            cards.append(_card(f"{color}-{number}-b", color, number))
        for value in ["skip", "reverse", "draw2"]:
            cards.append(_card(f"{color}-{value}-a", color, value))
            cards.append(_card(f"{color}-{value}-b", color, value))
    for index in range(4):
        cards.append(_card(f"wild-{index}", "wild", "wild"))
        cards.append(_card(f"wild4-{index}", "wild", "wild4"))
    random.shuffle(cards)
    return cards


def _draw_cards(game, hands, user_id, amount):
    deck = list(game.deck or [])
    discard = list(game.discard_pile or [])
    drawn = []
    for _ in range(amount):
        if not deck and len(discard) > 1:
            top = discard[-1]
            deck = discard[:-1]
            random.shuffle(deck)
            discard = [top]
        if not deck:
            break
        drawn.append(deck.pop())
    hands.setdefault(str(user_id), []).extend(drawn)
    game.deck = deck
    game.discard_pile = discard
    return drawn


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


def _next_index(players, current_index, direction, steps=1):
    if not players:
        return 0
    return (current_index + (direction * steps)) % len(players)


def _current_player(game, players=None):
    players = players or _ordered_players(game)
    if not players:
        return None
    return players[game.current_player_index % len(players)]


def _card_sort_key(card):
    return (COLORS.index(card["color"]) if card["color"] in COLORS else 9, card["value"], card["id"])


def _is_stack_card(card, pending_draw):
    if pending_draw <= 0:
        return True
    return card["value"] in {"draw2", "wild4"}


def _is_playable(card, top_card, current_color, pending_draw=0):
    if not top_card:
        return True
    if pending_draw and not _is_stack_card(card, pending_draw):
        return False
    if card["color"] == "wild":
        return True
    return card["color"] == current_color or card["value"] == top_card["value"]


def _has_playable(hand, game):
    top_card = (game.discard_pile or [{}])[-1]
    return any(_is_playable(card, top_card, game.current_color, game.pending_draw) for card in hand)


def _start_round(game):
    players = _ordered_players(game)
    deck = _build_deck()
    hands = {str(player.user_id): [] for player in players}
    for deal_round in range(7):
        for player in players:
            hands[str(player.user_id)].append(deck.pop())

    first = deck.pop()
    attempts = 0
    while first["color"] == "wild" and attempts < 40:
        deck.insert(0, first)
        random.shuffle(deck)
        first = deck.pop()
        attempts += 1

    game.deck = deck
    game.discard_pile = [first]
    game.hands = hands
    game.current_color = first["color"] if first["color"] in COLORS else random.choice(COLORS)
    game.current_player_index = 0
    game.direction = 1
    game.pending_draw = 0
    game.has_drawn_this_turn = False
    game.uno_calls = {}
    game.winner_user_id = None
    game.action_log = [_("Runde gestartet.")]
    game.status = UnoGame.STATUS_PLAYING
    _apply_card_effect(game, first, None, starting=True)


def _append_log(game, text):
    log = list(game.action_log or [])
    log.append(str(text))
    game.action_log = log[-8:]


def _apply_card_effect(game, card, player, chosen_color="", target_user_id=None, starting=False):
    players = _ordered_players(game)
    if card["color"] == "wild":
        game.current_color = chosen_color if chosen_color in COLORS else random.choice(COLORS)
    else:
        game.current_color = card["color"]

    steps = 1
    if card["value"] == "reverse":
        game.direction *= -1
        if len(players) == 2:
            steps = 2
    elif card["value"] == "skip":
        steps = 2
    elif card["value"] == "draw2":
        steps = _apply_draw_penalty(game, players, 2, starting=starting)
    elif card["value"] == "wild4":
        steps = _apply_draw_penalty(game, players, 4, starting=starting)
    elif card["value"] == "0" and game.seven_zero and len(players) > 1 and not starting:
        _rotate_hands(game, players)
    elif card["value"] == "7" and game.seven_zero and player and target_user_id:
        _swap_hands(game, player.user_id, target_user_id)

    if not starting:
        game.current_player_index = _next_index(players, game.current_player_index, game.direction, steps)
    elif card["value"] in {"skip", "reverse", "draw2", "wild4"}:
        game.current_player_index = _next_index(players, game.current_player_index, game.direction, 1)


def _apply_draw_penalty(game, players, amount, starting=False):
    if not players:
        return 1
    target_index = game.current_player_index if starting else _next_index(players, game.current_player_index, game.direction)
    target = players[target_index]
    hands = dict(game.hands or {})
    drawn = _draw_cards(game, hands, target.user_id, amount)
    game.hands = hands
    game.pending_draw = 0
    _append_log(
        game,
        _("%(name)s zieht automatisch %(count)s Karte(n).") % {
            "name": target.display_label,
            "count": len(drawn),
        },
    )
    return 2


def _rotate_hands(game, players):
    hands = dict(game.hands or {})
    if len(players) < 2:
        return
    user_ids = [str(player.user_id) for player in players]
    previous = {user_id: list(hands.get(user_id, [])) for user_id in user_ids}
    for index, user_id in enumerate(user_ids):
        source_id = user_ids[(index - game.direction) % len(user_ids)]
        hands[user_id] = previous[source_id]
    game.hands = hands
    _append_log(game, _("0 gespielt: Alle H\u00e4nde wurden rotiert."))


def _swap_hands(game, first_user_id, second_user_id):
    hands = dict(game.hands or {})
    first_key = str(first_user_id)
    second_key = str(second_user_id)
    if second_key not in hands or first_key == second_key:
        return
    hands[first_key], hands[second_key] = hands.get(second_key, []), hands.get(first_key, [])
    game.hands = hands
    _append_log(game, _("7 gespielt: H\u00e4nde wurden getauscht."))


def _seat_for_new_player(game):
    taken = set(game.players.values_list("seat", flat=True))
    for seat in range(game.max_players):
        if seat not in taken:
            return seat
    return None


def _join_game(game, user):
    player = game.player_for_user(user)
    if player:
        return player
    if game.status != UnoGame.STATUS_WAITING or game.is_full:
        return None
    seat = _seat_for_new_player(game)
    if seat is None:
        return None
    return UnoPlayer.objects.create(game=game, user=user, seat=seat)


def _home_games_for_user(user):
    return (
        UnoGame.objects
        .filter(Q(owner=user) | Q(players__user=user))
        .distinct()
        .order_by("-updated_at")[:12]
    )


def _cleanup_stale_games():
    for game in UnoGame.objects.prefetch_related("players", "players__user").all():
        _cleanup_game_players(game)
    UnoGame.objects.filter(players__isnull=True).delete()


def _delete_empty_games():
    _cleanup_stale_games()


def _remove_player_from_game(game, user):
    removed_count, _ = game.players.filter(user=user).delete()
    if removed_count:
        hands = dict(game.hands or {})
        hands.pop(str(user.id), None)
        game.hands = hands

        uno_calls = dict(game.uno_calls or {})
        uno_calls.pop(str(user.id), None)
        game.uno_calls = uno_calls

        if game.winner_user_id == user.id:
            game.winner_user_id = None
    return removed_count


def _reset_to_waiting_lobby(game):
    game.status = UnoGame.STATUS_WAITING
    game.deck = []
    game.discard_pile = []
    game.hands = {}
    game.current_color = ""
    game.current_player_index = 0
    game.direction = 1
    game.pending_draw = 0
    game.has_drawn_this_turn = False
    game.uno_calls = {}
    game.winner_user_id = None
    game.last_move_at = None


def _cleanup_game_players(game, keep_user_id=None):
    stale_before = timezone.now() - UNO_PLAYER_TIMEOUT
    stale_players = [
        player
        for player in _ordered_players(game)
        if player.user_id != keep_user_id and player.last_seen < stale_before
    ]
    if not stale_players:
        return False

    removed_owner = any(player.user_id == game.owner_id for player in stale_players)
    for player in stale_players:
        _remove_player_from_game(game, player.user)

    players_after = _ordered_players(game)
    if not players_after:
        game.delete()
        return True

    if removed_owner or game.owner_id not in [player.user_id for player in players_after]:
        game.owner = players_after[0].user

    if game.status == UnoGame.STATUS_PLAYING:
        if len(players_after) >= 2:
            game.current_player_index = game.current_player_index % len(players_after)
            game.pending_draw = 0
            game.has_drawn_this_turn = False
            _append_log(game, _("Inaktive Spieler wurden automatisch aus dem Raum entfernt."))
        else:
            _reset_to_waiting_lobby(game)
            _append_log(game, _("Inaktive Spieler wurden entfernt. Warte auf weitere Spieler."))
    else:
        game.current_player_index = game.current_player_index % len(players_after)

    game.save()
    return False

def _home_invites_for_user(user):
    return (
        UnoInvite.objects
        .select_related("game", "from_user")
        .filter(to_user=user, status=UnoInvite.STATUS_PENDING)
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
        "url": reverse("uno_lobby", args=[game.code]),
    }


def _serialize_home_invite(invite):
    return {
        "id": invite.id,
        "gameName": invite.game.name,
        "fromUser": invite.from_user.username,
        "acceptUrl": reverse("uno_invite_response", args=[invite.id]),
        "declineUrl": reverse("uno_invite_response", args=[invite.id]),
    }


def _friend_invite_rows(game, user):
    if game.is_full or game.status != UnoGame.STATUS_WAITING:
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
    invited_friend_ids = set(game.invites.filter(status=UnoInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted_invite_ids = set(game.invites.filter(status=UnoInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    return [
        {"user": friend, "is_invited": friend.id in invited_friend_ids, "was_invited": friend.id in accepted_invite_ids}
        for friend in friends
    ]


def _serialize_game(game, user):
    players = _ordered_players(game)
    player = next((row for row in players if row.user_id == user.id), None)
    current = _current_player(game, players)
    winner = next((row for row in players if row.user_id == game.winner_user_id), None)
    hands = game.hands if isinstance(game.hands, dict) else {}
    own_hand = sorted(hands.get(str(user.id), []), key=_card_sort_key) if player else []
    top_card = (game.discard_pile or [{}])[-1] if game.discard_pile else {}
    can_act = game.status == UnoGame.STATUS_PLAYING and current and current.user_id == user.id
    playable_ids = [card["id"] for card in own_hand if can_act and _is_playable(card, top_card, game.current_color, game.pending_draw)]

    can_call_uno = bool(
        player
        and can_act
        and len(own_hand) == 2
        and playable_ids
        and not (game.uno_calls or {}).get(str(user.id))
    )

    if game.status == UnoGame.STATUS_WAITING:
        message = _("Warte auf Spieler. Der Host startet ab 2 Spielern.")
    elif game.status == UnoGame.STATUS_FINISHED:
        message = _("Gewonnen: %(name)s") % {"name": winner.display_label if winner else _("Unbekannt")}
    elif can_call_uno:
        message = _("Sag Uno, bevor du deine vorletzte Karte legst.")
    elif can_act and game.pending_draw:
        message = _("Du musst +%(count)s ziehen oder stapeln.") % {"count": game.pending_draw}
    elif can_act:
        message = _("Du bist am Zug.")
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
        "currentColor": game.current_color,
        "currentColorLabel": str(COLOR_LABELS.get(game.current_color, game.current_color)),
        "direction": game.direction,
        "pendingDraw": game.pending_draw,
        "hasDrawnThisTurn": game.has_drawn_this_turn,
        "deckCount": len(game.deck or []),
        "discardCount": len(game.discard_pile or []),
        "topCard": top_card,
        "hand": own_hand,
        "playableIds": playable_ids,
        "canAct": can_act,
        "canStart": game.owner_id == user.id and game.status == UnoGame.STATUS_WAITING and len(players) >= 2,
        "canCallUno": can_call_uno,
        "message": message,
        "winnerName": winner.display_label if winner else "",
        "winnerUserId": game.winner_user_id,
        "rules": {
            "drawUntilPlayable": game.draw_until_playable,
            "stacking": game.stacking,
            "jumpIn": game.jump_in,
            "sevenZero": game.seven_zero,
            "forcePlayDrawnCard": game.force_play_drawn_card,
            "keepBluffChallenge": game.keep_bluff_challenge,
        },
        "players": [
            {
                "id": row.user_id,
                "name": row.display_label,
                **_profile_payload(row.user),
                "seat": row.seat,
                "isCurrent": current and row.user_id == current.user_id,
                "isYou": row.user_id == user.id,
                "isReady": row.is_ready,
                "cardCount": len(hands.get(str(row.user_id), [])),
                "saidUno": bool((game.uno_calls or {}).get(str(row.user_id))),
            }
            for row in players
        ],
        "actionLog": game.action_log or [],
        "updatedAt": timezone.localtime(game.updated_at).strftime("%d.%m.%Y %H:%M"),
    }


@login_required
def uno_home(request):
    _delete_empty_games()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            try:
                max_players = int(request.POST.get("max_players", 4) or 4)
            except (TypeError, ValueError):
                max_players = 4
            max_players = min(4, max(2, max_players))
            game = UnoGame.objects.create(
                owner=request.user,
                name=(request.POST.get("name", "").strip() or _("Uno"))[:80],
                code=_generate_game_code(),
                max_players=max_players,
                draw_until_playable=request.POST.get("draw_until_playable") == "on",
                stacking=request.POST.get("stacking") == "on",
                jump_in=request.POST.get("jump_in") == "on",
                seven_zero=request.POST.get("seven_zero") == "on",
                force_play_drawn_card=request.POST.get("force_play_drawn_card") == "on",
                keep_bluff_challenge=request.POST.get("keep_bluff_challenge") == "on",
            )
            UnoPlayer.objects.create(game=game, user=request.user, seat=0, is_ready=True)
            return redirect("uno_lobby", code=game.code)

        if action == "join":
            code = request.POST.get("code", "").strip().upper()
            if code:
                return redirect("uno_lobby", code=code)
            messages.error(request, _("Bitte gib einen Raum-Code ein."))

    return render(request, "app/uno_home.html", {"my_games": _home_games_for_user(request.user), "invites": _home_invites_for_user(request.user)})


@login_required
@require_GET
def uno_home_state_api(request):
    _delete_empty_games()
    return JsonResponse({"ok": True, "games": [_serialize_home_game(game) for game in _home_games_for_user(request.user)], "invites": [_serialize_home_invite(invite) for invite in _home_invites_for_user(request.user)]})


@login_required
def uno_lobby(request, code):
    game = UnoGame.objects.select_related("owner").filter(code=code.upper()).first()
    if not game:
        messages.warning(request, _("Diese Uno-Lobby existiert nicht mehr."))
        return redirect("uno_home")
    if not _join_game(game, request.user):
        messages.error(request, _("Dieser Uno-Raum ist voll oder l\u00e4uft bereits."))
        return redirect("uno_home")
    return render(request, "app/uno_lobby.html", {"game": game, "friend_invite_rows": _friend_invite_rows(game, request.user)})


@login_required
@require_POST
def uno_invite_friend(request, code):
    game = get_object_or_404(UnoGame, code=code.upper())
    if not (game.owner_id == request.user.id or game.player_for_user(request.user)) or game.is_full:
        messages.error(request, _("Dieser Raum kann keine weiteren Spieler aufnehmen."))
        return redirect("uno_lobby", code=game.code)
    friend = get_object_or_404(User, id=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("uno_lobby", code=game.code)
    UnoInvite.objects.update_or_create(game=game, to_user=friend, defaults={"from_user": request.user, "status": UnoInvite.STATUS_PENDING})
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("uno_lobby", code=game.code)


@login_required
@require_POST
def uno_invite_response(request, invite_id):
    invite = get_object_or_404(UnoInvite.objects.select_related("game"), id=invite_id, to_user=request.user)
    if request.POST.get("action") == "accept":
        if invite.game.is_full and not invite.game.player_for_user(request.user):
            invite.status = UnoInvite.STATUS_DECLINED
            invite.save(update_fields=["status", "updated_at"])
            messages.error(request, _("Dieser Uno-Raum ist bereits voll."))
            return redirect("uno_home")
        invite.status = UnoInvite.STATUS_ACCEPTED
        invite.save(update_fields=["status", "updated_at"])
        return redirect("uno_lobby", code=invite.game.code)
    invite.status = UnoInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    messages.info(request, _("Einladung wurde abgelehnt."))
    return redirect("uno_home")


@login_required
@require_GET
def uno_state_api(request, code):
    game = UnoGame.objects.filter(code=code.upper()).first()
    if not game:
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Uno-Raum wurde gelöscht."), "redirectUrl": reverse("uno_home")}, status=410)

    game.players.filter(user=request.user).update(last_seen=timezone.now())
    if _cleanup_game_players(game, keep_user_id=request.user.id):
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Uno-Raum wurde gelöscht."), "redirectUrl": reverse("uno_home")}, status=410)
    game.refresh_from_db()

    if not game.players.exists():
        game.delete()
        return JsonResponse({"ok": False, "gameDeleted": True, "error": _("Dieser Uno-Raum wurde gelöscht."), "redirectUrl": reverse("uno_home")}, status=410)

    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_start_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann starten.")}, status=403)
        if game.status != UnoGame.STATUS_WAITING or game.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Du brauchst mindestens zwei Spieler.")}, status=400)
        _start_round(game)
        game.last_move_at = timezone.now()
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_play_api(request, code):
    card_id = request.POST.get("card_id", "")
    chosen_color = request.POST.get("color", "")
    target_user_id = request.POST.get("target_user_id")
    target_user_id = int(target_user_id) if target_user_id and target_user_id.isdigit() else None
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        player = next((row for row in players if row.user_id == request.user.id), None)
        current = _current_player(game, players)
        if not player or game.status != UnoGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Du bist nicht in diesem Spiel.")}, status=403)
        hands = dict(game.hands or {})
        hand = list(hands.get(str(request.user.id), []))
        card = next((item for item in hand if item["id"] == card_id), None)
        top_card = (game.discard_pile or [{}])[-1] if game.discard_pile else {}
        is_jump_in = game.jump_in and current and current.user_id != request.user.id and card and card["color"] == top_card.get("color") and card["value"] == top_card.get("value")
        if current.user_id != request.user.id and not is_jump_in:
            return JsonResponse({"ok": False, "error": _("Du bist noch nicht am Zug.")}, status=400)
        if not card:
            return JsonResponse({"ok": False, "error": _("Diese Karte ist nicht auf deiner Hand.")}, status=400)
        if game.pending_draw and not game.stacking:
            return JsonResponse({"ok": False, "error": _("Ziehe erst die Strafkarten.")}, status=400)
        if not _is_playable(card, top_card, game.current_color, game.pending_draw):
            return JsonResponse({"ok": False, "error": _("Diese Karte passt gerade nicht.")}, status=400)
        if card["color"] == "wild" and chosen_color not in COLORS:
            return JsonResponse({"ok": False, "error": _("W\u00e4hle eine Farbe.")}, status=400)
        if card["value"] == "7" and game.seven_zero and len(players) > 1 and not target_user_id:
            return JsonResponse({"ok": False, "error": _("W\u00e4hle einen Spieler zum Tauschen.")}, status=400)

        hand_count_before = len(hand)
        uno_calls = dict(game.uno_calls or {})
        had_called_uno = bool(uno_calls.get(str(request.user.id)))
        hand.remove(card)
        hands[str(request.user.id)] = hand
        game.hands = hands
        game.discard_pile = list(game.discard_pile or []) + [card]
        game.has_drawn_this_turn = False
        if is_jump_in:
            game.current_player_index = players.index(player)
        _apply_card_effect(game, card, player, chosen_color, target_user_id)
        _append_log(game, _("%(name)s legt %(card)s.") % {"name": player.display_label, "card": card["label"]})
        if hand_count_before == 2 and not had_called_uno and game.status == UnoGame.STATUS_PLAYING:
            hands = dict(game.hands or {})
            drawn = _draw_cards(game, hands, request.user.id, 1)
            game.hands = hands
            hand = list(hands.get(str(request.user.id), []))
            if drawn:
                _append_log(game, _("%(name)s hat Uno vergessen und zieht 1 Strafkarte.") % {"name": player.display_label})
        if len(hand) != 1:
            uno_calls.pop(str(request.user.id), None)
        game.uno_calls = uno_calls
        if not hand:
            game.status = UnoGame.STATUS_FINISHED
            game.winner_user_id = request.user.id
            _append_log(game, _("%(name)s gewinnt die Runde.") % {"name": player.display_label})
        game.last_move_at = timezone.now()
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_draw_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        current = _current_player(game, players)
        player = next((row for row in players if row.user_id == request.user.id), None)
        if not player or not current or current.user_id != request.user.id or game.status != UnoGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Du bist nicht am Zug.")}, status=400)
        hands = dict(game.hands or {})
        amount = game.pending_draw or 1
        drawn = _draw_cards(game, hands, request.user.id, amount)
        game.hands = hands
        game.pending_draw = 0
        game.has_drawn_this_turn = True
        _append_log(game, _("%(name)s zieht %(count)s Karte(n).") % {"name": player.display_label, "count": len(drawn)})

        if game.draw_until_playable and not game.force_play_drawn_card and not game.pending_draw:
            while drawn and not _has_playable(hands.get(str(request.user.id), []), game):
                drawn = _draw_cards(game, hands, request.user.id, 1)
                game.hands = hands
        if game.force_play_drawn_card and drawn and _is_playable(drawn[-1], (game.discard_pile or [{}])[-1], game.current_color, game.pending_draw):
            pass
        else:
            game.current_player_index = _next_index(players, game.current_player_index, game.direction)
            game.has_drawn_this_turn = False
        game.last_move_at = timezone.now()
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_pass_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        current = _current_player(game, players)
        if not current or current.user_id != request.user.id or not game.has_drawn_this_turn:
            return JsonResponse({"ok": False, "error": _("Du kannst erst nach dem Ziehen passen.")}, status=400)
        hand = (game.hands or {}).get(str(request.user.id), [])
        if game.force_play_drawn_card and _has_playable(hand, game):
            return JsonResponse({"ok": False, "error": _("Du musst eine spielbare gezogene Karte legen.")}, status=400)
        game.current_player_index = _next_index(players, game.current_player_index, game.direction)
        game.has_drawn_this_turn = False
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_call_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        players = _ordered_players(game)
        current = _current_player(game, players)
        player = next((row for row in players if row.user_id == request.user.id), None)
        if not player or not current or current.user_id != request.user.id or game.status != UnoGame.STATUS_PLAYING:
            return JsonResponse({"ok": False, "error": _("Du kannst Uno nur sagen, wenn du am Zug bist.")}, status=400)
        hands = dict(game.hands or {})
        hand = list(hands.get(str(request.user.id), []))
        if len(hand) != 2 or not _has_playable(hand, game):
            return JsonResponse({"ok": False, "error": _("Uno sagst du, bevor du deine vorletzte Karte legst.")}, status=400)
        calls = dict(game.uno_calls or {})
        calls[str(request.user.id)] = True
        game.uno_calls = calls
        _append_log(game, _("%(name)s sagt Uno.") % {"name": _player_name(request.user)})
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_catch_api(request, code):
    target_user_id = request.POST.get("target_user_id")
    if not target_user_id or not target_user_id.isdigit():
        return JsonResponse({"ok": False, "error": _("W\u00e4hle einen Spieler.")}, status=400)
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        hands = dict(game.hands or {})
        target_key = str(int(target_user_id))
        if len(hands.get(target_key, [])) != 1 or (game.uno_calls or {}).get(target_key):
            return JsonResponse({"ok": False, "error": _("Dieser Spieler kann nicht bestraft werden.")}, status=400)
        _draw_cards(game, hands, int(target_user_id), 2)
        game.hands = hands
        _append_log(game, _("Uno vergessen: +2 Strafkarten."))
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
@_database_lock_guard
def uno_reset_api(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(of=("self",)), code=code.upper())
        if game.owner_id != request.user.id:
            return JsonResponse({"ok": False, "error": _("Nur der Host kann neu starten.")}, status=403)
        if game.players.count() < 2:
            return JsonResponse({"ok": False, "error": _("Du brauchst mindestens zwei Spieler.")}, status=400)
        game.round_number += 1
        _start_round(game)
        game.save()
    return JsonResponse({"ok": True, "game": _serialize_game(game, request.user)})


@login_required
@require_POST
def uno_leave(request, code):
    with transaction.atomic():
        game = get_object_or_404(UnoGame.objects.select_for_update(), code=code.upper())
        players_before = _ordered_players(game)
        removed_index = next((index for index, player in enumerate(players_before) if player.user_id == request.user.id), None)
        current_index_before = game.current_player_index % len(players_before) if players_before else 0
        removed_current_player = removed_index == current_index_before

        removed_count = _remove_player_from_game(game, request.user)
        if not removed_count:
            messages.info(request, _("Du bist nicht mehr in diesem Raum."))
            return redirect("uno_home")

        players_after = _ordered_players(game)
        if not players_after:
            game.delete()
            messages.info(request, _("Uno-Raum wurde gelöscht."))
            return redirect("uno_home")

        if game.owner_id == request.user.id:
            game.owner = players_after[0].user

        if game.status == UnoGame.STATUS_PLAYING:
            if len(players_after) >= 2:
                if removed_index is not None:
                    if removed_current_player:
                        game.current_player_index = removed_index % len(players_after)
                        game.pending_draw = 0
                        game.has_drawn_this_turn = False
                    elif removed_index < current_index_before:
                        game.current_player_index = max(0, current_index_before - 1) % len(players_after)
                    else:
                        game.current_player_index = current_index_before % len(players_after)
                else:
                    game.current_player_index = game.current_player_index % len(players_after)
                _append_log(game, _("Ein Spieler hat den Raum verlassen. Die Runde läuft weiter."))
            else:
                _reset_to_waiting_lobby(game)
                _append_log(game, _("Ein Spieler hat den Raum verlassen. Warte auf weitere Spieler."))
        else:
            game.current_player_index = game.current_player_index % len(players_after)

        game.save()
    return redirect("uno_home")


@login_required
@require_POST
def uno_delete(request, code):
    game = get_object_or_404(UnoGame, code=code.upper())
    if game.owner_id != request.user.id:
        messages.error(request, _("Du kannst diesen Raum nicht l\u00f6schen."))
        return redirect("uno_home")
    game.delete()
    messages.success(request, _("Uno-Raum wurde gel\u00f6scht."))
    return redirect("uno_home")
