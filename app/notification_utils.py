from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    BattleshipInvite,
    BattleshipGame,
    ChatMessage,
    ChatRoomMember,
    ConnectFourGame,
    ConnectFourInvite,
    DrawingGameInvite,
    DrawingGameLobby,
    FileShare,
    Friendship,
    HangmanInvite,
    KniffelGame,
    KniffelInvite,
    Note,
    PongGame,
    PongInvite,
    NotificationDismissal,
    StadtLandFlussLobby,
    StadtLandFlussInvite,
    StadtLandFlussPlayer,
    StadtLandFlussRoundAnswer,
    TicTacToeGame,
    TicTacToeInvite,
    UnoGame,
    UnoInvite,
    UserProfile,
)

COUNT_KEYS = (
    "unread_chat_messages",
    "note_reminders",
    "incoming_friend_requests",
    "shared_files",
    "game_turns",
    "skribble_invites",
    "tictactoe_invites",
    "connectfour_invites",
    "battleship_invites",
    "stadtlandfluss_invites",
    "uno_invites",
    "kniffel_invites",
    "hangman_invites",
    "pong_invites",
)

TYPE_COUNT_KEY = {
    "chat": "unread_chat_messages",
    "reminder": "note_reminders",
    "friend": "incoming_friend_requests",
    "file_share": "shared_files",
    "game_turn": "game_turns",
    "skribble": "skribble_invites",
    "tictactoe": "tictactoe_invites",
    "connectfour": "connectfour_invites",
    "battleship": "battleship_invites",
    "stadtlandfluss": "stadtlandfluss_invites",
    "uno": "uno_invites",
    "kniffel": "kniffel_invites",
    "hangman": "hangman_invites",
    "pong": "pong_invites",
}

NOTIFICATION_CACHE_VERSION = 2
NOTIFICATION_COUNT_CACHE_SECONDS = 6
NOTIFICATION_ITEM_CACHE_SECONDS = 5


def _notification_cache_key(user, suffix):
    return f"notifications:v{NOTIFICATION_CACHE_VERSION}:u{getattr(user, 'pk', 'anonymous')}:{suffix}"


def invalidate_notification_cache(user):
    if not getattr(user, "is_authenticated", False):
        return

    cache.delete_many([
        _notification_cache_key(user, "counts"),
        _notification_cache_key(user, "items:10"),
        _notification_cache_key(user, "items:12"),
        _notification_cache_key(user, "items:1000"),
    ])


def empty_notification_counts():
    counts = {key: 0 for key in COUNT_KEYS}
    counts["total_notifications"] = 0
    return counts


def dismissed_notification_keys(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(NotificationDismissal.objects.filter(user=user).values_list("key", flat=True))


def _is_visible(item, dismissed_keys):
    return item.get("key") not in dismissed_keys


def _add_invite_items(items, qs, *, item_type, icon, title, text_template, url_name, object_attr, dismissed_keys, limit):
    added = 0
    for invite in qs:
        game_object = getattr(invite, object_attr)
        key = f"{item_type}:{invite.pk}"
        if key in dismissed_keys:
            continue
        items.append({
            "key": key,
            "type": item_type,
            "icon": icon,
            "title": title,
            "text": text_template % {"user": invite.from_user.username, "name": game_object.name},
            "url": reverse(url_name, args=[game_object.code]),
            "action_label": _("Beitreten"),
            "created_at": invite.created_at,
            "badge": 1,
        })
        added += 1
        if added >= limit:
            break


def _timestamp_key(value):
    if not value:
        return "new"
    return str(int(value.timestamp()))


def _add_game_turn_item(items, *, game, key_type, icon, title, text, url_name, dismissed_keys):
    created_at = getattr(game, "last_move_at", None) or getattr(game, "updated_at", None) or getattr(game, "created_at", None)
    key = f"game-turn:{key_type}:{game.pk}:{getattr(game, 'round_number', getattr(game, 'current_round_number', 1))}:{_timestamp_key(created_at)}"
    if key in dismissed_keys:
        return
    items.append({
        "key": key,
        "type": "game_turn",
        "icon": icon,
        "title": title,
        "text": text,
        "url": reverse(url_name, args=[game.code]),
        "action_label": _("Zum Spiel"),
        "created_at": created_at,
        "badge": 1,
    })


def _current_seated_player(players, current_index):
    players = list(players)
    if not players:
        return None
    return players[current_index % len(players)]


def _collect_reminder_items(user, dismissed_keys, limit):
    now = timezone.now()
    items = []
    notes = (
        Note.objects
        .filter(
            Q(user=user) | Q(shared_with=user),
            is_archived=False,
            reminder_at__isnull=False,
            reminder_at__lte=now,
        )
        .select_related("user")
        .distinct()
        .order_by("-reminder_at", "-updated_at")
    )

    for note in notes:
        key = f"reminder:{note.pk}:{_timestamp_key(note.reminder_at)}"
        if key in dismissed_keys:
            continue
        title = (note.title or _("Unbenannte Notiz"))[:80]
        if note.user_id == user.id:
            text = _("Deine Erinnerung ist fällig.")
        else:
            text = _("Geteilte Notiz von %(user)s ist fällig.") % {"user": note.user.username}
        items.append({
            "key": key,
            "type": "reminder",
            "icon": "fa-regular fa-bell",
            "title": title,
            "text": text,
            "url": reverse("note_detail", args=[note.pk]),
            "action_label": _("Öffnen"),
            "created_at": note.reminder_at,
            "badge": 1,
        })
        if len(items) >= limit:
            break
    return items


def _collect_file_share_items(user, dismissed_keys, limit):
    items = []
    shares = (
        FileShare.objects
        .filter(recipients=user)
        .exclude(owner=user)
        .select_related("owner")
        .order_by("-created_at")
    )

    for share in shares:
        key = f"file-share:{share.pk}"
        if key in dismissed_keys:
            continue
        items.append({
            "key": key,
            "type": "file_share",
            "icon": share.icon_class,
            "title": _("Neue Dateifreigabe"),
            "text": _("%(user)s hat %(file)s mit dir geteilt") % {
                "user": share.owner.username,
                "file": share.original_name,
            },
            "url": reverse("file_share"),
            "action_label": _("Ansehen"),
            "created_at": share.created_at,
            "badge": 1,
        })
        if len(items) >= limit:
            break
    return items


def _collect_game_turn_items(user, dismissed_keys, limit):
    items = []

    for game in TicTacToeGame.objects.filter(status=TicTacToeGame.STATUS_PLAYING).filter(Q(player_x=user) | Q(player_o=user)):
        if game.symbol_for_user(user) == game.current_symbol:
            _add_game_turn_item(
                items,
                game=game,
                key_type="tictactoe",
                icon="fa-solid fa-table-cells",
                title=_("Tic Tac Toe"),
                text=_("Du bist am Zug in %(name)s.") % {"name": game.name},
                url_name="tictactoe_lobby",
                dismissed_keys=dismissed_keys,
            )

    for game in ConnectFourGame.objects.filter(status=ConnectFourGame.STATUS_PLAYING).filter(Q(player_red=user) | Q(player_yellow=user)):
        if game.disc_for_user(user) == game.current_disc:
            _add_game_turn_item(
                items,
                game=game,
                key_type="connectfour",
                icon="fa-solid fa-grip",
                title=_("Vier gewinnt"),
                text=_("Du bist am Zug in %(name)s.") % {"name": game.name},
                url_name="connectfour_lobby",
                dismissed_keys=dismissed_keys,
            )

    for game in BattleshipGame.objects.filter(status__in=[BattleshipGame.STATUS_SETUP, BattleshipGame.STATUS_PLAYING]).filter(Q(player_a=user) | Q(player_b=user)):
        side = game.side_for_user(user)
        if game.status == BattleshipGame.STATUS_SETUP:
            is_ready = (side == BattleshipGame.SIDE_A and game.ready_a) or (side == BattleshipGame.SIDE_B and game.ready_b)
            if not is_ready:
                _add_game_turn_item(
                    items,
                    game=game,
                    key_type="battleship-setup",
                    icon="fa-solid fa-anchor",
                    title=_("Schiffe versenken"),
                    text=_("Platziere deine Flotte in %(name)s.") % {"name": game.name},
                    url_name="battleship_lobby",
                    dismissed_keys=dismissed_keys,
                )
        elif side == game.current_turn:
            _add_game_turn_item(
                items,
                game=game,
                key_type="battleship",
                icon="fa-solid fa-anchor",
                title=_("Schiffe versenken"),
                text=_("Du bist am Zug in %(name)s.") % {"name": game.name},
                url_name="battleship_lobby",
                dismissed_keys=dismissed_keys,
            )

    for game in UnoGame.objects.filter(status=UnoGame.STATUS_PLAYING, players__user=user).distinct().prefetch_related("players__user"):
        current = _current_seated_player(game.players.all(), game.current_player_index)
        if current and current.user_id == user.id:
            _add_game_turn_item(
                items,
                game=game,
                key_type="uno",
                icon="fa-solid fa-layer-group",
                title=_("Uno"),
                text=_("Du bist am Zug in %(name)s.") % {"name": game.name},
                url_name="uno_lobby",
                dismissed_keys=dismissed_keys,
            )

    for game in KniffelGame.objects.filter(status=KniffelGame.STATUS_PLAYING, players__user=user).distinct().prefetch_related("players__user"):
        current = _current_seated_player(game.players.all(), game.current_player_index)
        if current and current.user_id == user.id:
            _add_game_turn_item(
                items,
                game=game,
                key_type="kniffel",
                icon="fa-solid fa-dice",
                title=_("Kniffel"),
                text=_("Du bist am Zug in %(name)s.") % {"name": game.name},
                url_name="kniffel_lobby",
                dismissed_keys=dismissed_keys,
            )

    for lobby in StadtLandFlussLobby.objects.filter(status=StadtLandFlussLobby.STATUS_PLAYING, players__user=user).distinct():
        player = StadtLandFlussPlayer.objects.filter(lobby=lobby, user=user).first()
        has_submitted = False
        if player:
            has_submitted = StadtLandFlussRoundAnswer.objects.filter(
                lobby=lobby,
                player=player,
                round_number=lobby.current_round_number,
                is_submitted=True,
            ).exists()
        if player and not has_submitted:
            _add_game_turn_item(
                items,
                game=lobby,
                key_type="stadtlandfluss",
                icon="fa-solid fa-pen-to-square",
                title=_("Stadt Land Fluss"),
                text=_("Runde %(round)s wartet auf deine Antworten.") % {"round": lobby.current_round_number},
                url_name="stadtlandfluss_lobby",
                dismissed_keys=dismissed_keys,
            )

    for lobby in DrawingGameLobby.objects.filter(status=DrawingGameLobby.STATUS_PLAYING, players__user=user).distinct().prefetch_related("players__user"):
        current_drawer = _current_seated_player(lobby.players.all(), lobby.current_turn_index)
        if current_drawer and current_drawer.user_id == user.id:
            action_text = _("Wähle ein Wort in %(name)s.") if not lobby.current_word else _("Du zeichnest gerade in %(name)s.")
            _add_game_turn_item(
                items,
                game=lobby,
                key_type="skribble",
                icon="fa-solid fa-pencil",
                title=_("Skribble"),
                text=action_text % {"name": lobby.name},
                url_name="skribble_lobby",
                dismissed_keys=dismissed_keys,
            )

    items.sort(key=lambda item: item.get("created_at") or timezone.now(), reverse=True)
    return items[:limit]


def _collect_notification_items(user, *, limit=10, include_dismissed=False):
    if not getattr(user, "is_authenticated", False):
        return []

    profile, _created = UserProfile.objects.get_or_create(user=user)
    muted_by_dnd = profile.status == UserProfile.STATUS_DND and profile.dnd_silence_notifications
    dismissed_keys = set() if include_dismissed else dismissed_notification_keys(user)
    items = []

    if profile.notify_chat and not muted_by_dnd:
        for membership in ChatRoomMember.objects.filter(user=user).select_related("room"):
            qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user).select_related("sender").order_by("-created_at")
            if membership.last_read_at:
                qs = qs.filter(created_at__gt=membership.last_read_at)
            unread_count = qs.count()
            latest = qs.first()
            if unread_count and latest:
                key = f"chat:{membership.room_id}:{latest.pk}"
                if key in dismissed_keys:
                    continue
                room_title = membership.room.title_for(user)
                items.append({
                    "key": key,
                    "type": "chat",
                    "icon": "fa-solid fa-comments",
                    "title": room_title,
                    "text": _("%(count)s ungelesene Nachricht(en) von %(user)s") % {"count": unread_count, "user": latest.sender.username},
                    "url": reverse("chat_room", args=[membership.room_id]),
                    "action_label": _("Zum Chat"),
                    "created_at": latest.created_at,
                    "badge": unread_count,
                })

    if not muted_by_dnd:
        items.extend(_collect_reminder_items(user, dismissed_keys, limit))
        items.extend(_collect_file_share_items(user, dismissed_keys, limit))
        items.extend(_collect_game_turn_items(user, dismissed_keys, limit))

    if profile.notify_friend_requests and not muted_by_dnd:
        added = 0
        friendships = Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).select_related("from_user").order_by("-created_at")
        for friendship in friendships:
            key = f"friend:{friendship.pk}"
            if key in dismissed_keys:
                continue
            items.append({
                "key": key,
                "type": "friend",
                "icon": "fa-solid fa-user-plus",
                "title": _("Freundschaftsanfrage"),
                "text": _("%(user)s möchte mit dir befreundet sein") % {"user": friendship.from_user.username},
                "url": reverse("profile") + "#friend-requests",
                "action_label": _("Ansehen"),
                "created_at": friendship.created_at,
                "badge": 1,
            })
            added += 1
            if added >= limit:
                break

    if profile.notify_skribble and not muted_by_dnd:
        _add_invite_items(
            items,
            DrawingGameInvite.objects.filter(to_user=user, status=DrawingGameInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="skribble",
            icon="fa-solid fa-pencil",
            title=_("Skribble-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="skribble_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            TicTacToeInvite.objects.filter(to_user=user, status=TicTacToeInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="tictactoe",
            icon="fa-solid fa-table-cells",
            title=_("Tic-Tac-Toe-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="tictactoe_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            ConnectFourInvite.objects.filter(to_user=user, status=ConnectFourInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="connectfour",
            icon="fa-solid fa-grip",
            title=_("Vier-gewinnt-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="connectfour_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            BattleshipInvite.objects.filter(to_user=user, status=BattleshipInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="battleship",
            icon="fa-solid fa-anchor",
            title=_("Schiffe-versenken-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="battleship_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            StadtLandFlussInvite.objects.filter(to_user=user, status=StadtLandFlussInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="stadtlandfluss",
            icon="fa-solid fa-pen-to-square",
            title=_("Stadt-Land-Fluss-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="stadtlandfluss_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            UnoInvite.objects.filter(to_user=user, status=UnoInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="uno",
            icon="fa-solid fa-layer-group",
            title=_("Uno-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="uno_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            KniffelInvite.objects.filter(to_user=user, status=KniffelInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="kniffel",
            icon="fa-solid fa-dice",
            title=_("Kniffel-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="kniffel_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            HangmanInvite.objects.filter(to_user=user, status=HangmanInvite.STATUS_PENDING).select_related("lobby", "from_user").order_by("-created_at"),
            item_type="hangman",
            icon="fa-solid fa-user-secret",
            title=_("Hangman-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="hangman_lobby",
            object_attr="lobby",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )
        _add_invite_items(
            items,
            PongInvite.objects.filter(to_user=user, status=PongInvite.STATUS_PENDING).select_related("game", "from_user").order_by("-created_at"),
            item_type="pong",
            icon="fa-solid fa-table-tennis-paddle-ball",
            title=_("Pong-Einladung"),
            text_template=_("%(user)s hat dich in %(name)s eingeladen"),
            url_name="pong_lobby",
            object_attr="game",
            dismissed_keys=dismissed_keys,
            limit=limit,
        )

    items.sort(key=lambda item: item.get("created_at") or timezone.now(), reverse=True)
    return items


def _build_notification_counts(user):
    counts = empty_notification_counts()

    for item in _collect_notification_items(user, limit=1000):
        count_key = TYPE_COUNT_KEY.get(item.get("type"))
        if count_key:
            counts[count_key] += int(item.get("badge") or 1)

    counts["total_notifications"] = sum(counts[key] for key in COUNT_KEYS)
    return counts


def get_notification_counts(user, *, use_cache=True):
    """Return all small header notification counters for the current user.

    These counters are shown on nearly every page. A very short cache keeps
    header rendering and live polling cheap while staying responsive enough
    for chat/game notifications.
    """
    if not getattr(user, "is_authenticated", False):
        return empty_notification_counts()

    cache_key = _notification_cache_key(user, "counts")

    if use_cache:
        cached_counts = cache.get(cache_key)
        if cached_counts is not None:
            return cached_counts

    counts = _build_notification_counts(user)
    cache.set(cache_key, counts, NOTIFICATION_COUNT_CACHE_SECONDS)
    return counts


def get_notification_items(user, limit=10, *, use_cache=True):
    if not getattr(user, "is_authenticated", False):
        return []

    normalized_limit = max(1, min(int(limit or 10), 1000))
    cache_key = _notification_cache_key(user, f"items:{normalized_limit}")

    if use_cache:
        cached_items = cache.get(cache_key)
        if cached_items is not None:
            return cached_items

    items = _collect_notification_items(user, limit=normalized_limit)[:normalized_limit]
    cache.set(cache_key, items, NOTIFICATION_ITEM_CACHE_SECONDS)
    return items
