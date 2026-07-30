import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from allauth.core.exceptions import ImmediateHttpResponse
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from app.adapters import MyToolsSocialAccountAdapter
from app.consumers import ChatConsumer
from app.models import (
    AvatarCharacter,
    ChatAttachment,
    ChatMessage,
    ChatRoom,
    ChatRoomMember,
    FileShare,
    Shortcut,
    ShortcutSection,
    UserBlock,
    UserTwoFactorSettings,
)
from app.rate_limits import check_rate_limit, rule_for_request
from app.views.media import public_media


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="mytools-security-tests-")


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


def raster_upload(name="image.png"):
    buffer = BytesIO()
    Image.new("RGB", (24, 24), (80, 120, 160)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def svg_upload(name="active.svg"):
    return SimpleUploadedFile(
        name,
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        content_type="image/svg+xml",
    )


def assert_webp(test_case, field_file):
    test_case.assertTrue(field_file.name.endswith(".webp"))
    field_file.open("rb")
    try:
        signature = field_file.read(12)
    finally:
        field_file.close()
    test_case.assertEqual(signature[:4], b"RIFF")
    test_case.assertEqual(signature[8:12], b"WEBP")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ActiveUploadSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="security-user",
            password="testpass-123",
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_shortcut_and_avatar_images_are_reencoded_as_webp(self):
        section = ShortcutSection.objects.create(user=self.user, name="Security")
        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "Safe",
            "url": "https://example.com",
            "image": raster_upload("shortcut.png"),
        })
        self.assertEqual(response.status_code, 302)
        assert_webp(self, Shortcut.objects.get(name="Safe").image)

        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "Aang",
            "nation": "Luft",
            "image": raster_upload("avatar.png"),
        })
        self.assertEqual(response.status_code, 201)
        assert_webp(self, AvatarCharacter.objects.get(name="Aang").image)

    def test_active_images_are_rejected_by_public_image_features(self):
        section = ShortcutSection.objects.create(user=self.user, name="Security")
        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "Unsafe",
            "url": "https://example.com",
            "image": svg_upload(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Shortcut.objects.filter(name="Unsafe").exists())

        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "Unsafe",
            "nation": "Luft",
            "image": svg_upload("avatar.svg"),
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AvatarCharacter.objects.filter(name="Unsafe").exists())

    def test_file_share_normalizes_raster_and_forces_active_content_to_download(self):
        response = self.client.post(reverse("file_share_upload"), {
            "is_public_link": "on",
            "files": [raster_upload("photo.png")],
        })
        self.assertEqual(response.status_code, 302)
        image_share = FileShare.objects.get(owner=self.user)
        self.assertEqual(image_share.content_type, "image/webp")
        self.assertTrue(image_share.original_name.endswith(".webp"))
        assert_webp(self, image_share.file)

        preview = self.client.get(
            reverse("file_share_download", args=[image_share.token]),
            {"preview": "1"},
        )
        self.assertEqual(preview["Content-Type"], "image/webp")
        self.assertNotIn("attachment", preview.get("Content-Disposition", ""))
        self.assertEqual(preview["X-Content-Type-Options"], "nosniff")

        response = self.client.post(reverse("file_share_upload"), {
            "is_public_link": "on",
            "files": [svg_upload()],
        })
        self.assertEqual(response.status_code, 302)
        active_share = FileShare.objects.exclude(pk=image_share.pk).get()
        self.assertEqual(active_share.content_type, "application/octet-stream")
        self.assertFalse(active_share.is_image)

        download = self.client.get(
            reverse("file_share_download", args=[active_share.token]),
            {"preview": "1"},
        )
        self.assertEqual(download["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")

    def test_chat_attachment_only_previews_reencoded_webp(self):
        other = get_user_model().objects.create_user(username="chat-peer", password="testpass-123")
        room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_DIRECT,
            direct_key=ChatRoom.direct_key_for_users(self.user, other),
        )
        ChatRoomMember.objects.create(room=room, user=self.user)
        ChatRoomMember.objects.create(room=room, user=other)

        response = self.client.post(
            reverse("chat_send", args=[room.id]),
            {"text": "file", "attachments": svg_upload()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        attachment = ChatAttachment.objects.get(message__room=room)
        self.assertEqual(attachment.content_type, "application/octet-stream")
        self.assertFalse(attachment.is_image)
        self.assertEqual(response.json()["message"]["attachments"][0]["preview_url"], "")

        download = self.client.get(
            reverse("chat_attachment_download", args=[attachment.id]),
            {"preview": "1"},
        )
        self.assertEqual(download["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", download["Content-Disposition"])

        response = self.client.post(
            reverse("chat_send", args=[room.id]),
            {"text": "image", "attachments": raster_upload("chat.png")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        image_attachment = ChatAttachment.objects.exclude(pk=attachment.pk).get(message__room=room)
        self.assertEqual(image_attachment.content_type, "image/webp")
        assert_webp(self, image_attachment.file)
        self.assertTrue(response.json()["message"]["attachments"][0]["preview_url"].endswith("?preview=1"))

    def test_debug_public_media_forces_active_documents_to_attachment(self):
        media_path = Path(settings.MEDIA_ROOT) / "shortcut_icons"
        media_path.mkdir(parents=True, exist_ok=True)
        active_path = media_path / "legacy.svg"
        active_path.write_bytes(svg_upload().read())

        request = RequestFactory().get(f"{settings.MEDIA_URL}shortcut_icons/legacy.svg")
        response = public_media(request, "shortcut_icons/legacy.svg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'; sandbox")


class TwoFactorSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="two-factor-user",
            password="testpass-123",
        )
        self.two_factor = UserTwoFactorSettings.objects.create(
            user=self.user,
            secret_key="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _set_pending_session(self):
        session = self.client.session
        session["two_factor_user_id"] = self.user.pk
        session["two_factor_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["two_factor_next"] = reverse("home")
        session["two_factor_attempts"] = 0
        session.save()

    @patch("app.views.auth.verify_totp", return_value=False)
    def test_five_failed_codes_discard_pending_login_on_next_attempt(self, _verify):
        self._set_pending_session()

        for _attempt in range(5):
            response = self.client.post(reverse("two_factor_verify"), {"token": "123456"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("two_factor_verify"), {"token": "123456"})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("two_factor_user_id", self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_two_factor_rate_limit_tracks_pending_user_and_ip_independently(self):
        factory = RequestFactory()
        rule = rule_for_request("two_factor_verify", "POST")

        for index in range(5):
            request = factory.post("/accounts/2fa/", REMOTE_ADDR=f"10.0.0.{index + 1}")
            request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
            request.session = {"two_factor_user_id": self.user.pk}
            self.assertTrue(check_rate_limit(request, rule).allowed)
        request = factory.post("/accounts/2fa/", REMOTE_ADDR="10.0.0.99")
        request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
        request.session = {"two_factor_user_id": self.user.pk}
        self.assertFalse(check_rate_limit(request, rule).allowed)

        cache.clear()
        for index in range(5):
            request = factory.post("/accounts/2fa/", REMOTE_ADDR="10.1.0.1")
            request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
            request.session = {"two_factor_user_id": index + 1000}
            self.assertTrue(check_rate_limit(request, rule).allowed)
        request = factory.post("/accounts/2fa/", REMOTE_ADDR="10.1.0.1")
        request.user = SimpleNamespace(is_authenticated=False, is_staff=False)
        request.session = {"two_factor_user_id": 9999}
        self.assertFalse(check_rate_limit(request, rule).allowed)

    def test_google_login_is_stopped_before_authenticated_session(self):
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        sociallogin = Mock(user=self.user, account=Mock(user=self.user))

        with self.assertRaises(ImmediateHttpResponse) as raised:
            MyToolsSocialAccountAdapter().pre_social_login(request, sociallogin)

        self.assertEqual(raised.exception.response.status_code, 302)
        self.assertEqual(raised.exception.response["Location"], reverse("two_factor_verify"))
        self.assertEqual(request.session["two_factor_user_id"], self.user.pk)
        self.assertNotIn("_auth_user_id", request.session)

    def test_admin_login_is_redirected_to_site_two_factor(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        response = self.client.post(
            reverse("admin:login"),
            {"username": self.user.username, "password": "testpass-123", "next": reverse("admin:index")},
        )

        self.assertRedirects(response, reverse("two_factor_verify"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["two_factor_user_id"], self.user.pk)
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BlockedDirectChatSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.blocker = get_user_model().objects.create_user(username="blocker", password="testpass-123")
        self.blocked = get_user_model().objects.create_user(username="blocked", password="testpass-123")
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_DIRECT,
            direct_key=ChatRoom.direct_key_for_users(self.blocker, self.blocked),
        )
        ChatRoomMember.objects.create(room=self.room, user=self.blocker)
        ChatRoomMember.objects.create(room=self.room, user=self.blocked)
        self.message = ChatMessage.objects.create(room=self.room, sender=self.blocked, text="before block")
        self.attachment = ChatAttachment.objects.create(
            message=self.message,
            file=SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain"),
            original_name="secret.txt",
            content_type="application/octet-stream",
            size=6,
        )
        self.client.force_login(self.blocker)

    @patch("app.views.profile.broadcast_chat_event")
    def test_block_revokes_all_direct_chat_http_access(self, broadcast):
        response = self.client.post(
            reverse("block_user", args=[self.blocked.id]),
            {"action": "block", "next": reverse("users")},
        )
        self.assertEqual(response.status_code, 302)
        broadcast.assert_called_once_with(self.room.id, "access_revoked")

        message_count = ChatMessage.objects.filter(room=self.room).count()
        self.assertEqual(
            self.client.post(reverse("chat_send", args=[self.room.id]), {"text": "after block"}).status_code,
            404,
        )
        self.assertEqual(ChatMessage.objects.filter(room=self.room).count(), message_count)
        self.assertEqual(self.client.get(reverse("chat_messages_api", args=[self.room.id])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("chat_attachment_download", args=[self.attachment.id])).status_code,
            404,
        )
        chat_page = self.client.get(reverse("chat"))
        self.assertNotContains(chat_page, "before block")

        self.client.force_login(self.blocked)
        self.assertEqual(self.client.get(reverse("chat_messages_api", args=[self.room.id])).status_code, 404)


class BlockedDirectChatWebSocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.blocker = get_user_model().objects.create_user(username="ws-blocker", password="testpass-123")
        self.blocked = get_user_model().objects.create_user(username="ws-blocked", password="testpass-123")
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_DIRECT,
            direct_key=ChatRoom.direct_key_for_users(self.blocker, self.blocked),
        )
        ChatRoomMember.objects.create(room=self.room, user=self.blocker)
        ChatRoomMember.objects.create(room=self.room, user=self.blocked)

    def test_open_socket_is_closed_after_block(self):
        async def scenario():
            communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.room.id}/")
            communicator.scope["url_route"] = {"kwargs": {"room_id": self.room.id}}
            communicator.scope["user"] = self.blocked
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()

            await database_sync_to_async(UserBlock.objects.create)(
                blocker=self.blocker,
                blocked=self.blocked,
            )
            await get_channel_layer().group_send(
                f"chat_{self.room.id}",
                {"type": "chat.access_revoked"},
            )
            output = await communicator.receive_output(timeout=1)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], 4403)

        async_to_sync(scenario)()


class CaddyActiveMediaTests(TestCase):
    def test_caddy_forces_active_public_media_to_attachment(self):
        caddyfile = (settings.BASE_DIR / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("@active_public_media", caddyfile)
        self.assertIn('Content-Disposition "attachment"', caddyfile)
        self.assertIn('Content-Type "application/octet-stream"', caddyfile)
        self.assertIn("default-src 'none'; sandbox", caddyfile)
