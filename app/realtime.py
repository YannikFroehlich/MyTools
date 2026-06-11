"""Small helpers for optional realtime fan-out via Django Channels.

The normal HTTP endpoints stay as a fallback. These helpers only broadcast a
lightweight event to connected WebSocket clients so pages do not need to poll as
frequently when Channels/Redis is available.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_group(group_name, event):
    """Send an event to a Channels group and silently skip unavailable layers."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return False

    async_to_sync(channel_layer.group_send)(group_name, event)
    return True


def chat_group_name(room_id):
    return f"chat_{int(room_id)}"


def broadcast_chat_event(room_id, event_name, **payload):
    """Broadcast a chat event to all open tabs in a room."""
    event = {"type": f"chat.{event_name}", **payload}
    return broadcast_group(chat_group_name(room_id), event)
