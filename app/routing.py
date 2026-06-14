from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/live-status/", consumers.LiveStatusConsumer.as_asgi()),
    path("ws/chat/<int:room_id>/", consumers.ChatConsumer.as_asgi()),
    path("ws/pong/<str:code>/", consumers.PongConsumer.as_asgi()),
]
