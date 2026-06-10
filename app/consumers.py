import asyncio
import json
from contextlib import suppress

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import PongGame
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


ROOM_TICK_RATE = 1 / 45
_room_tasks = {}
_room_connections = {}
_room_lock = asyncio.Lock()


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
            game = PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right").filter(code=self.code).first()
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
            game = PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right").filter(code=self.code).first()
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
            game = PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right").filter(code=self.code).first()
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
        game = PongGame.objects.select_for_update().select_related("owner", "player_left", "player_right").filter(code=code).first()
        if not game:
            return False
        _ensure_game_ready(game)
        _tick_game(game)
        game.save()
        return True
