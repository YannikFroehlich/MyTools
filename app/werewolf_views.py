import random
import secrets
import string
from collections import Counter

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .models import Friendship, WerewolfInvite, WerewolfLobby, WerewolfMessage, WerewolfPlayer
from .notification_utils import invalidate_notification_cache


MIN_PLAYERS = 5
MAX_PLAYERS = 20
ROLE_LABELS = dict(WerewolfPlayer.ROLE_CHOICES)


def _json_error(text, status=400):
    return JsonResponse({"ok": False, "error": str(text)}, status=status)


def _make_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not WerewolfLobby.objects.filter(code=code).exists():
            return code


def _int(value, default, minimum, maximum):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _is_friend(user, other):
    return other.id in Friendship.friend_ids_for_user(user)


def _can_join(lobby, user, password="", invited=False):
    if lobby.status != WerewolfLobby.STATUS_WAITING:
        return False, _("Dieses Spiel läuft bereits.")
    if lobby.players.count() >= lobby.max_players:
        return False, _("Die Lobby ist voll.")
    if lobby.visibility == WerewolfLobby.VISIBILITY_FRIENDS:
        if not (invited or _is_friend(user, lobby.owner)):
            return False, _("Dieser Raum ist nur für Freunde des Hosts.")
    if lobby.visibility == WerewolfLobby.VISIBILITY_PASSWORD:
        if not invited and not check_password(password or "", lobby.password_hash):
            return False, _("Das Lobby-Passwort ist falsch.")
    return True, ""


def _add_player(lobby, user):
    player, _created = WerewolfPlayer.objects.get_or_create(
        lobby=lobby,
        user=user,
        defaults={"seat": lobby.players.count(), "display_name": user.get_full_name() or user.username},
    )
    WerewolfInvite.objects.filter(lobby=lobby, to_user=user).update(status=WerewolfInvite.STATUS_ACCEPTED)
    return player


def _system(lobby, text):
    WerewolfMessage.objects.create(
        lobby=lobby,
        channel=WerewolfMessage.CHANNEL_SYSTEM,
        text=str(text)[:500],
        day_number=lobby.day_number,
    )


def _winner(lobby):
    alive = lobby.players.filter(is_alive=True)
    wolves = alive.filter(role=WerewolfPlayer.ROLE_WEREWOLF).count()
    villagers = alive.exclude(role=WerewolfPlayer.ROLE_WEREWOLF).count()
    if wolves == 0:
        return "village"
    if wolves >= villagers:
        return "wolves"
    return ""


def _finish_if_needed(lobby):
    winner = _winner(lobby)
    if not winner:
        return False
    lobby.status = WerewolfLobby.STATUS_FINISHED
    lobby.winner = winner
    lobby.phase_started_at = timezone.now()
    lobby.save(update_fields=["status", "winner", "phase_started_at", "updated_at"])
    text = _("Das Dorf gewinnt!") if winner == "village" else _("Die Werwölfe gewinnen!")
    _system(lobby, text)
    return True


def _role_setup(lobby, players):
    player_count = len(players)
    max_wolves = max(1, (player_count - 1) // 2)
    wolf_count = min(max(1, lobby.werewolf_count), max_wolves)
    roles = [WerewolfPlayer.ROLE_WEREWOLF] * wolf_count
    optional = [
        (lobby.include_seer, WerewolfPlayer.ROLE_SEER),
        (lobby.include_witch, WerewolfPlayer.ROLE_WITCH),
        (lobby.include_guard, WerewolfPlayer.ROLE_GUARD),
    ]
    for enabled, role in optional:
        if enabled and len(roles) < player_count:
            roles.append(role)
    roles.extend([WerewolfPlayer.ROLE_VILLAGER] * (player_count - len(roles)))
    random.SystemRandom().shuffle(roles)
    for player, role in zip(players, roles):
        state = {}
        if role == WerewolfPlayer.ROLE_WITCH:
            state = {"heal_available": True, "poison_available": True}
        player.role = role
        player.is_alive = True
        player.vote_target = None
        player.night_target = None
        player.role_state = state
    WerewolfPlayer.objects.bulk_update(players, ["role", "is_alive", "vote_target", "night_target", "role_state"])


def _plurality_target(players, field):
    target_ids = [getattr(player, field + "_id") for player in players if getattr(player, field + "_id")]
    if not target_ids:
        return None
    counts = Counter(target_ids)
    top_count = max(counts.values())
    leaders = [target_id for target_id, count in counts.items() if count == top_count]
    if len(leaders) != 1:
        return None
    return leaders[0]


def _kill_player(lobby, player, reason):
    if not player or not player.is_alive:
        return
    player.is_alive = False
    player.save(update_fields=["is_alive"])
    if lobby.reveal_roles_on_death:
        _system(lobby, _("%(name)s ist gestorben (%(role)s).") % {"name": player.display_label, "role": ROLE_LABELS.get(player.role, player.role)})
    else:
        _system(lobby, _("%(name)s ist gestorben.") % {"name": player.display_label})


def _resolve_night(lobby):
    alive = list(lobby.players.filter(is_alive=True).select_related("user", "night_target"))
    wolves = [player for player in alive if player.role == WerewolfPlayer.ROLE_WEREWOLF]
    victim_id = _plurality_target(wolves, "night_target")
    victim = next((player for player in alive if player.id == victim_id), None)

    guard = next((player for player in alive if player.role == WerewolfPlayer.ROLE_GUARD), None)
    protected_id = guard.night_target_id if guard else None
    witch = next((player for player in alive if player.role == WerewolfPlayer.ROLE_WITCH), None)
    witch_state = dict(witch.role_state or {}) if witch else {}
    witch_action = witch_state.get("night_action", "")

    deaths = []
    saved = False
    if victim:
        if protected_id == victim.id:
            saved = True
        elif witch and witch_action == "heal" and witch_state.get("heal_available", False):
            saved = True
            witch_state["heal_available"] = False
        else:
            deaths.append(victim)

    if witch and witch_action == "poison" and witch_state.get("poison_available", False) and witch.night_target_id:
        poison_target = next((player for player in alive if player.id == witch.night_target_id), None)
        if poison_target and poison_target not in deaths:
            deaths.append(poison_target)
        witch_state["poison_available"] = False

    if witch:
        witch_state.pop("night_action", None)
        witch.role_state = witch_state
        witch.save(update_fields=["role_state"])
    if guard and guard.night_target_id:
        guard_state = dict(guard.role_state or {})
        guard_state["last_protected_id"] = guard.night_target_id
        guard.role_state = guard_state
        guard.save(update_fields=["role_state"])

    for player in deaths:
        _kill_player(lobby, player, "night")
    if not deaths:
        _system(lobby, _("Die Nacht endet ohne Opfer."))
    elif saved and victim:
        _system(lobby, _("Jemand wurde in dieser Nacht gerettet."))

    lobby.players.update(vote_target=None, night_target=None)
    if not _finish_if_needed(lobby):
        lobby.status = WerewolfLobby.STATUS_DAY
        lobby.phase_started_at = timezone.now()
        lobby.save(update_fields=["status", "phase_started_at", "updated_at"])
        _system(lobby, _("Tag %(day)s beginnt. Diskutiert und stimmt ab.") % {"day": lobby.day_number})


def _resolve_day(lobby):
    alive = list(lobby.players.filter(is_alive=True).select_related("user", "vote_target"))
    target_id = _plurality_target(alive, "vote_target")
    eliminated = next((player for player in alive if player.id == target_id), None)
    if eliminated:
        _kill_player(lobby, eliminated, "vote")
    else:
        _system(lobby, _("Die Abstimmung endet ohne eindeutige Mehrheit."))
    lobby.players.update(vote_target=None, night_target=None)
    if not _finish_if_needed(lobby):
        lobby.day_number += 1
        lobby.status = WerewolfLobby.STATUS_NIGHT
        lobby.phase_started_at = timezone.now()
        lobby.save(update_fields=["day_number", "status", "phase_started_at", "updated_at"])
        _system(lobby, _("Nacht %(day)s beginnt. Das Dorf schläft ein.") % {"day": lobby.day_number})


def _public_lobbies():
    return (
        WerewolfLobby.objects.filter(visibility=WerewolfLobby.VISIBILITY_PUBLIC, status=WerewolfLobby.STATUS_WAITING)
        .annotate()
        .prefetch_related("players")[:30]
    )


def _friend_invite_rows(lobby, user):
    User = get_user_model()
    current_ids = set(lobby.players.values_list("user_id", flat=True))
    friends = User.objects.filter(id__in=Friendship.friend_ids_for_user(user), is_active=True).exclude(id__in=current_ids).order_by("username")
    pending = set(lobby.invites.filter(status=WerewolfInvite.STATUS_PENDING).values_list("to_user_id", flat=True))
    accepted = set(lobby.invites.filter(status=WerewolfInvite.STATUS_ACCEPTED).values_list("to_user_id", flat=True))
    return [{"user": friend, "is_invited": friend.id in pending, "was_invited": friend.id in accepted} for friend in friends]


def _serialize_messages(lobby, viewer):
    channels = [WerewolfMessage.CHANNEL_SYSTEM, WerewolfMessage.CHANNEL_VILLAGE]
    if viewer.role == WerewolfPlayer.ROLE_WEREWOLF:
        channels.append(WerewolfMessage.CHANNEL_WOLVES)
    rows = lobby.messages.filter(channel__in=channels).select_related("sender").order_by("-created_at")[:80]
    return [
        {
            "id": row.id,
            "channel": row.channel,
            "sender": row.sender.username if row.sender else "",
            "text": row.text,
            "time": timezone.localtime(row.created_at).strftime("%H:%M"),
        }
        for row in reversed(list(rows))
    ]


def _serialize_lobby(lobby, user):
    players = list(lobby.players.select_related("user", "vote_target", "night_target"))
    viewer = next(player for player in players if player.user_id == user.id)
    finished = lobby.status == WerewolfLobby.STATUS_FINISHED
    player_rows = []
    day_counts = Counter(player.vote_target_id for player in players if player.vote_target_id)
    for player in players:
        visible_role = ""
        if player.id == viewer.id or finished or (not player.is_alive and lobby.reveal_roles_on_death):
            visible_role = player.role
        elif viewer.role == WerewolfPlayer.ROLE_WEREWOLF and player.role == WerewolfPlayer.ROLE_WEREWOLF:
            visible_role = player.role
        row = {
            "id": player.id,
            "name": player.display_label,
            "isAlive": player.is_alive,
            "isHost": player.user_id == lobby.owner_id,
            "isMe": player.id == viewer.id,
            "role": visible_role,
            "roleLabel": str(ROLE_LABELS.get(visible_role, "")),
            "voteCount": day_counts.get(player.id, 0) if lobby.status == WerewolfLobby.STATUS_DAY else 0,
            "hasVoted": bool(player.vote_target_id) if not lobby.anonymous_day_votes or player.id == viewer.id else False,
        }
        if viewer.role == WerewolfPlayer.ROLE_WEREWOLF and player.role == WerewolfPlayer.ROLE_WEREWOLF:
            row["nightTargetId"] = player.night_target_id
        player_rows.append(row)

    state = dict(viewer.role_state or {})
    result = {
        "ok": True,
        "code": lobby.code,
        "name": lobby.name,
        "status": lobby.status,
        "statusLabel": str(lobby.get_status_display()),
        "day": lobby.day_number,
        "winner": lobby.winner,
        "isHost": lobby.owner_id == user.id,
        "viewer": {
            "id": viewer.id,
            "role": viewer.role,
            "roleLabel": str(ROLE_LABELS.get(viewer.role, _("Noch keine Rolle"))),
            "isAlive": viewer.is_alive,
            "voteTargetId": viewer.vote_target_id,
            "nightTargetId": viewer.night_target_id,
            "roleState": state,
        },
        "players": player_rows,
        "messages": _serialize_messages(lobby, viewer),
        "rules": {
            "maxPlayers": lobby.max_players,
            "werewolfCount": lobby.werewolf_count,
            "seer": lobby.include_seer,
            "witch": lobby.include_witch,
            "guard": lobby.include_guard,
            "revealRoles": lobby.reveal_roles_on_death,
            "anonymousVotes": lobby.anonymous_day_votes,
        },
    }
    if viewer.role == WerewolfPlayer.ROLE_WITCH and lobby.status == WerewolfLobby.STATUS_NIGHT:
        wolves = [player for player in players if player.is_alive and player.role == WerewolfPlayer.ROLE_WEREWOLF]
        victim_id = _plurality_target(wolves, "night_target")
        victim = next((player for player in players if player.id == victim_id), None)
        result["viewer"]["wolfVictim"] = {"id": victim.id, "name": victim.display_label} if victim else None
    return result


@login_required
def werewolf_home(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            visibility = request.POST.get("visibility", WerewolfLobby.VISIBILITY_PUBLIC)
            if visibility not in dict(WerewolfLobby.VISIBILITY_CHOICES):
                visibility = WerewolfLobby.VISIBILITY_PUBLIC
            password = request.POST.get("password", "").strip()
            if visibility == WerewolfLobby.VISIBILITY_PASSWORD and len(password) < 4:
                messages.error(request, _("Das Passwort muss mindestens 4 Zeichen haben."))
            else:
                lobby = WerewolfLobby.objects.create(
                    owner=request.user,
                    name=(request.POST.get("name") or _("Werwolf-Dorf")).strip()[:80],
                    code=_make_code(),
                    visibility=visibility,
                    password_hash=make_password(password) if visibility == WerewolfLobby.VISIBILITY_PASSWORD else "",
                    max_players=_int(request.POST.get("max_players"), 12, MIN_PLAYERS, MAX_PLAYERS),
                    werewolf_count=_int(request.POST.get("werewolf_count"), 2, 1, 6),
                    include_seer=request.POST.get("include_seer") == "on",
                    include_witch=request.POST.get("include_witch") == "on",
                    include_guard=request.POST.get("include_guard") == "on",
                    reveal_roles_on_death=request.POST.get("reveal_roles_on_death") == "on",
                    anonymous_day_votes=request.POST.get("anonymous_day_votes") == "on",
                )
                _add_player(lobby, request.user)
                _system(lobby, _("Die Lobby wurde erstellt."))
                return redirect("werewolf_lobby", code=lobby.code)
        elif action == "join":
            code = (request.POST.get("code") or "").strip().upper()
            lobby = WerewolfLobby.objects.filter(code=code).first()
            if not lobby:
                messages.error(request, _("Keine Werwolf-Lobby mit diesem Code gefunden."))
            elif lobby.players.filter(user=request.user).exists():
                return redirect("werewolf_lobby", code=lobby.code)
            else:
                invited = lobby.invites.filter(to_user=request.user, status=WerewolfInvite.STATUS_PENDING).exists()
                allowed, error = _can_join(lobby, request.user, request.POST.get("password", ""), invited)
                if allowed:
                    _add_player(lobby, request.user)
                    _system(lobby, _("%(name)s ist der Lobby beigetreten.") % {"name": request.user.username})
                    return redirect("werewolf_lobby", code=lobby.code)
                messages.error(request, error)

    invites = WerewolfInvite.objects.filter(to_user=request.user, status=WerewolfInvite.STATUS_PENDING).select_related("lobby", "from_user")
    my_lobbies = WerewolfLobby.objects.filter(players__user=request.user).distinct()[:20]
    return render(request, "app/werewolf_home.html", {"public_lobbies": _public_lobbies(), "invites": invites, "my_lobbies": my_lobbies})


@login_required
def werewolf_lobby(request, code):
    lobby = get_object_or_404(WerewolfLobby, code=code.upper())
    if not lobby.players.filter(user=request.user).exists():
        messages.error(request, _("Du bist kein Mitglied dieser Lobby."))
        return redirect("werewolf_home")
    return render(request, "app/werewolf_lobby.html", {"lobby": lobby, "friend_invite_rows": _friend_invite_rows(lobby, request.user)})


@login_required
@require_POST
def werewolf_join(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        if lobby.players.filter(user=request.user).exists():
            return redirect("werewolf_lobby", code=lobby.code)
        invited = lobby.invites.filter(to_user=request.user, status=WerewolfInvite.STATUS_PENDING).exists()
        allowed, error = _can_join(lobby, request.user, request.POST.get("password", ""), invited)
        if not allowed:
            messages.error(request, error)
            return redirect("werewolf_home")
        _add_player(lobby, request.user)
        _system(lobby, _("%(name)s ist der Lobby beigetreten.") % {"name": request.user.username})
    return redirect("werewolf_lobby", code=lobby.code)


@login_required
@require_POST
def werewolf_invite_friend(request, code):
    lobby = get_object_or_404(WerewolfLobby, code=code.upper(), players__user=request.user)
    if lobby.status != WerewolfLobby.STATUS_WAITING:
        messages.error(request, _("Während des Spiels können keine Spieler eingeladen werden."))
        return redirect("werewolf_lobby", code=lobby.code)
    friend = get_object_or_404(get_user_model(), pk=request.POST.get("friend_id"), is_active=True)
    if friend.id not in Friendship.friend_ids_for_user(request.user):
        messages.error(request, _("Du kannst nur Freunde einladen."))
        return redirect("werewolf_lobby", code=lobby.code)
    invite, created = WerewolfInvite.objects.get_or_create(lobby=lobby, to_user=friend, defaults={"from_user": request.user})
    if not created:
        invite.from_user = request.user
        invite.status = WerewolfInvite.STATUS_PENDING
        invite.save(update_fields=["from_user", "status", "updated_at"])
    invalidate_notification_cache(friend)
    messages.success(request, _("Einladung wurde gesendet."))
    return redirect("werewolf_lobby", code=lobby.code)


@login_required
@require_POST
def werewolf_invite_response(request, invite_id):
    invite = get_object_or_404(WerewolfInvite.objects.select_related("lobby"), pk=invite_id, to_user=request.user)
    if request.POST.get("action") == "accept":
        allowed, error = _can_join(invite.lobby, request.user, invited=True)
        if allowed:
            _add_player(invite.lobby, request.user)
            _system(invite.lobby, _("%(name)s ist der Lobby beigetreten.") % {"name": request.user.username})
            invalidate_notification_cache(request.user)
            return redirect("werewolf_lobby", code=invite.lobby.code)
        messages.error(request, error)
    invite.status = WerewolfInvite.STATUS_DECLINED
    invite.save(update_fields=["status", "updated_at"])
    invalidate_notification_cache(request.user)
    return redirect("werewolf_home")


@login_required
@require_GET
def werewolf_state_api(request, code):
    lobby = WerewolfLobby.objects.filter(code=code.upper()).first()
    if not lobby:
        return JsonResponse({"ok": False, "gameDeleted": True, "redirectUrl": reverse("werewolf_home")}, status=410)
    player = lobby.players.filter(user=request.user).first()
    if not player:
        return _json_error(_("Kein Zugriff auf diese Lobby."), 403)
    player.save(update_fields=["last_seen"])
    return JsonResponse(_serialize_lobby(lobby, request.user))


@login_required
@require_POST
def werewolf_start_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return _json_error(_("Nur der Host kann das Spiel starten."), 403)
        if lobby.status != WerewolfLobby.STATUS_WAITING:
            return _json_error(_("Das Spiel wurde bereits gestartet."))
        players = list(lobby.players.select_for_update().order_by("seat", "joined_at"))
        if len(players) < MIN_PLAYERS:
            return _json_error(_("Werwolf benötigt mindestens %(count)s Spieler.") % {"count": MIN_PLAYERS})
        _role_setup(lobby, players)
        lobby.status = WerewolfLobby.STATUS_NIGHT
        lobby.day_number = 1
        lobby.winner = ""
        lobby.phase_started_at = timezone.now()
        lobby.save(update_fields=["status", "day_number", "winner", "phase_started_at", "updated_at"])
        _system(lobby, _("Nacht 1 beginnt. Schaut euch eure geheime Rolle an."))
    return JsonResponse(_serialize_lobby(lobby, request.user))


@login_required
@require_POST
def werewolf_action_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        player = get_object_or_404(WerewolfPlayer.objects.select_for_update(), lobby=lobby, user=request.user)
        if not player.is_alive:
            return _json_error(_("Ausgeschiedene Spieler können nicht mehr handeln."), 403)
        action = request.POST.get("action", "")
        target_id = request.POST.get("target_id")
        target = lobby.players.filter(pk=target_id, is_alive=True).first() if target_id else None

        if action == "day_vote":
            if lobby.status != WerewolfLobby.STATUS_DAY or not target or target.id == player.id:
                return _json_error(_("Diese Abstimmung ist nicht möglich."))
            player.vote_target = target
            player.save(update_fields=["vote_target"])
        elif action == "wolf_vote":
            if lobby.status != WerewolfLobby.STATUS_NIGHT or player.role != WerewolfPlayer.ROLE_WEREWOLF:
                return _json_error(_("Diese Nachtaktion ist nicht möglich."), 403)
            if not target or target.role == WerewolfPlayer.ROLE_WEREWOLF:
                return _json_error(_("Werwölfe müssen einen lebenden Nicht-Werwolf wählen."))
            player.night_target = target
            player.save(update_fields=["night_target"])
        elif action == "seer_inspect":
            if lobby.status != WerewolfLobby.STATUS_NIGHT or player.role != WerewolfPlayer.ROLE_SEER:
                return _json_error(_("Diese Nachtaktion ist nicht möglich."), 403)
            if not target or target.id == player.id:
                return _json_error(_("Wähle einen anderen lebenden Spieler."))
            state = dict(player.role_state or {})
            if state.get("inspected_day") == lobby.day_number:
                return _json_error(_("Du hast in dieser Nacht bereits jemanden geprüft."))
            state.update({"inspected_day": lobby.day_number, "inspection_name": target.display_label, "inspection_is_wolf": target.role == WerewolfPlayer.ROLE_WEREWOLF})
            player.night_target = target
            player.role_state = state
            player.save(update_fields=["night_target", "role_state"])
        elif action == "guard_protect":
            if lobby.status != WerewolfLobby.STATUS_NIGHT or player.role != WerewolfPlayer.ROLE_GUARD:
                return _json_error(_("Diese Nachtaktion ist nicht möglich."), 403)
            if not target:
                return _json_error(_("Wähle einen lebenden Spieler."))
            if (player.role_state or {}).get("last_protected_id") == target.id:
                return _json_error(_("Du kannst nicht zweimal hintereinander dieselbe Person schützen."))
            player.night_target = target
            player.save(update_fields=["night_target"])
        elif action == "witch_action":
            if lobby.status != WerewolfLobby.STATUS_NIGHT or player.role != WerewolfPlayer.ROLE_WITCH:
                return _json_error(_("Diese Nachtaktion ist nicht möglich."), 403)
            choice = request.POST.get("choice", "skip")
            state = dict(player.role_state or {})
            if choice == "heal" and not state.get("heal_available", False):
                return _json_error(_("Der Heiltrank wurde bereits benutzt."))
            if choice == "poison":
                if not state.get("poison_available", False):
                    return _json_error(_("Der Gifttrank wurde bereits benutzt."))
                if not target or target.id == player.id:
                    return _json_error(_("Wähle ein gültiges Gift-Opfer."))
                player.night_target = target
            elif choice in {"heal", "skip"}:
                player.night_target = None
            else:
                return _json_error(_("Unbekannte Hexen-Aktion."))
            state["night_action"] = choice
            player.role_state = state
            player.save(update_fields=["night_target", "role_state"])
        else:
            return _json_error(_("Unbekannte Aktion."))
    return JsonResponse(_serialize_lobby(lobby, request.user))


@login_required
@require_POST
def werewolf_advance_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return _json_error(_("Nur der Host kann die Phase beenden."), 403)
        if lobby.status == WerewolfLobby.STATUS_NIGHT:
            _resolve_night(lobby)
        elif lobby.status == WerewolfLobby.STATUS_DAY:
            _resolve_day(lobby)
        else:
            return _json_error(_("Diese Phase kann nicht beendet werden."))
    return JsonResponse(_serialize_lobby(lobby, request.user))


@login_required
@require_POST
def werewolf_message_api(request, code):
    lobby = get_object_or_404(WerewolfLobby, code=code.upper())
    player = get_object_or_404(WerewolfPlayer, lobby=lobby, user=request.user)
    text = " ".join((request.POST.get("text") or "").strip().split())[:500]
    channel = request.POST.get("channel", WerewolfMessage.CHANNEL_VILLAGE)
    if not text:
        return _json_error(_("Schreibe zuerst eine Nachricht."))
    if not player.is_alive and lobby.status != WerewolfLobby.STATUS_FINISHED:
        return _json_error(_("Ausgeschiedene Spieler können nur noch zuschauen."), 403)
    if channel == WerewolfMessage.CHANNEL_WOLVES:
        if player.role != WerewolfPlayer.ROLE_WEREWOLF:
            return _json_error(_("Kein Zugriff auf den Werwolf-Chat."), 403)
    elif channel != WerewolfMessage.CHANNEL_VILLAGE:
        return _json_error(_("Unbekannter Chat-Kanal."))
    WerewolfMessage.objects.create(lobby=lobby, sender=request.user, channel=channel, text=text, day_number=lobby.day_number)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def werewolf_reset_api(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        if lobby.owner_id != request.user.id:
            return _json_error(_("Nur der Host kann eine neue Runde vorbereiten."), 403)
        lobby.status = WerewolfLobby.STATUS_WAITING
        lobby.day_number = 0
        lobby.winner = ""
        lobby.phase_started_at = None
        lobby.save(update_fields=["status", "day_number", "winner", "phase_started_at", "updated_at"])
        lobby.players.update(role="", is_alive=True, vote_target=None, night_target=None, role_state={})
        lobby.messages.all().delete()
        _system(lobby, _("Eine neue Runde kann beginnen."))
    return JsonResponse(_serialize_lobby(lobby, request.user))


@login_required
@require_POST
def werewolf_leave(request, code):
    with transaction.atomic():
        lobby = get_object_or_404(WerewolfLobby.objects.select_for_update(), code=code.upper())
        player = lobby.players.filter(user=request.user).first()
        if not player:
            return redirect("werewolf_home")
        if lobby.status == WerewolfLobby.STATUS_WAITING:
            player.delete()
        else:
            player.is_alive = False
            player.save(update_fields=["is_alive"])
            _system(lobby, _("%(name)s hat das Spiel verlassen.") % {"name": player.display_label})
            _finish_if_needed(lobby)
        remaining = list(lobby.players.select_related("user").order_by("seat", "joined_at"))
        if not remaining:
            lobby.delete()
            return redirect("werewolf_home")
        if lobby.owner_id == request.user.id:
            lobby.owner = remaining[0].user
            lobby.save(update_fields=["owner", "updated_at"])
    return redirect("werewolf_home")


@login_required
@require_POST
def werewolf_delete(request, code):
    lobby = get_object_or_404(WerewolfLobby, code=code.upper())
    if lobby.owner_id != request.user.id:
        messages.error(request, _("Nur der Host kann die Lobby löschen."))
        return redirect("werewolf_home")
    lobby.delete()
    messages.success(request, _("Werwolf-Lobby wurde gelöscht."))
    return redirect("werewolf_home")
