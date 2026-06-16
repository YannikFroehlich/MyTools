import asyncio
import json
from contextlib import suppress
from types import SimpleNamespace

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import ChatMessage, ChatRoom, ChatRoomMember, ChatTypingStatus, PongGame
from .chat_views import mark_room_messages_read, message_payload, pinned_message_for, typing_payload
from .notification_utils import invalidate_notification_cache
from .notification_views import _notification_payload, _presence_payload
from .presence_utils import touch_user_presence
from .pong_views import (
    FIELD_H,
    PADDLE_H,
    _clamp,
    _ensure_game_ready,
    _mark_player_seen,
    _reset_ball,
    _serialize_game,
    _tick_game,
)
from .realtime import live_presence_group_name, live_status_group_name


ROOM_TICK_RATE = 1 / 45
_room_tasks = {}
_room_connections = {}
_room_lock = asyncio.Lock()


class LiveStatusConsumer(AsyncWebsocketConsumer):
    """Global realtime channel for header badges, notifications and presence.

    HTTP polling remains as a fallback in base.js. This socket pushes the same
    payload when something relevant changes, so open pages react immediately
    without waiting for the next polling interval.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        self.include_items = False
        self.presence_ids = []

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = live_status_group_name(self.user.id)
        self.presence_group_name = live_presence_group_name()

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(self.presence_group_name, self.channel_name)
        await self.accept()
        await self._touch_presence()
        await self.send_live_status(reason="connected")
        await self.channel_layer.group_send(
            self.presence_group_name,
            {"type": "live.presence_changed", "user_id": self.user.id},
        )

    async def disconnect(self, close_code):
        with suppress(Exception):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        with suppress(Exception):
            await self.channel_layer.group_discard(self.presence_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = payload.get("action")
        if action == "configure":
            self.include_items = bool(payload.get("includeItems") or payload.get("include_items"))
            self.presence_ids = self._normalize_presence_ids(payload.get("presenceIds") or payload.get("presence_ids"))
            await self.send_live_status(reason="configured")
        elif action == "refresh":
            include_items = payload.get("includeItems") if "includeItems" in payload else payload.get("include_items")
            await self.send_live_status(
                reason="manual",
                include_items=self.include_items if include_items is None else bool(include_items),
            )
        elif action == "ping":
            await self._touch_presence()
            await self.channel_layer.group_send(
                self.presence_group_name,
                {"type": "live.presence_changed", "user_id": self.user.id},
            )
            await self.send_json({"type": "pong"})

    async def live_status_changed(self, event):
        await self.send_live_status(reason=event.get("reason", "changed"))

    async def live_presence_changed(self, event):
        try:
            user_id = int(event.get("user_id"))
        except (TypeError, ValueError):
            return

        if user_id not in self.presence_ids:
            return

        profiles = await self._presence_payload([user_id])
        if profiles:
            await self.send_json({"type": "presence", "profiles": profiles})

    async def send_live_status(self, *, reason="refresh", include_items=None):
        payload = await self._live_status_payload(
            self.include_items if include_items is None else bool(include_items)
        )
        payload["type"] = "live_status"
        payload["reason"] = reason
        await self.send_json(payload)

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    def _normalize_presence_ids(self, raw_ids):
        if not isinstance(raw_ids, list):
            return []

        normalized_ids = []
        for raw_id in raw_ids:
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                continue

            if user_id not in normalized_ids:
                normalized_ids.append(user_id)

            if len(normalized_ids) >= 50:
                break

        return normalized_ids

    @database_sync_to_async
    def _touch_presence(self):
        touch_user_presence(self.user)

    @database_sync_to_async
    def _live_status_payload(self, include_items):
        request = SimpleNamespace(user=self.user)
        payload = _notification_payload(self.user, include_items=include_items)
        payload["profiles"] = _presence_payload(request, list(self.presence_ids))
        return payload

    @database_sync_to_async
    def _presence_payload(self, user_ids):
        request = SimpleNamespace(user=self.user)
        return _presence_payload(request, user_ids)




class ChatConsumer(AsyncWebsocketConsumer):
    """Realtime chat room channel with HTTP fallback.

    Messages are still created/edited/deleted through the existing HTTP views so
    file uploads, CSRF checks and validation stay unchanged. This socket only
    fans out events and typing state to reduce polling.
    """

    async def connect(self):
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.group_name = f"chat_{self.room_id}"
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        if not await self._can_join_room():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "roomId": self.room_id})

    async def disconnect(self, close_code):
        with suppress(Exception):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = payload.get("action")
        if action == "typing":
            is_typing = bool(payload.get("isTyping"))
            await self._set_typing(is_typing)
            await self.channel_layer.group_send(self.group_name, {"type": "chat.typing"})
        elif action == "ping":
            await self.send_json({"type": "pong"})

    async def chat_message_created(self, event):
        payload = await self._message_payload(event.get("message_id"))
        if not payload:
            return
        if not payload.get("is_own"):
            await self._mark_room_read()
        await self.send_json({"type": "message_created", "message": payload})

    async def chat_message_updated(self, event):
        payload = await self._message_payload(event.get("message_id"))
        if payload:
            await self.send_json({"type": "message_updated", "message": payload})

    async def chat_message_deleted(self, event):
        await self.send_json({"type": "message_deleted", "deletedIds": [event.get("message_id")]})

    async def chat_reaction_updated(self, event):
        update = await self._reaction_update(event.get("message_id"))
        if update:
            await self.send_json({"type": "message_updated", "message": update})

    async def chat_pinned_updated(self, event):
        payload = await self._pinned_payload()
        await self.send_json({"type": "pinned_updated", "pinnedMessage": payload})

    async def chat_typing(self, event):
        await self.send_json({"type": "typing", "typingUsers": await self._typing_payload()})

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def _can_join_room(self):
        return ChatRoomMember.objects.filter(room_id=self.room_id, user=self.user).exists()

    @database_sync_to_async
    def _set_typing(self, is_typing):
        ChatTypingStatus.objects.update_or_create(
            room_id=self.room_id,
            user=self.user,
            defaults={"is_typing": is_typing},
        )

    @database_sync_to_async
    def _message_payload(self, message_id):
        if not message_id:
            return None
        message = (
            ChatMessage.objects
            .filter(id=message_id, room_id=self.room_id)
            .select_related("room", "sender", "sender__profile")
            .prefetch_related("reactions", "attachments", "read_receipts")
            .first()
        )
        if not message:
            return None
        return message_payload(message, self.user, message.room.pinned_message_id)

    @database_sync_to_async
    def _reaction_update(self, message_id):
        if not message_id:
            return None
        message = (
            ChatMessage.objects
            .filter(id=message_id, room_id=self.room_id)
            .select_related("room", "sender", "sender__profile")
            .prefetch_related("reactions", "attachments", "read_receipts")
            .first()
        )
        if not message:
            return None
        payload = message_payload(message, self.user, message.room.pinned_message_id)
        return {
            "id": payload["id"],
            "text": payload["text"],
            "edited_at": payload["edited_at"],
            "is_edited": payload["is_edited"],
            "reactions": payload["reactions"],
            "read_label": payload["read_label"],
            "is_pinned": payload["is_pinned"],
        }

    @database_sync_to_async
    def _pinned_payload(self):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        if not room:
            return None
        pinned_message = pinned_message_for(room, self.user)
        return message_payload(pinned_message, self.user, room.pinned_message_id) if pinned_message else None

    @database_sync_to_async
    def _typing_payload(self):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        return typing_payload(room, self.user) if room else []

    @database_sync_to_async
    def _mark_room_read(self):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        if not room:
            return False
        did_mark = mark_room_messages_read(room, self.user)
        if did_mark:
            ChatRoomMember.objects.filter(room=room, user=self.user).update(last_read_at=timezone.now())
            invalidate_notification_cache(self.user)
        return did_mark

class PongConsumer(AsyncWebsocketConsumer):
    """Realtime Pong channel.

    The HTTP endpoints still exist as a fallback, but active matches use this
    consumer so both browsers receive the same authoritative game state from
    the server instead of polling at different moments.
    """

    async def connect(self):
        self.code = self.scope["url_route"]["kwargs"]["code"].upper()
        self.group_name = f"pong_{self.code}"
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        can_connect = await self._touch_player()
        if not can_connect:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._increment_room_connections()
        await self._ensure_room_loop()
        await self.send_state()

    async def disconnect(self, close_code):
        with suppress(Exception):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self._decrement_room_connections()

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = payload.get("action")
        if action == "paddle":
            await self._update_paddle(payload.get("y"))
        elif action == "reset":
            ok = await self._reset_round()
            if ok:
                await self.channel_layer.group_send(self.group_name, {"type": "pong.state"})
            else:
                await self.send_json({"type": "error", "error": str(_("Nur der Host kann eine neue Runde starten."))})
        elif action == "ping":
            await self._touch_player()
            await self.send_json({"type": "pong"})

    async def pong_state(self, event):
        game_payload = await self._state_for_user()
        if not game_payload:
            await self.send_json({
                "type": "deleted",
                "error": str(_("Dieser Pong-Raum wurde gelöscht.")),
                "redirectUrl": reverse("pong_home"),
            })
            return
        await self.send_json({"type": "state", "game": game_payload})

    async def pong_deleted(self, event):
        await self.send_json({
            "type": "deleted",
            "error": event.get("error") or str(_("Dieser Pong-Raum wurde gelöscht.")),
            "redirectUrl": reverse("pong_home"),
        })

    async def send_state(self):
        game_payload = await self._state_for_user()
        if game_payload:
            await self.send_json({"type": "state", "game": game_payload})

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    async def _increment_room_connections(self):
        async with _room_lock:
            _room_connections[self.code] = _room_connections.get(self.code, 0) + 1

    async def _decrement_room_connections(self):
        async with _room_lock:
            current = max(_room_connections.get(self.code, 1) - 1, 0)
            if current:
                _room_connections[self.code] = current
            else:
                _room_connections.pop(self.code, None)

    async def _ensure_room_loop(self):
        async with _room_lock:
            task = _room_tasks.get(self.code)
            if task and not task.done():
                return
            _room_tasks[self.code] = asyncio.create_task(_room_loop(self.channel_layer, self.code, self.group_name))

    @database_sync_to_async
    def _touch_player(self):
        with transaction.atomic():
            game = PongGame.objects.select_for_update(of=("self",)).select_related("owner", "player_left", "player_right").filter(code=self.code).first()
            if not game:
                return False
            if not game.side_for_user(self.user):
                return False
            _mark_player_seen(game, self.user)
            _ensure_game_ready(game)
            return True

    @database_sync_to_async
    def _state_for_user(self):
        game = PongGame.objects.select_related("owner", "player_left", "player_right").filter(code=self.code).first()
        if not game:
            return None
        return _serialize_game(game, self.user)

    @database_sync_to_async
    def _update_paddle(self, raw_y):
        try:
            y = float(raw_y)
        except (TypeError, ValueError):
            return False
        y = _clamp(y, PADDLE_H / 2, FIELD_H - PADDLE_H / 2)
        with transaction.atomic():
            game = PongGame.objects.select_for_update(of=("self",)).select_related("owner", "player_left", "player_right").filter(code=self.code).first()
            if not game:
                return False
            side = game.side_for_user(self.user)
            if not side:
                return False
            now = timezone.now()
            if side == PongGame.SIDE_LEFT:
                game.paddle_left_y = y
                game.player_left_last_seen = now
            else:
                game.paddle_right_y = y
                game.player_right_last_seen = now
            game.save(update_fields=[
                "paddle_left_y", "paddle_right_y",
                "player_left_last_seen", "player_right_last_seen", "updated_at",
            ])
        return True

    @database_sync_to_async
    def _reset_round(self):
        with transaction.atomic():
            game = PongGame.objects.select_for_update(of=("self",)).select_related("owner", "player_left", "player_right").filter(code=self.code).first()
            if not game or game.owner_id != self.user.id:
                return False
            game.score_left = 0
            game.score_right = 0
            game.winner_side = ""
            game.paddle_left_y = 50.0
            game.paddle_right_y = 50.0
            game.round_number += 1
            game.status = PongGame.STATUS_PLAYING if game.player_left_id and game.player_right_id else PongGame.STATUS_WAITING
            _reset_ball(game)
            game.save()
        return True


async def _room_loop(channel_layer, code, group_name):
    try:
        while True:
            await asyncio.sleep(ROOM_TICK_RATE)
            if _room_connections.get(code, 0) <= 0:
                break
            exists = await _tick_room(code)
            if not exists:
                await channel_layer.group_send(group_name, {
                    "type": "pong.deleted",
                    "error": str(_("Dieser Pong-Raum wurde gelöscht.")),
                })
                break
            await channel_layer.group_send(group_name, {"type": "pong.state"})
    finally:
        async with _room_lock:
            task = _room_tasks.get(code)
            if task is asyncio.current_task():
                _room_tasks.pop(code, None)


@database_sync_to_async
def _tick_room(code):
    with transaction.atomic():
        game = PongGame.objects.select_for_update(of=("self",)).select_related("owner", "player_left", "player_right").filter(code=code).first()
        if not game:
            return False
        _ensure_game_ready(game)
        _tick_game(game)
        game.save()
        return True
