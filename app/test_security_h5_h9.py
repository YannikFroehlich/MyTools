from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from MyTools.asgi import application
from MyTools.settings import validate_production_backends
from app.consumers import ChatConsumer, PongConsumer
from app.image_optimization import MAX_IMAGE_PIXELS, validate_image_dimensions
from app.models import (
    AvatarCharacter,
    ChatMessage,
    ChatMessageRead,
    ChatRoom,
    ChatRoomMember,
    FileShare,
    SiteAccessSettings,
    UserSuspension,
)
from app.realtime import realtime_policy_group_name, realtime_user_group_name
from app.views.performance_tools import (
    MAX_FILE_SHARE_BATCH_BYTES,
    MAX_FILE_SHARE_FILES,
    _file_share_batch_error,
)


class ChatMembershipRevocationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="group-admin", password="testpass-123")
        self.member = user_model.objects.create_user(username="group-member", password="testpass-123")
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_GROUP,
            name="Security room",
            created_by=self.admin,
        )
        ChatRoomMember.objects.create(room=self.room, user=self.admin, is_admin=True)
        ChatRoomMember.objects.create(room=self.room, user=self.member)

    def _communicator(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.room.id}/")
        communicator.scope["url_route"] = {"kwargs": {"room_id": self.room.id}}
        communicator.scope["user"] = self.member
        return communicator

    def test_http_member_removal_immediately_closes_open_socket(self):
        def remove_member():
            self.client.force_login(self.admin)
            return self.client.post(
                reverse("chat_group_member_action", args=[self.room.id, self.member.id]),
                {"action": "remove"},
            ).status_code

        async def scenario():
            communicator = self._communicator()
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()

            status_code = await database_sync_to_async(remove_member)()
            self.assertEqual(status_code, 302)
            output = await communicator.receive_output(timeout=1)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)

        async_to_sync(scenario)()
        self.assertFalse(ChatRoomMember.objects.filter(room=self.room, user=self.member).exists())

    def test_message_event_rechecks_membership_before_payload_or_read_receipt(self):
        async def scenario():
            communicator = self._communicator()
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()

            await database_sync_to_async(
                ChatRoomMember.objects.filter(room=self.room, user=self.member).delete
            )()
            message = await database_sync_to_async(ChatMessage.objects.create)(
                room=self.room,
                sender=self.admin,
                text="secret after removal",
            )
            await get_channel_layer().group_send(
                f"chat_{self.room.id}",
                {"type": "chat.message_created", "message_id": message.id},
            )

            output = await communicator.receive_output(timeout=1)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)
            return message.id

        message_id = async_to_sync(scenario)()
        self.assertFalse(ChatMessageRead.objects.filter(message_id=message_id, user=self.member).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class WebSocketOriginTests(SimpleTestCase):
    def test_foreign_origin_is_rejected_before_consumer_connect(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                "/ws/chat/1/",
                headers=[
                    (b"host", b"testserver"),
                    (b"origin", b"https://evil.example"),
                ],
            )
            connected, _detail = await communicator.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()


class WebSocketPolicyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="policy-user", password="testpass-123")
        self.room = ChatRoom.objects.create(room_type=ChatRoom.ROOM_GROUP, name="Policy room")
        ChatRoomMember.objects.create(room=self.room, user=self.user)

    def _chat_communicator(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.room.id}/")
        communicator.scope["url_route"] = {"kwargs": {"room_id": self.room.id}}
        communicator.scope["user"] = self.user
        return communicator

    def test_suspended_user_cannot_connect(self):
        UserSuspension.objects.create(
            user=self.user,
            ends_at=timezone.now() + timedelta(hours=1),
        )

        async def scenario():
            communicator = self._chat_communicator()
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4403)

        async_to_sync(scenario)()

    def test_chat_and_pong_tool_rules_apply_at_connect(self):
        access_settings = SiteAccessSettings.get_solo()
        access_settings.set_tool_access_rules({
            "chat": SiteAccessSettings.TOOL_ACCESS_ADMIN,
            "pong": SiteAccessSettings.TOOL_ACCESS_ADMIN,
        })
        access_settings.save(update_fields=["tool_access_rules", "updated_at"])

        async def scenario():
            chat = self._chat_communicator()
            chat_connected, chat_code = await chat.connect()
            self.assertFalse(chat_connected)
            self.assertEqual(chat_code, 4403)

            pong = WebsocketCommunicator(PongConsumer.as_asgi(), "/ws/pong/ABC123/")
            pong.scope["url_route"] = {"kwargs": {"code": "ABC123"}}
            pong.scope["user"] = self.user
            pong_connected, pong_code = await pong.connect()
            self.assertFalse(pong_connected)
            self.assertEqual(pong_code, 4403)

        async_to_sync(scenario)()

    def test_open_socket_closes_after_suspension_event(self):
        async def scenario():
            communicator = self._chat_communicator()
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()

            await database_sync_to_async(UserSuspension.objects.create)(
                user=self.user,
                ends_at=timezone.now() + timedelta(hours=1),
            )
            await get_channel_layer().group_send(
                realtime_user_group_name(self.user.id),
                {"type": "realtime.access_revoked"},
            )
            output = await communicator.receive_output(timeout=1)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)

        async_to_sync(scenario)()

    def test_open_socket_closes_after_tool_policy_change(self):
        async def restrict_chat():
            access_settings = await database_sync_to_async(SiteAccessSettings.get_solo)()
            access_settings.set_tool_access_rules({"chat": SiteAccessSettings.TOOL_ACCESS_ADMIN})
            await database_sync_to_async(access_settings.save)(
                update_fields=["tool_access_rules", "updated_at"]
            )

        async def scenario():
            communicator = self._chat_communicator()
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()

            await restrict_chat()
            await get_channel_layer().group_send(
                realtime_policy_group_name(),
                {"type": "realtime.policy_changed"},
            )
            output = await communicator.receive_output(timeout=1)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)

        async_to_sync(scenario)()


class UploadAndConverterResourceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="upload-user", password="testpass-123")
        self.client.force_login(self.user)

    def test_file_share_rejects_more_than_ten_files_without_objects(self):
        uploads = [
            SimpleUploadedFile(f"file-{index}.txt", b"x", content_type="text/plain")
            for index in range(MAX_FILE_SHARE_FILES + 1)
        ]
        response = self.client.post(
            reverse("file_share_upload"),
            {"is_public_link": "on", "files": uploads},
        )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(FileShare.objects.filter(owner=self.user).exists())

    def test_file_share_batch_limit_uses_total_declared_size(self):
        uploads = [
            SimpleNamespace(size=MAX_FILE_SHARE_BATCH_BYTES // 2 + 1),
            SimpleNamespace(size=MAX_FILE_SHARE_BATCH_BYTES // 2 + 1),
        ]
        self.assertIsNotNone(_file_share_batch_error(uploads))

    def test_file_share_quota_rejects_before_new_file_is_stored(self):
        FileShare.objects.create(
            owner=self.user,
            file="private/file_shares/existing.txt",
            original_name="existing.txt",
            size=5,
            content_type="application/octet-stream",
            token="existing-quota-file",
        )
        with patch("app.views.performance_tools.MAX_FILE_SHARE_USER_QUOTA_BYTES", 5):
            response = self.client.post(
                reverse("file_share_upload"),
                {
                    "is_public_link": "on",
                    "files": SimpleUploadedFile("new.txt", b"x", content_type="text/plain"),
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(FileShare.all_objects.filter(owner=self.user).count(), 1)

    def test_avatar_wiki_rejects_oversized_image_before_model_creation(self):
        with patch("app.views.tools.MAX_AVATAR_WIKI_UPLOAD_SIZE", 1):
            response = self.client.post(
                reverse("avatar-characters-api"),
                {
                    "name": "Oversized",
                    "nation": "Feuer",
                    "image": SimpleUploadedFile("avatar.png", b"xx", content_type="image/png"),
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(AvatarCharacter.objects.filter(user=self.user).exists())

    def test_extreme_image_dimensions_raise_decompression_bomb_error(self):
        image = SimpleNamespace(width=MAX_IMAGE_PIXELS + 1, height=1)
        with self.assertRaises(Image.DecompressionBombError):
            validate_image_dimensions(image)

    def test_decompression_bomb_file_share_is_not_persisted(self):
        with patch(
            "app.views.performance_tools.prepare_untrusted_upload",
            side_effect=Image.DecompressionBombError("too many pixels"),
        ):
            response = self.client.post(
                reverse("file_share_upload"),
                {
                    "is_public_link": "on",
                    "files": SimpleUploadedFile("bomb.png", b"png", content_type="image/png"),
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(FileShare.objects.filter(owner=self.user).exists())

    def test_oversized_converter_output_is_rejected(self):
        def return_source(source_path, target):
            return source_path

        with (
            patch("app.views.file_converter.MAX_CONVERTER_OUTPUT_SIZE", 0),
            patch("app.views.file_converter._convert_image", side_effect=return_source),
        ):
            response = self.client.post(
                reverse("file_converter"),
                {
                    "target": "png",
                    "file": SimpleUploadedFile("image.png", b"x", content_type="image/png"),
                },
            )

        self.assertEqual(response.status_code, 413)


class ProductionBackendGuardTests(SimpleTestCase):
    def test_production_rejects_sqlite_and_local_cache(self):
        for use_sqlite, use_local_cache in ((True, False), (False, True), (True, True)):
            with self.subTest(use_sqlite=use_sqlite, use_local_cache=use_local_cache):
                with self.assertRaises(ImproperlyConfigured):
                    validate_production_backends(
                        debug=False,
                        is_testing=False,
                        use_sqlite=use_sqlite,
                        use_local_cache=use_local_cache,
                    )

    def test_development_tests_and_management_commands_may_use_local_backends(self):
        validate_production_backends(
            debug=True,
            is_testing=False,
            use_sqlite=True,
            use_local_cache=True,
        )
        validate_production_backends(
            debug=False,
            is_testing=True,
            use_sqlite=True,
            use_local_cache=True,
        )
        validate_production_backends(
            debug=False,
            is_testing=False,
            is_management_command=True,
            use_sqlite=True,
            use_local_cache=True,
        )

    def test_deployment_files_pin_safe_backends_and_resource_limits(self):
        compose = (settings.BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
        dockerfile = (settings.BASE_DIR / "Dockerfile").read_text(encoding="utf-8")
        caddyfile = (settings.BASE_DIR / "Caddyfile").read_text(encoding="utf-8")

        self.assertIn('USE_SQLITE: "False"', compose)
        self.assertIn('USE_LOCAL_CACHE: "False"', compose)
        self.assertIn("condition: service_healthy", compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("image: caddy:2.10-alpine", compose)
        self.assertIn("USER mytools", dockerfile)
        self.assertIn("request_body", caddyfile)
        self.assertIn("max_size 110MB", caddyfile)
