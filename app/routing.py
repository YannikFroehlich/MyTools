from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/pong/<str:code>/", consumers.PongConsumer.as_asgi()),
]
