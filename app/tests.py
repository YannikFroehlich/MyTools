import json
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PIL import Image

from django.conf import settings
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import MessageEncoder
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import pre_save
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse, resolve
from django.utils import timezone
from django_recaptcha.client import RecaptchaResponse

from app.forms import NoteForm
from app.achievement_utils import get_achievement_summary
from app.models import (
    AvatarCharacter,
    BattleshipGame,
    BattleshipInvite,
    ChatAttachment,
    ChatMessage,
    ChatTypingStatus,
    ChatRoom,
    ChatRoomMember,
    ConnectFourGame,
    CookieClickerHighScore,
    CookieCosmosV2Save,
    Game2048HighScore,
    DrawingGameLobby,
    DrawingGamePlayer,
    FeatureComment,
    FeatureIdea,
    FeatureVote,
    FileShare,
    Friendship,
    HomeLayoutPreference,
    HomeWidget,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    HangmanLobby,
    HangmanPlayer,
    InboxItem,
    KniffelGame,
    KniffelInvite,
    KniffelPlayer,
    Note,
    PongGame,
    PongInvite,
    SecurityEvent,
    ProfileGalleryImage,
    Shortcut,
    ShortcutSection,
    SiteAccessSettings,
    StadtLandFlussLobby,
    StadtLandFlussPlayer,
    TicTacToeGame,
    TicTacToeInvite,
    ToolFavorite,
    ToolFeedback,
    ModerationAuditLog,
    UnoGame,
    UnoPlayer,
    UserBlock,
    UserPresence,
    UserProfile,
    UserReport,
    UserSuspension,
    UserTwoFactorSettings,
    WeatherLocation,
)
from app.notification_utils import get_notification_counts, get_notification_items, invalidate_notification_cache
from app.trash_utils import purge_expired_trash
from app.totp_utils import current_totp


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaseTestCase(TestCase):
    user_scoped_models = (
        AvatarCharacter,
        HomeWidget,
        CookieClickerHighScore,
        CookieCosmosV2Save,
        HumanBenchmarkHighScore,
        HumanBenchmarkScore,
        Note,
        Shortcut,
        ShortcutSection,
        WeatherLocation,
    )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="testpass-123",
        )
        self.client.force_login(self.user)
        self._connect_user_signal()

    def tearDown(self):
        self._disconnect_user_signal()
        cache.clear()
        super().tearDown()

    def _connect_user_signal(self):
        def assign_test_user(sender, instance, **kwargs):
            if getattr(instance, "user_id", None) is None:
                instance.user = self.user

        self._assign_test_user = assign_test_user
        for model in self.user_scoped_models:
            pre_save.connect(self._assign_test_user, sender=model, weak=False)

    def _disconnect_user_signal(self):
        for model in self.user_scoped_models:
            pre_save.disconnect(self._assign_test_user, sender=model)

    def get_test_image(self, name="test.png"):
        buffer = BytesIO()
        Image.new("RGB", (16, 16), (120, 120, 120)).save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def get_large_test_image(self, name="large.bmp"):
        width = 2000
        height = 1000
        row_size = ((24 * width + 31) // 32) * 4
        pixel_data_size = row_size * height
        file_size = 54 + pixel_data_size

        return SimpleUploadedFile(
            name,
            (
                b"BM"
                + file_size.to_bytes(4, "little")
                + b"\x00\x00\x00\x00"
                + (54).to_bytes(4, "little")
                + (40).to_bytes(4, "little")
                + width.to_bytes(4, "little")
                + height.to_bytes(4, "little")
                + (1).to_bytes(2, "little")
                + (24).to_bytes(2, "little")
                + (0).to_bytes(4, "little")
                + pixel_data_size.to_bytes(4, "little")
                + (2835).to_bytes(4, "little")
                + (2835).to_bytes(4, "little")
                + (0).to_bytes(4, "little")
                + (0).to_bytes(4, "little")
                + (b"\xff\xff\xff" * width + (b"\x00" * (row_size - width * 3))) * height
            ),
            content_type="image/bmp",
        )


class ModelTests(BaseTestCase):
    def test_shortcut_section_str_returns_name(self):
        section = ShortcutSection.objects.create(name="Server")

        self.assertEqual(str(section), "Server")

    def test_shortcut_str_returns_name(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="GitHub",
            url="https://github.com",
            icon="fa-brands fa-github",
        )

        self.assertEqual(str(shortcut), "GitHub")

    def test_shortcut_belongs_to_section(self):
        section = ShortcutSection.objects.create(name="Verknüpfungen")
        shortcut = Shortcut.objects.create(
            section=section,
            name="YouTube",
            url="https://youtube.com",
            icon="fa-brands fa-youtube",
        )

        self.assertEqual(shortcut.section, section)
        self.assertIn(shortcut, section.shortcuts.all())

    def test_note_str_returns_title_or_default_name(self):
        titled_note = Note.objects.create(title="Server-Idee", content="Text")
        empty_note = Note.objects.create(title="", content="Nur Inhalt")

        self.assertEqual(str(titled_note), "Server-Idee")
        self.assertEqual(str(empty_note), "Unbenannte Notiz")

    def test_note_tag_list_removes_empty_tags_and_spaces(self):
        note = Note.objects.create(tags="schule, server, , idee ,")

        self.assertEqual(note.tag_list(), ["schule", "server", "idee"])

    def test_weather_location_str_returns_name(self):
        location = WeatherLocation.objects.create(name="Berlin")

        self.assertEqual(str(location), "Berlin")

    def test_avatar_character_str_returns_name(self):
        character = AvatarCharacter.objects.create(
            name="Aang",
            nation="Luft",
            image=self.get_test_image(),
        )

        self.assertEqual(str(character), "Aang")

    def test_user_profile_str_and_initials(self):
        self.user.first_name = "Yannik"
        self.user.last_name = "Fröhlich"
        self.user.save(update_fields=["first_name", "last_name"])

        profile = UserProfile.objects.create(user=self.user, bio="Hallo")

        self.assertEqual(str(profile), "Profil von testuser")
        self.assertEqual(profile.initials, "YF")

    def test_user_profile_initials_fallback_to_username(self):
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(profile.initials, "TE")
        self.assertEqual(profile.avatar_url, "")

    def test_friendship_str_and_other_user(self):
        other_user = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        friendship = Friendship.objects.create(
            from_user=self.user,
            to_user=other_user,
            status=Friendship.STATUS_ACCEPTED,
        )

        self.assertIn("testuser", str(friendship))
        self.assertEqual(friendship.other_user(self.user), other_user)
        self.assertEqual(friendship.other_user(other_user), self.user)
        self.assertEqual(Friendship.friend_ids_for_user(self.user), [other_user.id])

    def test_home_widget_str_returns_title_and_type(self):
        widget = HomeWidget.objects.create(
            user=self.user,
            title="Mein Wetter",
            widget_type=HomeWidget.WIDGET_WEATHER,
        )

        self.assertEqual(str(widget), "Mein Wetter · Wetter")

    def test_home_layout_preference_str_returns_user(self):
        preference = HomeLayoutPreference.objects.create(user=self.user)

        self.assertEqual(str(preference), f"Home-Layout von {self.user}")

    def test_human_benchmark_score_str_returns_user_game_and_score(self):
        score = HumanBenchmarkScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=250,
            display_score="250 ms",
            details={"rounds": 5},
        )

        self.assertEqual(str(score), f"{self.user} · Reaktion · 250 ms")

    def test_human_benchmark_highscore_str_returns_user_game_and_score(self):
        highscore = HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_TYPING,
            score=82,
            display_score="82 WPM",
            details={"accuracy": 97},
        )

        self.assertEqual(str(highscore), f"{self.user} · Typing Test · 82 WPM")


class MultiplayerRoomCleanupTests(BaseTestCase):
    def test_home_state_apis_delete_empty_rooms_for_all_games(self):
        empty_rooms = [
            (
                TicTacToeGame.objects.create(owner=self.user, code="TTTEMPTY", board=[""] * 9),
                "tictactoe_home_state_api",
                TicTacToeGame,
            ),
            (
                ConnectFourGame.objects.create(owner=self.user, code="CFOEMPTY"),
                "connectfour_home_state_api",
                ConnectFourGame,
            ),
            (
                BattleshipGame.objects.create(owner=self.user, code="SEAEMPTY"),
                "battleship_home_state_api",
                BattleshipGame,
            ),
            (
                UnoGame.objects.create(owner=self.user, code="UNOEMPTY"),
                "uno_home_state_api",
                UnoGame,
            ),
            (
                KniffelGame.objects.create(owner=self.user, code="KNFEMPTY"),
                "kniffel_home_state_api",
                KniffelGame,
            ),
            (
                StadtLandFlussLobby.objects.create(owner=self.user, code="SLFEMPTY"),
                "stadtlandfluss_home_state_api",
                StadtLandFlussLobby,
            ),
            (
                DrawingGameLobby.objects.create(owner=self.user, code="DRWEMPTY"),
                "skribble_home",
                DrawingGameLobby,
            ),
            (
                HangmanLobby.objects.create(owner=self.user, code="HGMEMPTY"),
                "hangman_home_state_api",
                HangmanLobby,
            ),
        ]

        for room, home_state_route, model in empty_rooms:
            with self.subTest(route=home_state_route):
                response = self.client.get(reverse(home_state_route))

                self.assertEqual(response.status_code, 200)
                self.assertFalse(model.objects.filter(pk=room.pk).exists())

    def test_hangman_home_state_deletes_current_users_stale_room(self):
        lobby = HangmanLobby.objects.create(owner=self.user, code="HGMSTALE")
        player = HangmanPlayer.objects.create(lobby=lobby, user=self.user, display_name=self.user.username)
        HangmanPlayer.objects.filter(pk=player.pk).update(
            last_seen=timezone.now() - timezone.timedelta(minutes=20)
        )

        response = self.client.get(reverse("hangman_home_state_api"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(HangmanLobby.objects.filter(pk=lobby.pk).exists())


class HangmanManualModeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.other = get_user_model().objects.create_user(
            username="otheruser",
            password="testpass-123",
        )

    def create_two_player_lobby(self, code="HGM2P", first_user=None, second_user=None):
        first_user = first_user or self.user
        second_user = second_user or self.other
        lobby = HangmanLobby.objects.create(owner=self.user, code=code, max_mistakes=8)
        HangmanPlayer.objects.create(lobby=lobby, user=first_user, display_name=first_user.username)
        HangmanPlayer.objects.create(lobby=lobby, user=second_user, display_name=second_user.username)
        return lobby

    def test_hangman_manual_review_reveals_letter_after_setter_confirms(self):
        lobby = self.create_two_player_lobby()

        start_response = self.client.post(reverse("hangman_start_api", args=[lobby.code]))
        self.assertEqual(start_response.status_code, 200)
        self.assertTrue(start_response.json()["game"]["canSetWord"])

        word_response = self.client.post(reverse("hangman_word_api", args=[lobby.code]), {
            "word": "PYTHON",
            "hint": "Code",
        })
        self.assertEqual(word_response.status_code, 200)
        self.assertEqual(word_response.json()["game"]["roundPhase"], "guessing")

        self.client.force_login(self.other)
        guess_response = self.client.post(reverse("hangman_guess_api", args=[lobby.code]), {"guess": "P"})
        self.assertEqual(guess_response.status_code, 200)
        guess_game = guess_response.json()["game"]
        self.assertEqual(guess_game["roundPhase"], "review")
        self.assertEqual(guess_game["pendingGuess"]["guess"], "P")
        self.assertEqual(guess_game["guessedLetters"], [])
        self.assertEqual(guess_game["mistakes"], 0)

        self.client.force_login(self.user)
        review_response = self.client.post(reverse("hangman_review_api", args=[lobby.code]), {"result": "correct"})
        self.assertEqual(review_response.status_code, 200)
        review_game = review_response.json()["game"]
        self.assertEqual(review_game["roundPhase"], "guessing")
        self.assertIn("P", review_game["guessedLetters"])
        self.assertEqual(review_game["maskedWord"][0], "P")
        self.assertEqual(review_game["mistakes"], 0)

    def test_hangman_finishes_after_fourth_round_review(self):
        lobby = self.create_two_player_lobby(code="HGM4P", first_user=self.other, second_user=self.user)
        lobby.status = HangmanLobby.STATUS_PLAYING
        lobby.round_number = 4
        lobby.word = "PYTHON"
        lobby.last_guess = {
            "phase": "review",
            "pending": True,
            "player": self.other.username,
            "playerId": self.other.id,
            "guess": "PYTHON",
            "guessType": "word",
        }
        lobby.save()

        response = self.client.post(reverse("hangman_review_api", args=[lobby.code]), {"result": "correct"})

        self.assertEqual(response.status_code, 200)
        game = response.json()["game"]
        self.assertEqual(game["status"], HangmanLobby.STATUS_FINISHED)
        self.assertEqual(game["roundPhase"], "game_over")
        lobby.refresh_from_db()
        self.assertEqual(lobby.winner, self.other)

    def test_hangman_room_rejects_third_player(self):
        lobby = self.create_two_player_lobby()
        third = get_user_model().objects.create_user(username="thirduser", password="testpass-123")
        self.client.force_login(third)

        response = self.client.get(reverse("hangman_lobby", args=[lobby.code]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(lobby.players.filter(user=third).exists())




class LiveStatusPerformanceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_live_status_api_returns_notifications_and_presence_in_one_request(self):
        friend = get_user_model().objects.create_user(username="statusfriend", password="testpass-123")
        UserProfile.objects.get_or_create(user=friend)
        UserPresence.objects.create(user=friend, last_seen=timezone.now())
        game = PongGame.objects.create(owner=friend, player_left=friend, name="Pong", code="LIV123")
        PongInvite.objects.create(game=game, from_user=friend, to_user=self.user)

        response = self.client.get(reverse("live_status_api"), {"ids": str(friend.id), "items": "1"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["counts"]["pong_invites"], 1)
        self.assertTrue(any(item["type"] == "pong" for item in payload["items"]))
        self.assertEqual(payload["profiles"][0]["userId"], friend.id)
        self.assertTrue(payload["profiles"][0]["isOnline"])

    def test_notification_counts_are_invalidated_when_invite_changes(self):
        friend = get_user_model().objects.create_user(username="cachefriend", password="testpass-123")
        game = PongGame.objects.create(owner=self.user, player_left=self.user, name="Pong", code="CAC123")
        invite = PongInvite.objects.create(game=game, from_user=self.user, to_user=friend)

        self.assertEqual(get_notification_counts(friend)["pong_invites"], 1)

        with self.captureOnCommitCallbacks(execute=True):
            invite.delete()
        self.assertEqual(get_notification_counts(friend)["pong_invites"], 0)


    def test_live_status_ignores_invalid_ids_and_limits_presence_profiles(self):
        created_users = [
            get_user_model().objects.create_user(username=f"presence_user_{index}", password="testpass-123")
            for index in range(55)
        ]
        for created_user in created_users:
            UserProfile.objects.get_or_create(user=created_user)
            UserPresence.objects.create(user=created_user, last_seen=timezone.now())

        raw_ids = "abc,," + ",".join(str(created_user.id) for created_user in created_users) + f",{created_users[0].id}"
        response = self.client.get(reverse("live_status_api"), {"ids": raw_ids})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["profiles"]), 50)
        self.assertEqual(payload["profiles"][0]["userId"], created_users[0].id)
        self.assertEqual(payload["profiles"][-1]["userId"], created_users[49].id)

    def test_live_status_respects_private_presence_for_non_friends(self):
        private_user = get_user_model().objects.create_user(username="private_presence", password="testpass-123")
        profile, _ = UserProfile.objects.get_or_create(user=private_user)
        profile.privacy_show_online = False
        profile.save(update_fields=["privacy_show_online"])
        UserPresence.objects.create(
            user=private_user,
            last_seen=timezone.now(),
            active_game="2048",
            active_game_label="spielt 2048",
            active_game_updated_at=timezone.now(),
        )

        response = self.client.get(reverse("live_status_api"), {"ids": str(private_user.id)})

        self.assertEqual(response.status_code, 200)
        profile_payload = response.json()["profiles"][0]
        self.assertFalse(profile_payload["isOnline"])
        self.assertEqual(profile_payload["activityStatus"], "")

    def test_live_status_presence_payload_is_short_cached(self):
        friend = get_user_model().objects.create_user(username="presence_cache_friend", password="testpass-123")
        UserProfile.objects.get_or_create(user=friend)
        UserPresence.objects.create(user=friend, last_seen=timezone.now())

        first_response = self.client.get(reverse("live_status_api"), {"ids": str(friend.id)})
        self.assertTrue(first_response.json()["profiles"][0]["isOnline"])

        UserPresence.objects.filter(user=friend).update(last_seen=timezone.now() - timezone.timedelta(days=1))
        cached_response = self.client.get(reverse("live_status_api"), {"ids": str(friend.id)})
        self.assertTrue(cached_response.json()["profiles"][0]["isOnline"])

        cache.clear()
        fresh_response = self.client.get(reverse("live_status_api"), {"ids": str(friend.id)})
        self.assertFalse(fresh_response.json()["profiles"][0]["isOnline"])


class MediaThumbnailTests(BaseTestCase):
    def test_media_srcset_filter_builds_responsive_thumbnail_urls(self):
        from app.templatetags.media_performance import media_srcset

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)

        srcset = media_srcset(profile.avatar, "avatar-small 96w, avatar 192w")

        self.assertIn("/media-thumb/avatar-small/", srcset)
        self.assertIn("/media-thumb/avatar/", srcset)
        self.assertIn("96w", srcset)
        self.assertIn("192w", srcset)

    def test_media_thumbnail_creates_cached_preview_without_login(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)
        self.client.logout()

        response = self.client.get(reverse("media_thumbnail", args=["avatar-small", profile.avatar.name]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=31536000", response["Cache-Control"])
        self.assertTrue(response.streaming)

    def test_media_thumbnail_response_uses_webp_content_type(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.png", self.get_test_image("avatar.png"), save=True)
        self.client.logout()

        response = self.client.get(reverse("media_thumbnail", args=["avatar-small", profile.avatar.name]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/webp")

    def test_media_filters_return_empty_for_missing_files(self):
        from app.templatetags.media_performance import media_srcset, media_thumb

        self.assertEqual(media_thumb(None, "avatar-small"), "")
        self.assertEqual(media_srcset(None, "avatar-small 96w"), "")

    def test_media_srcset_skips_empty_entries_and_keeps_descriptor_order(self):
        from app.templatetags.media_performance import media_srcset

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.png", self.get_test_image("avatar.png"), save=True)

        srcset = media_srcset(profile.avatar, " , avatar-tiny 48w, avatar-small 96w, ")

        self.assertIn("avatar-tiny", srcset)
        self.assertIn("48w", srcset)
        self.assertIn("avatar-small", srcset)
        self.assertIn("96w", srcset)
        self.assertNotIn("unknown", srcset)

    def test_media_thumbnail_returns_not_modified_for_matching_header(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)
        self.client.logout()

        first_response = self.client.get(reverse("media_thumbnail", args=["avatar-small", profile.avatar.name]))
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.get(
            reverse("media_thumbnail", args=["avatar-small", profile.avatar.name]),
            HTTP_IF_MODIFIED_SINCE=first_response["Last-Modified"],
        )

        self.assertEqual(second_response.status_code, 304)


    def test_media_thumbnail_cache_path_uses_webp_for_png_sources(self):
        from app.media_views import _thumbnail_path

        thumb_path = _thumbnail_path("profile_pictures/avatar.png", "avatar-small", Path("avatar.png"))

        self.assertEqual(thumb_path.suffix, ".webp")
        self.assertIn("avatar-small", str(thumb_path))

    def test_media_thumbnail_rejects_path_traversal(self):
        self.client.logout()

        response = self.client.get("/media-thumb/avatar-small/../secret.png")

        self.assertEqual(response.status_code, 400)

    def test_media_thumbnail_rejects_unknown_spec(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)

        response = self.client.get(reverse("media_thumbnail", args=["unknown", profile.avatar.name]))

        self.assertEqual(response.status_code, 404)


class RealtimeInfrastructureTests(SimpleTestCase):
    def test_broadcast_group_returns_false_without_channel_layer(self):
        from app.realtime import broadcast_group

        with patch("app.realtime.get_channel_layer", return_value=None):
            self.assertFalse(broadcast_group("chat_1", {"type": "chat.typing"}))

    def test_broadcast_chat_event_sends_channels_group_event(self):
        from app.realtime import broadcast_chat_event

        layer = Mock()
        send_callable = Mock()
        with patch("app.realtime.get_channel_layer", return_value=layer), patch("app.realtime.async_to_sync", return_value=send_callable):
            did_send = broadcast_chat_event(42, "message_created", message_id=7)

        self.assertTrue(did_send)
        send_callable.assert_called_once_with("chat_42", {"type": "chat.message_created", "message_id": 7})

    def test_broadcast_live_status_event_sends_user_group_event(self):
        from app.realtime import broadcast_live_status_event

        layer = Mock()
        send_callable = Mock()
        with patch("app.realtime.get_channel_layer", return_value=layer), patch("app.realtime.async_to_sync", return_value=send_callable):
            did_send = broadcast_live_status_event(23, reason="notifications")

        self.assertTrue(did_send)
        send_callable.assert_called_once_with(
            "live_status_user_23",
            {"type": "live.status_changed", "reason": "notifications"},
        )

    def test_invalidate_notification_cache_broadcasts_live_status(self):
        from app.notification_utils import invalidate_notification_cache_for_user_id

        with patch("app.notification_utils.broadcast_live_status_event") as mock_broadcast:
            invalidate_notification_cache_for_user_id(23)

        mock_broadcast.assert_called_once_with(23, reason="notifications")

    def test_websocket_routes_include_chat_pong_and_live_status(self):
        from app.routing import websocket_urlpatterns

        routes = {getattr(pattern.pattern, "_route", str(pattern.pattern)) for pattern in websocket_urlpatterns}

        self.assertIn("ws/live-status/", routes)
        self.assertIn("ws/chat/<int:room_id>/", routes)
        self.assertIn("ws/pong/<str:code>/", routes)


class PerformanceIndexTests(SimpleTestCase):
    def index_names(self, model):
        return {index.name for index in model._meta.indexes if index.name}

    def test_chat_indexes_cover_realtime_message_and_read_queries(self):
        self.assertIn("chatroom_updated_idx", self.index_names(ChatRoom))
        self.assertIn("chatmember_user_read_idx", self.index_names(ChatRoomMember))
        self.assertIn("chatmsg_room_new_idx", self.index_names(ChatMessage))
        self.assertIn("chatattach_msg_created_idx", self.index_names(ChatAttachment))

    def test_dashboard_and_media_indexes_are_declared_on_models(self):
        self.assertIn("weather_user_default_idx", self.index_names(WeatherLocation))
        self.assertIn("homewidget_enabled_order_idx", self.index_names(HomeWidget))
        self.assertIn("gallery_user_public_idx", self.index_names(ProfileGalleryImage))
        self.assertIn("fileshare_type_created_idx", self.index_names(FileShare))
        self.assertIn("upres_game_updated_idx", self.index_names(UserPresence))




class PwaTests(BaseTestCase):
    def test_manifest_is_public_and_installable(self):
        self.client.logout()
        response = self.client.get(reverse("pwa_manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        self.assertEqual(response.json()["display"], "standalone")
        self.assertEqual(response.json()["scope"], "/")
        self.assertTrue(any(icon["sizes"] == "512x512" for icon in response.json()["icons"]))
        self.assertTrue(any(icon["purpose"] == "maskable" for icon in response.json()["icons"]))

    def test_service_worker_is_public_and_allowed_for_root_scope(self):
        self.client.logout()
        response = self.client.get(reverse("pwa_service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertContains(response, "navigationFallback")
        self.assertContains(response, reverse("offline"))
        self.assertContains(response, "/static/app/css/core.css")

    def test_offline_page_is_public(self):
        self.client.logout()
        response = self.client.get(reverse("offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Du bist offline")
        self.assertContains(response, "Erneut versuchen")

    def test_base_template_links_manifest_and_pwa_assets(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("pwa_manifest"))
        self.assertContains(response, "pwa-install-button")
        self.assertContains(response, "/static/app/js/base.js")

    def test_base_js_registers_service_worker(self):
        base_js = settings.BASE_DIR / "app" / "static" / "app" / "js" / "base.js"
        content = base_js.read_text(encoding="utf-8")

        self.assertIn("navigator.serviceWorker.register('/service-worker.js')", content)
        self.assertIn("beforeinstallprompt", content)


class CaddyPerformanceConfigTests(SimpleTestCase):
    def test_caddyfile_has_static_media_compression_and_cache_headers(self):
        caddyfile = (settings.BASE_DIR / "Caddyfile").read_text(encoding="utf-8")

        self.assertIn("encode gzip zstd", caddyfile)
        self.assertIn("handle_path /static/*", caddyfile)
        self.assertIn("handle_path /media/*", caddyfile)
        self.assertIn('Cache-Control "public, max-age=604800', caddyfile)
        self.assertIn('Cache-Control "public, max-age=86400', caddyfile)
        self.assertIn('X-Content-Type-Options "nosniff"', caddyfile)


class AuthViewTests(BaseTestCase):
    def _mock_recaptcha_success(self, mocked_submit):
        mocked_submit.return_value = RecaptchaResponse(is_valid=True)

    def _login_payload(self, username, password):
        return {
            "username": username,
            "password": password,
            "g-recaptcha-response": "PASSED",
        }

    def test_signup_page_loads_without_login(self):
        self.client.logout()

        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signup.html")

    def test_signup_creates_user_and_logs_in(self):
        self.client.logout()

        response = self.client.post(reverse("signup"), {
            "username": "neueruser",
            "email": "neu@example.com",
            "password1": "complex-test-pass-123",
            "password2": "complex-test-pass-123",
        })

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(get_user_model().objects.filter(username="neueruser").exists())

    def test_login_route_uses_access_aware_login_view(self):
        from app.auth_views import AccessAwareLoginView

        match = resolve("/accounts/login/")

        self.assertEqual(match.func.view_class, AccessAwareLoginView)

    def test_login_page_contains_recaptcha(self):
        self.client.logout()

        response = self.client.get(reverse("login"))

        self.assertContains(response, "g-recaptcha")

    @patch("django_recaptcha.fields.client.submit")
    def test_login_without_two_factor_logs_in_directly(self, mocked_submit):
        self._mock_recaptcha_success(mocked_submit)
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            self._login_payload(self.user.username, "testpass-123"),
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_two_factor_verify_without_pending_login_redirects_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("two_factor_verify"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)


    def test_two_factor_setup_can_be_enabled(self):
        response = self.client.post(reverse("two_factor_settings"), {"action": "start_setup"})
        self.assertRedirects(response, reverse("two_factor_settings"))

        settings_obj = UserTwoFactorSettings.objects.get(user=self.user)
        token = current_totp(settings_obj.secret_key)

        response = self.client.post(reverse("two_factor_settings"), {
            "action": "confirm_setup",
            "token": token,
        })

        self.assertRedirects(response, reverse("two_factor_settings"))
        settings_obj.refresh_from_db()
        self.assertTrue(settings_obj.is_enabled)

    @patch("django_recaptcha.fields.client.submit")
    def test_two_factor_login_requires_second_code(self, mocked_submit):
        self._mock_recaptcha_success(mocked_submit)
        self.client.logout()
        two_factor_settings = UserTwoFactorSettings.objects.create(
            user=self.user,
            secret_key="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )

        response = self.client.post(
            reverse("login"),
            self._login_payload(self.user.username, "testpass-123"),
        )

        self.assertRedirects(response, reverse("two_factor_verify"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("two_factor_verify"), {
            "token": current_totp(two_factor_settings.secret_key),
        })

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    @patch("django_recaptcha.fields.client.submit")
    def test_two_factor_rejects_wrong_code(self, mocked_submit):
        self._mock_recaptcha_success(mocked_submit)
        self.client.logout()
        UserTwoFactorSettings.objects.create(
            user=self.user,
            secret_key="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )
        self.client.post(
            reverse("login"),
            self._login_payload(self.user.username, "testpass-123"),
        )

        response = self.client.post(reverse("two_factor_verify"), {"token": "000000"})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_access_lock_blocks_signup(self):
        self.client.logout()
        SiteAccessSettings.objects.update_or_create(
            pk=1,
            defaults={"login_registration_locked": True, "lock_message": "Wartung"},
        )

        response = self.client.post(reverse("signup"), {
            "username": "blockeduser",
            "email": "blocked@example.com",
            "password1": "complex-test-pass-123",
            "password2": "complex-test-pass-123",
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username="blockeduser").exists())

    @patch("django_recaptcha.fields.client.submit")
    def test_access_lock_blocks_normal_login_but_allows_staff(self, mocked_submit):
        self._mock_recaptcha_success(mocked_submit)
        self.client.logout()
        SiteAccessSettings.objects.update_or_create(pk=1, defaults={"login_registration_locked": True})
        normal_user = get_user_model().objects.create_user(username="normaluser", password="testpass-123")
        staff_user = get_user_model().objects.create_user(username="staffuser", password="testpass-123", is_staff=True)

        normal_response = self.client.post(
            reverse("login"),
            self._login_payload(normal_user.username, "testpass-123"),
        )
        self.assertEqual(normal_response.status_code, 200)
        self.assertNotEqual(int(self.client.session.get("_auth_user_id", 0) or 0), normal_user.id)

        staff_response = self.client.post(
            reverse("login"),
            self._login_payload(staff_user.username, "testpass-123"),
        )
        self.assertRedirects(staff_response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), staff_user.id)

    def test_staff_can_toggle_access_lock_from_moderation(self):
        self.client.logout()
        staff_user = get_user_model().objects.create_user(username="moderator", password="testpass-123", is_staff=True)
        self.client.force_login(staff_user)

        response = self.client.post(reverse("moderation_access_toggle"), {
            "login_registration_locked": "1",
            "lock_message": "Kurz Wartung",
        })

        self.assertRedirects(response, reverse("moderation"))
        settings_obj = SiteAccessSettings.get_solo()
        self.assertTrue(settings_obj.login_registration_locked)
        self.assertEqual(settings_obj.lock_message, "Kurz Wartung")

    def test_user_admin_can_reset_two_factor_for_selected_users(self):
        from django.contrib import admin

        UserModel = get_user_model()
        UserTwoFactorSettings.objects.create(
            user=self.user,
            secret_key="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )
        request = RequestFactory().post("/admin/auth/user/")
        request.user = UserModel.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="testpass-123",
        )
        request._messages = Mock()
        user_admin = admin.site._registry[UserModel]

        user_admin.reset_two_factor_for_users(request, UserModel.objects.filter(pk=self.user.pk))

        self.assertFalse(UserTwoFactorSettings.objects.filter(user=self.user).exists())

    def test_user_admin_shows_two_factor_status(self):
        from django.contrib import admin

        UserModel = get_user_model()
        user_admin = admin.site._registry[UserModel]

        self.assertFalse(user_admin.two_factor_status(self.user))
        UserTwoFactorSettings.objects.create(
            user=self.user,
            secret_key="JBSWY3DPEHPK3PXP",
            is_enabled=True,
        )

        self.assertTrue(user_admin.two_factor_status(self.user))


class ProfileViewTests(BaseTestCase):
    def test_profile_page_loads_and_creates_profile(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/profile.html")
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        self.assertContains(response, "Achievements öffentlich anzeigen")

    def test_achievement_summary_unlocks_cross_app_badges(self):
        friend = get_user_model().objects.create_user(
            username="badgefreund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        note = Note.objects.create(
            title="Badge Notiz",
            reminder_at=timezone.now() + timezone.timedelta(days=1),
        )
        note.shared_with.add(friend)
        profile, _created = UserProfile.objects.get_or_create(user=self.user)
        profile.profile_game_cards = [{"key": "human_benchmark", "visible": True}]
        profile.save(update_fields=["profile_game_cards"])

        room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_GROUP,
            name="Badge Chat",
            created_by=self.user,
        )
        ChatRoomMember.objects.create(room=room, user=self.user)
        ChatMessage.objects.create(room=room, sender=self.user, text="Hallo")

        FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("badge.txt", b"badge", content_type="text/plain"),
            original_name="badge.txt",
            size=5,
            content_type="text/plain",
            token="badge-share-token",
            is_public_link=True,
            download_count=10,
        )
        CookieClickerHighScore.objects.create(
            user=self.user,
            score=1000,
            display_score="1.000",
            achievements_count=25,
        )
        for index in range(10):
            HumanBenchmarkScore.objects.create(
                user=self.user,
                game=HumanBenchmarkScore.GAME_REACTION,
                score=220 + index,
                display_score=f"{220 + index} ms",
            )
        for game, score in [
            (HumanBenchmarkScore.GAME_REACTION, 220),
            (HumanBenchmarkScore.GAME_AIM, 40),
            (HumanBenchmarkScore.GAME_TYPING, 80),
            (HumanBenchmarkScore.GAME_VISUAL, 12),
        ]:
            HumanBenchmarkHighScore.objects.create(
                user=self.user,
                game=game,
                score=score,
                display_score=str(score),
            )
        TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="BADGE1",
            status=TicTacToeGame.STATUS_FINISHED,
            winner_symbol=TicTacToeGame.SYMBOL_X,
        )

        summary = get_achievement_summary(self.user)
        unlocked_keys = {achievement["key"] for achievement in summary["unlocked"]}

        self.assertIn("first_note", unlocked_keys)
        self.assertIn("reminder_ready", unlocked_keys)
        self.assertIn("note_collab", unlocked_keys)
        self.assertIn("first_message", unlocked_keys)
        self.assertIn("first_upload", unlocked_keys)
        self.assertIn("public_link", unlocked_keys)
        self.assertIn("downloaded", unlocked_keys)
        self.assertIn("first_game", unlocked_keys)
        self.assertIn("score_hunter", unlocked_keys)
        self.assertIn("first_win", unlocked_keys)
        self.assertIn("profile_showcase", unlocked_keys)
        self.assertIn("daily_visit", unlocked_keys)
        self.assertIn("benchmark_regular", unlocked_keys)
        self.assertIn("highscore_master", unlocked_keys)
        self.assertIn("cookie_collector", unlocked_keys)
        self.assertGreater(summary["total_xp"], 0)
        self.assertGreaterEqual(summary["level"]["level"], 2)

    def test_profile_post_updates_profile_and_user_fields(self):
        response = self.client.post(reverse("profile"), {
            "username": "neuername",
            "first_name": "Yannik",
            "last_name": "Fröhlich",
            "email": "yannik@example.com",
            "bio": "Meine Bio",
        })

        self.assertRedirects(response, reverse("profile"))

        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)

        self.assertEqual(self.user.username, "neuername")
        self.assertEqual(self.user.first_name, "Yannik")
        self.assertEqual(self.user.last_name, "Fröhlich")
        self.assertEqual(self.user.email, "yannik@example.com")
        self.assertEqual(profile.bio, "Meine Bio")

    def test_profile_settings_hide_navigation_shortcuts_and_banner(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Chat öffnen")
        self.assertNotContains(response, "Nutzer finden")
        self.assertNotContains(response, "Freundesliste öffnen")
        self.assertNotContains(response, "Banner auswählen")
        self.assertNotIn("profile_banner", response.context["form"].fields)
        self.assertTemplateNotUsed(response, "app/includes/achievement_panel.html")
        self.assertTemplateNotUsed(response, "app/includes/profile_game_cards.html")

    def test_profile_settings_save_achievement_visibility(self):
        response = self.client.post(reverse("profile"), {
            "username": self.user.username,
            "first_name": "",
            "last_name": "",
            "email": "",
            "bio": "",
        })

        self.assertRedirects(response, reverse("profile"))
        self.assertFalse(UserProfile.objects.get(user=self.user).privacy_show_achievements)

    def test_profile_rejects_duplicate_username(self):
        get_user_model().objects.create_user(
            username="belegt",
            email="belegt@example.com",
            password="testpass-123",
        )

        response = self.client.post(reverse("profile"), {
            "username": "belegt",
            "first_name": "",
            "last_name": "",
            "email": "frei@example.com",
            "bio": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "username", "Dieser Benutzername ist bereits vergeben.")

    def test_users_page_lists_active_profiles(self):
        other_user = get_user_model().objects.create_user(
            username="anderer",
            first_name="Max",
            password="testpass-123",
        )

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/users.html")
        self.assertEqual(response.context["total_users"], 2)
        self.assertTrue(UserProfile.objects.filter(user=other_user).exists())

    def test_users_page_uses_profile_card_design_for_user_cards(self):
        other_user = get_user_model().objects.create_user(
            username="cardstyleuser",
            password="testpass-123",
        )
        UserProfile.objects.create(
            user=other_user,
            profile_card_primary="#123456",
            profile_card_secondary="#abcdef",
            profile_card_tertiary="#fedcba",
            profile_card_text="#ffffff",
            profile_card_border="#00ff99",
            profile_card_badge_bg="#112233",
            profile_card_badge_text="Tester",
            profile_card_style="glass",
            profile_card_pattern="grid",
            profile_card_radius="bold",
        )

        response = self.client.get(reverse("users"))

        self.assertContains(response, "user-card-profile-showcase")
        self.assertContains(response, "profile-showcase-card-glass")
        self.assertContains(response, "profile-showcase-pattern-grid")
        self.assertContains(response, "--profile-card-primary: #123456")
        self.assertContains(response, "--profile-card-secondary: #abcdef")
        self.assertContains(response, "--profile-card-border: #00ff99")
        self.assertContains(response, "Tester")

    def test_users_page_search_filters_by_username(self):
        get_user_model().objects.create_user(username="serverfreund", password="testpass-123")
        get_user_model().objects.create_user(username="anderer", password="testpass-123")

        response = self.client.get(reverse("users"), {
            "q": "server",
        })

        usernames = [profile.user.username for profile in response.context["profiles"]]

        self.assertIn("serverfreund", usernames)
        self.assertNotIn("anderer", usernames)

    def test_public_profile_page_loads(self):
        other_user = get_user_model().objects.create_user(
            username="publicuser",
            password="testpass-123",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/public_profile.html")
        self.assertEqual(response.context["profile_user"], other_user)
        self.assertEqual(response.context["friendship_state"], "none")
        self.assertTrue(UserProfile.objects.filter(user=other_user).exists())
        self.assertIn("achievement_summary", response.context)

    def test_own_public_profile_shows_profile_settings_button(self):
        response = self.client.get(reverse("public_profile", args=[self.user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["friendship_state"], "self")
        self.assertContains(response, reverse("profile"))
        self.assertContains(response, "Profileinstellungen")

    def test_header_profile_link_opens_own_public_profile(self):
        response = self.client.get(reverse("home"))
        public_profile_url = reverse("public_profile", args=[self.user.id])

        self.assertContains(response, f'href="{public_profile_url}"')
        self.assertNotContains(
            response,
            f'href="{reverse("profile")}" class="profile-menu-item"',
        )

    def test_public_profile_hides_private_achievement_categories_from_strangers(self):
        other_user = get_user_model().objects.create_user(
            username="privatebadges",
            password="testpass-123",
        )
        Note.objects.create(user=other_user, title="Private Notiz")
        ChatRoom.objects.create(room_type=ChatRoom.ROOM_GROUP, name="Privat", created_by=other_user)
        FileShare.objects.create(
            owner=other_user,
            file=SimpleUploadedFile("private.txt", b"private", content_type="text/plain"),
            original_name="private.txt",
            size=7,
            content_type="text/plain",
            token="private-badge-share-token",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        category_keys = {category["key"] for category in response.context["achievement_summary"]["categories"]}
        self.assertIn("profile", category_keys)
        self.assertNotIn("notes", category_keys)
        self.assertNotIn("chat", category_keys)
        self.assertNotIn("uploads", category_keys)

    def test_public_profile_hides_achievements_when_disabled(self):
        other_user = get_user_model().objects.create_user(
            username="hiddenachievements",
            password="testpass-123",
        )
        UserProfile.objects.create(user=other_user, privacy_show_achievements=False)

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_achievements"])
        self.assertIsNone(response.context["achievement_summary"])
        self.assertTemplateNotUsed(response, "app/includes/achievement_panel.html")

    def test_send_friend_request_from_public_profile(self):
        other_user = get_user_model().objects.create_user(
            username="friendtarget",
            password="testpass-123",
        )

        response = self.client.post(reverse("friendship_action", args=[other_user.id]), {
            "action": "send",
            "next": reverse("public_profile", args=[other_user.id]),
        })

        self.assertRedirects(response, reverse("public_profile", args=[other_user.id]))
        friendship = Friendship.objects.get(from_user=self.user, to_user=other_user)
        self.assertEqual(friendship.status, Friendship.STATUS_PENDING)

    def test_accept_friend_request(self):
        other_user = get_user_model().objects.create_user(
            username="requestsender",
            password="testpass-123",
        )
        friendship = Friendship.objects.create(from_user=other_user, to_user=self.user)

        response = self.client.post(reverse("friendship_action", args=[other_user.id]), {
            "action": "accept",
            "next": reverse("profile"),
        })

        self.assertRedirects(response, reverse("profile"))
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.STATUS_ACCEPTED)

    def test_friends_list_page_shows_accepted_friends_only(self):
        accepted_user = get_user_model().objects.create_user(
            username="acceptedfriend",
            password="testpass-123",
        )
        pending_user = get_user_model().objects.create_user(
            username="pendingfriend",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=accepted_user,
            status=Friendship.STATUS_ACCEPTED,
        )
        Friendship.objects.create(from_user=self.user, to_user=pending_user)

        response = self.client.get(reverse("friends_list", args=[self.user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/friends.html")
        usernames = [profile.user.username for profile in response.context["friends"]]
        self.assertIn("acceptedfriend", usernames)
        self.assertNotIn("pendingfriend", usernames)

    def test_public_profile_uses_profile_card_design_for_hero(self):
        other_user = get_user_model().objects.create_user(
            username="cardhero",
            password="testpass-123",
        )
        UserProfile.objects.create(
            user=other_user,
            profile_card_primary="#123456",
            profile_card_secondary="#abcdef",
            profile_card_tertiary="#fedcba",
            profile_card_text="#ffffff",
            profile_card_border="#00ff99",
            profile_card_badge_bg="#112233",
            profile_card_badge_text="HeroBadge",
            profile_card_style="glass",
            profile_card_pattern="grid",
            profile_card_radius="bold",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertContains(response, "public-profile-card-theme")
        self.assertContains(response, "profile-showcase-card-glass")
        self.assertContains(response, "profile-showcase-pattern-grid")
        self.assertContains(response, "--profile-card-primary: #123456")
        self.assertContains(response, "--profile-card-secondary: #abcdef")
        self.assertContains(response, "--profile-card-border: #00ff99")
        self.assertContains(response, "HeroBadge")

    def test_public_profile_shows_profile_users_human_benchmark_highscores(self):
        other_user = get_user_model().objects.create_user(
            username="benchmarkuser",
            password="testpass-123",
        )

        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=180,
            display_score="180 ms",
        )
        HumanBenchmarkHighScore.objects.create(
            user=other_user,
            game=HumanBenchmarkScore.GAME_TYPING,
            score=82,
            display_score="82 WPM",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        highscores = response.context["benchmark_highscores"]

        self.assertContains(response, "82 WPM")
        self.assertNotContains(response, "180 ms")
        self.assertEqual(len(highscores), len(HumanBenchmarkScore.GAME_CHOICES))
        typing_row = next(
            item for item in highscores
            if item["game"] == HumanBenchmarkScore.GAME_TYPING
        )

        self.assertEqual(typing_row["highscore"].display_score, "82 WPM")

    def test_cookie_clicker_score_api_creates_and_keeps_best_score(self):
        response = self.client.post(
            reverse("cookie-clicker-score-api"),
            data=json.dumps({
                "score": 12345,
                "display_score": "12.3K",
                "cps": 42.5,
                "click_power": 7.25,
                "stardust": 2,
                "ascensions": 1,
                "achievements_count": 5,
                "upgrades_count": 9,
                "buildings_count": 16,
                "details": {"total_clicks": 88},
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["new_highscore"])

        highscore = CookieClickerHighScore.objects.get(user=self.user)
        self.assertEqual(highscore.score, 12345)
        self.assertEqual(highscore.display_score, "12.3K")
        self.assertEqual(highscore.cps, 42.5)
        self.assertEqual(highscore.details["total_clicks"], 88)

        lower_response = self.client.post(
            reverse("cookie-clicker-score-api"),
            data=json.dumps({
                "score": 100,
                "display_score": "100",
                "cps": 1,
                "click_power": 1,
            }),
            content_type="application/json",
        )

        self.assertEqual(lower_response.status_code, 200)
        self.assertFalse(lower_response.json()["new_highscore"])
        highscore.refresh_from_db()
        self.assertEqual(highscore.score, 12345)
        self.assertEqual(highscore.display_score, "12.3K")

    def test_cookie_clicker_page_sets_presence_status(self):
        response = self.client.get(reverse("cookie-clicker"))

        self.assertEqual(response.status_code, 200)
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "cookie_cosmos")
        self.assertEqual(presence.active_game_label, "spielt Cookie Cosmos")
        self.assertIsNotNone(presence.active_game_updated_at)

    def test_cookie_clicker_score_api_refreshes_presence_status(self):
        response = self.client.post(
            reverse("cookie-clicker-score-api"),
            data=json.dumps({
                "score": 12345,
                "cps": 42.5,
                "click_power": 7.25,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "cookie_cosmos")
        self.assertEqual(presence.active_game_label, "spielt Cookie Cosmos")

    def test_cookie_clicker_score_api_rejects_non_finite_score(self):
        response = self.client.post(
            reverse("cookie-clicker-score-api"),
            data='{"score": NaN, "cps": 0, "click_power": 1}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(CookieClickerHighScore.objects.filter(user=self.user).exists())

    def test_cookie_cosmos_v2_page_sets_presence_status(self):
        response = self.client.get(reverse("cookie-cosmos-v2"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/cookie_cosmos_v2.html")
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "cookie_cosmos_v2")
        self.assertEqual(presence.active_game_label, "spielt Cookie Cosmos V2")

    def test_nebula_forge_tycoon_page_sets_presence_status(self):
        response = self.client.get(reverse("nebula-forge-tycoon"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/nebula_forge_tycoon.html")
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "nebula_forge_tycoon")
        self.assertEqual(presence.active_game_label, "spielt Nebula Forge Tycoon")

    def test_cookie_cosmos_v2_save_api_persists_save_and_rate_limits(self):
        payload = {
            "save_data": {
                "version": 2,
                "cookies": 1500,
                "lifetimeCookies": 2500,
                "prestigeLevel": 2,
                "buildings": {"hand_mixer": 3},
            },
            "cookies": 1500,
            "lifetime_cookies": 2500,
            "cps": 12.5,
            "click_power": 4.5,
            "prestige_level": 2,
            "prestige_crumbs": 1,
            "achievements_count": 3,
            "upgrades_count": 2,
            "buildings_count": 3,
        }

        response = self.client.post(
            reverse("cookie-cosmos-v2-save-api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        save = CookieCosmosV2Save.objects.get(user=self.user)
        self.assertEqual(save.save_data["prestigeLevel"], 2)
        self.assertEqual(save.prestige_level, 2)
        self.assertEqual(save.lifetime_cookies, 2500)
        self.assertIsNotNone(save.last_manual_save)

        limited_response = self.client.post(
            reverse("cookie-cosmos-v2-save-api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(limited_response.status_code, 429)
        self.assertGreater(limited_response.json()["next_save_in_seconds"], 0)

    def test_cookie_cosmos_v2_load_api_returns_saved_state(self):
        CookieCosmosV2Save.objects.create(
            user=self.user,
            save_data={"version": 2, "cookies": 99, "prestigeLevel": 3},
            cookies=99,
            lifetime_cookies=1234,
            prestige_level=3,
        )

        response = self.client.get(reverse("cookie-cosmos-v2-load-api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["save_data"]["prestigeLevel"], 3)
        self.assertEqual(response.json()["save"]["prestige_level"], 3)

    def test_profile_settings_hide_cookie_highscore_but_public_profile_shows_it(self):
        CookieClickerHighScore.objects.create(
            user=self.user,
            score=987654,
            display_score="987.7K",
            cps=321.4,
            click_power=12.5,
            stardust=4,
            ascensions=2,
            achievements_count=11,
            upgrades_count=18,
            buildings_count=44,
        )

        settings_response = self.client.get(reverse("profile"))
        public_response = self.client.get(reverse("public_profile", args=[self.user.id]))

        self.assertNotContains(settings_response, "987.7K")
        self.assertNotIn("cookie_highscore", settings_response.context)
        self.assertContains(public_response, "987.7K")
        self.assertEqual(public_response.context["cookie_highscore"].display_score, "987.7K")

    def test_profile_game_card_settings_can_be_reordered_and_hidden(self):
        response = self.client.post(reverse("profile"), {
            "profile_action": "game_cards",
            "game_card_order": ["skribble", "cookie_cosmos", "human_benchmark"],
            "game_card_visible": ["skribble", "human_benchmark"],
        })

        self.assertRedirects(response, reverse("profile"))
        profile = UserProfile.objects.get(user=self.user)

        self.assertEqual(profile.profile_game_cards[0], {"key": "skribble", "visible": True})
        self.assertEqual(profile.profile_game_cards[1], {"key": "cookie_cosmos", "visible": False})
        self.assertEqual(profile.profile_game_cards[2], {"key": "human_benchmark", "visible": True})

    def test_public_profile_uses_configured_game_card_order_and_visibility(self):
        other_user = get_user_model().objects.create_user(
            username="gamecards",
            password="testpass-123",
        )
        UserProfile.objects.create(
            user=other_user,
            profile_game_cards=[
                {"key": "skribble", "visible": True},
                {"key": "cookie_cosmos", "visible": False},
                {"key": "human_benchmark", "visible": True},
            ],
        )
        HumanBenchmarkHighScore.objects.create(
            user=other_user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=210,
            display_score="210 ms",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        card_keys = [card["key"] for card in response.context["profile_game_cards"]]
        self.assertEqual(card_keys[:2], ["skribble", "human_benchmark"])
        self.assertNotIn("cookie_cosmos", card_keys)
        self.assertContains(response, "210 ms")

    def test_public_profile_shows_cookie_clicker_highscore_when_visible(self):
        other_user = get_user_model().objects.create_user(
            username="cookiepublic",
            password="testpass-123",
        )
        CookieClickerHighScore.objects.create(
            user=other_user,
            score=45000000,
            display_score="45M",
            cps=1200,
            click_power=32,
            achievements_count=8,
            upgrades_count=14,
            buildings_count=30,
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertContains(response, "Cookie Cosmos")
        self.assertContains(response, "45M")
        self.assertEqual(response.context["cookie_highscore"].display_score, "45M")

    def test_public_profile_hides_cookie_clicker_highscore_when_private(self):
        other_user = get_user_model().objects.create_user(
            username="cookieprivate",
            password="testpass-123",
        )
        UserProfile.objects.create(user=other_user, privacy_show_highscores=False)
        CookieClickerHighScore.objects.create(
            user=other_user,
            score=99000000,
            display_score="99M",
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertIsNone(response.context["cookie_highscore"])
        self.assertNotContains(response, "99M")


class HomeViewTests(BaseTestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/home.html")
        self.assertIn("sections", response.context)
        self.assertIn("home_labels", response.context)

    def test_header_has_visual_identity_and_current_page_state(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'class="header-brand-slot"')
        self.assertContains(response, 'class="logo-mark"')
        self.assertContains(response, 'class="logo-wordmark"')
        self.assertContains(response, 'id="header-language-select"')
        self.assertContains(response, 'class="nav-primary-link active" aria-current="page"')
        self.assertContains(response, 'aria-controls="games-menu-dropdown"')
        self.assertContains(response, 'aria-controls="google-apps-menu-dropdown"')
        self.assertContains(response, 'aria-controls="menu-dropdown"')

        stylesheet = (settings.BASE_DIR / "app" / "static" / "app" / "css" / "core.css").read_text(encoding="utf-8")
        self.assertIn("Verfeinerter, mit den Menüs abgestimmter Header", stylesheet)
        self.assertIn("nav#site-header .header-brand-slot", stylesheet)
        self.assertRegex(stylesheet, r"nav#site-header \.logo\s*\{[^}]*flex: 0 0 auto")
        self.assertIn("nav#site-header .navigation > a.active", stylesheet)

    def test_games_menu_has_an_individual_theme_for_every_game(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "data-game-theme=", count=17)
        for theme in (
            "human", "racing", "2048", "snake", "cookie", "cookie-v2", "nebula",
            "werewolf", "tictactoe", "battleship", "connectfour", "stadtlandfluss",
            "uno", "kniffel", "pong", "hangman", "skribble",
        ):
            self.assertIn(f'data-game-theme="{theme}"', content)

    def test_tools_menu_has_an_individual_theme_for_every_visible_tool(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "data-tool-theme=", count=19)
        for theme in (
            "clock", "notes", "file-share", "feedback", "roadmap", "changelog",
            "calculator", "fuel", "units", "randomizer", "qr", "genius", "images",
            "converter", "palette", "profile-card", "avatar", "stream-deck", "obs",
        ):
            self.assertIn(f'data-tool-theme="{theme}"', content)

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        staff_response = self.client.get(reverse("home"))
        self.assertContains(staff_response, "data-tool-theme=", count=21)
        self.assertContains(staff_response, 'data-tool-theme="moderation"')
        self.assertContains(staff_response, 'data-tool-theme="server"')

    def test_google_menu_has_an_individual_theme_for_every_app(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "data-google-theme=", count=11)
        for theme in (
            "search", "maps", "youtube", "news", "photos", "gmail", "drive",
            "calendar", "translate", "play", "gemini",
        ):
            self.assertIn(f'data-google-theme="{theme}"', content)

    def test_global_search_results_include_visual_theme_keys(self):
        response = self.client.get(reverse("global_search_api"))

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(results)
        self.assertTrue(all(result.get("theme") for result in results))
        self.assertEqual(results[0]["theme"], "home")
        self.assertIn("weather", {result["theme"] for result in results})

    def test_global_search_uses_content_theme_for_note_results(self):
        Note.objects.create(user=self.user, title="Visuelle Suche", content="Farbiges Ergebnis")

        response = self.client.get(reverse("global_search_api"), {"q": "Visuelle Suche"})

        self.assertEqual(response.status_code, 200)
        note_result = next(result for result in response.json()["results"] if result["kind"] == "Notiz")
        self.assertEqual(note_result["theme"], "note-result")

    def test_global_search_frontend_renders_individual_result_themes(self):
        script = (settings.BASE_DIR / "app" / "static" / "app" / "js" / "base.js").read_text(encoding="utf-8")

        self.assertIn("resolveGlobalSearchTheme", script)
        self.assertIn('data-search-theme="${escapeHtml(theme.key)}"', script)
        self.assertIn("--search-result-start:${theme.start}", script)

    def test_home_has_accessible_heading_and_search_combobox(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<h1 class="sr-only">MyTools Dashboard</h1>', html=True)
        self.assertContains(response, 'role="search"')
        self.assertContains(response, 'for="google-search-input"')
        self.assertContains(response, 'role="combobox"')
        self.assertContains(response, 'aria-controls="suggestions-box"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'role="listbox"')

    def test_home_modals_have_accessible_dialog_semantics(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'class="shortcut-modal-content" role="dialog"', count=3)
        self.assertContains(response, 'id="onboarding-dialog"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, 'id="widget-modal" aria-hidden="true"')
        self.assertContains(response, 'aria-labelledby="widget-modal-title"')
        self.assertContains(response, 'aria-labelledby="shortcut-modal-title"')
        self.assertContains(response, 'aria-labelledby="section-modal-title"')
        self.assertContains(response, 'aria-label="Widget-Dialog schließen"')
        self.assertContains(response, 'aria-label="Verknüpfungsdialog schließen"')
        self.assertContains(response, 'aria-label="Bereichsdialog schließen"')

    def test_home_javascript_manages_focus_without_mobile_autofocus(self):
        script = (settings.BASE_DIR / "app" / "static" / "app" / "js" / "home.js").read_text(encoding="utf-8")

        self.assertIn('(pointer: fine)', script)
        self.assertIn('modalReturnFocus', script)
        self.assertIn('event.key !== "Tab"', script)
        self.assertIn('returnFocus.focus({ preventScroll: true })', script)
        self.assertNotIn('event.key === "Tab" && currentFirstSuggestion', script)

    def test_home_delete_actions_use_accessible_undo_toasts(self):
        response = self.client.get(reverse("home"))
        script = (settings.BASE_DIR / "app" / "static" / "app" / "js" / "home.js").read_text(encoding="utf-8")

        self.assertContains(response, "data-delete-undo-region")
        self.assertContains(response, 'aria-live="polite"')
        self.assertEqual(response.context["home_labels"]["undoDelete"], "Rückgängig")
        self.assertIn("deleteUndoDelay = 7000", script)
        self.assertIn(".delete-widget-form, .delete-section-form, .delete-shortcut-form", script)
        self.assertIn('"X-Requested-With": "XMLHttpRequest"', script)

    def test_ajax_delete_actions_return_json(self):
        section = ShortcutSection.objects.create(name="Temporär")
        shortcut = Shortcut.objects.create(section=section, name="Kurz", url="https://example.com")
        widget = HomeWidget.objects.create(title="Temporär", widget_type=HomeWidget.WIDGET_STATS)

        shortcut_response = self.client.post(
            reverse("home"),
            {"action": "delete_shortcut", "shortcut_id": shortcut.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        section_response = self.client.post(
            reverse("home"),
            {"action": "delete_section", "section_id": section.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        widget_response = self.client.post(
            reverse("home"),
            {"action": "delete_widget", "widget_id": widget.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(shortcut_response.json(), {"success": True, "deleted": "shortcut"})
        self.assertEqual(section_response.json(), {"success": True, "deleted": "section"})
        self.assertEqual(widget_response.json(), {"success": True, "deleted": "widget"})
        self.assertFalse(Shortcut.objects.filter(id=shortcut.id).exists())
        self.assertFalse(ShortcutSection.objects.filter(id=section.id).exists())
        self.assertFalse(HomeWidget.objects.filter(id=widget.id).exists())

    def test_empty_dashboard_shows_onboarding(self):
        response = self.client.get(reverse("home"))

        self.assertTrue(response.context["show_onboarding"])
        self.assertContains(response, 'id="onboarding-modal"')
        self.assertContains(response, "Alltag")
        self.assertContains(response, "Gaming")
        self.assertContains(response, "Homelab")

    def test_dashboard_with_existing_content_does_not_show_onboarding(self):
        section = ShortcutSection.objects.create(name="Verknüpfungen")
        Shortcut.objects.create(
            section=section,
            name="Vorhanden",
            url="https://example.com",
        )

        response = self.client.get(reverse("home"))

        self.assertFalse(response.context["show_onboarding"])
        self.assertNotContains(response, 'id="onboarding-modal"')

    def test_everyday_onboarding_creates_widgets_and_shortcuts(self):
        response = self.client.post(reverse("home"), {
            "action": "complete_onboarding",
            "onboarding_template": "everyday",
        })

        self.assertRedirects(response, reverse("home"))
        preference = HomeLayoutPreference.objects.get(user=self.user)
        self.assertTrue(preference.onboarding_completed)
        self.assertEqual(HomeWidget.objects.filter(user=self.user).count(), 4)
        self.assertEqual(Shortcut.objects.filter(user=self.user).count(), 3)
        self.assertTrue(HomeWidget.objects.filter(user=self.user, widget_type=HomeWidget.WIDGET_WEATHER).exists())
        self.assertTrue(Shortcut.objects.filter(user=self.user, name="Gmail").exists())

    def test_gaming_onboarding_creates_gaming_selection(self):
        self.client.post(reverse("home"), {
            "action": "complete_onboarding",
            "onboarding_template": "gaming",
        })

        widget_types = set(HomeWidget.objects.filter(user=self.user).values_list("widget_type", flat=True))
        self.assertSetEqual(widget_types, {
            HomeWidget.WIDGET_CHAT,
            HomeWidget.WIDGET_FRIENDS,
            HomeWidget.WIDGET_TICTACTOE,
            HomeWidget.WIDGET_BENCHMARK,
        })
        self.assertSetEqual(
            set(Shortcut.objects.filter(user=self.user).values_list("name", flat=True)),
            {"Steam", "Twitch", "Discord"},
        )

    def test_homelab_onboarding_creates_service_shortcuts(self):
        self.client.post(reverse("home"), {
            "action": "complete_onboarding",
            "onboarding_template": "homelab",
        })

        self.assertTrue(Shortcut.objects.filter(user=self.user, name="CasaOS").exists())
        self.assertTrue(Shortcut.objects.filter(user=self.user, name="Home Assistant").exists())
        self.assertTrue(Shortcut.objects.filter(user=self.user, name="Nextcloud").exists())
        self.assertEqual(HomeWidget.objects.filter(user=self.user).count(), 3)

    def test_onboarding_can_be_skipped(self):
        response = self.client.post(reverse("home"), {
            "action": "complete_onboarding",
            "onboarding_template": "blank",
        })

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(HomeLayoutPreference.objects.get(user=self.user).onboarding_completed)
        self.assertFalse(HomeWidget.objects.filter(user=self.user).exists())
        self.assertFalse(Shortcut.objects.filter(user=self.user).exists())

    def test_completed_onboarding_is_idempotent(self):
        payload = {
            "action": "complete_onboarding",
            "onboarding_template": "everyday",
        }
        self.client.post(reverse("home"), payload)
        self.client.post(reverse("home"), payload)

        self.assertEqual(HomeWidget.objects.filter(user=self.user).count(), 4)
        self.assertEqual(Shortcut.objects.filter(user=self.user).count(), 3)

    def test_home_creates_default_section(self):
        self.assertFalse(ShortcutSection.objects.filter(name="Verknüpfungen").exists())

        self.client.get(reverse("home"))

        self.assertTrue(ShortcutSection.objects.filter(name="Verknüpfungen").exists())

    def test_old_shortcuts_without_section_are_moved_to_default_section(self):
        shortcut = Shortcut.objects.create(
            section=None,
            name="Altes Tool",
            url="https://example.com",
            icon="fa-solid fa-link",
        )

        self.client.get(reverse("home"))
        shortcut.refresh_from_db()

        self.assertIsNotNone(shortcut.section)
        self.assertEqual(shortcut.section.name, "Verknüpfungen")

    def test_add_section_creates_section_with_color_and_next_order(self):
        ShortcutSection.objects.create(name="Verknüpfungen", order=0)

        response = self.client.post(reverse("home"), {
            "action": "add_section",
            "section_name": "Server",
            "section_color": "green",
        })

        self.assertRedirects(response, reverse("home"))

        section = ShortcutSection.objects.get(name="Server")
        self.assertEqual(section.color, "green")
        self.assertEqual(section.order, 2)

    def test_add_empty_section_does_not_create_extra_section(self):
        response = self.client.post(reverse("home"), {
            "action": "add_section",
            "section_name": "",
        })

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(ShortcutSection.objects.count(), 1)
        self.assertTrue(ShortcutSection.objects.filter(name="Verknüpfungen").exists())

    def test_edit_section_updates_name_and_color(self):
        section = ShortcutSection.objects.create(name="Alt", color="blue")

        response = self.client.post(reverse("home"), {
            "action": "edit_section",
            "section_id": section.id,
            "section_name": "Neu",
            "section_color": "purple",
        })

        self.assertRedirects(response, reverse("home"))

        section.refresh_from_db()
        self.assertEqual(section.name, "Neu")
        self.assertEqual(section.color, "purple")

    def test_delete_section(self):
        section = ShortcutSection.objects.create(name="Server")
        shortcut = Shortcut.objects.create(section=section, name="Dienst", url="https://example.com")

        response = self.client.post(reverse("home"), {
            "action": "delete_section",
            "section_id": section.id,
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(ShortcutSection.objects.filter(id=section.id).exists())
        self.assertFalse(Shortcut.objects.filter(id=shortcut.id).exists())
        trashed_shortcut = Shortcut.all_objects.get(id=shortcut.id)
        self.assertIsNotNone(trashed_shortcut.deleted_at)
        self.assertEqual(trashed_shortcut.section.name, "Verknüpfungen")

    def test_default_section_cannot_be_deleted(self):
        default_section = ShortcutSection.objects.create(name="Verknüpfungen")

        response = self.client.post(reverse("home"), {
            "action": "delete_section",
            "section_id": default_section.id,
        })

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(ShortcutSection.objects.filter(id=default_section.id).exists())

    def test_toggle_section_collapse(self):
        section = ShortcutSection.objects.create(name="Server", is_collapsed=False)

        response = self.client.post(reverse("home"), {
            "action": "toggle_section_collapse",
            "section_id": section.id,
        })

        self.assertRedirects(response, reverse("home"))

        section.refresh_from_db()
        self.assertTrue(section.is_collapsed)

    def test_add_shortcut_adds_https_default_icon_and_order(self):
        section = ShortcutSection.objects.create(name="Coding")
        Shortcut.objects.create(
            section=section,
            name="Alt",
            url="https://alt.de",
            order=0,
        )

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "GitHub",
            "url": "github.com",
            "icon": "",
            "custom_icon": "",
        })

        self.assertRedirects(response, reverse("home"))

        shortcut = Shortcut.objects.get(name="GitHub")
        self.assertEqual(shortcut.section, section)
        self.assertEqual(shortcut.url, "https://github.com")
        self.assertEqual(shortcut.icon, "fa-solid fa-link")
        self.assertEqual(shortcut.order, 1)

    def test_add_shortcut_with_custom_icon_overwrites_selected_icon(self):
        section = ShortcutSection.objects.create(name="Server")

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "CasaOS",
            "url": "https://casaos.io",
            "icon": "fa-solid fa-link",
            "custom_icon": "fa-solid fa-server",
        })

        self.assertRedirects(response, reverse("home"))

        shortcut = Shortcut.objects.get(name="CasaOS")
        self.assertEqual(shortcut.icon, "fa-solid fa-server")

    def test_add_shortcut_without_name_or_url_does_not_create_shortcut(self):
        section = ShortcutSection.objects.create(name="Coding")

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "",
            "url": "",
        })

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(Shortcut.objects.count(), 0)

    def test_edit_shortcut_updates_data_and_preserves_http_url(self):
        old_section = ShortcutSection.objects.create(name="Alt")
        new_section = ShortcutSection.objects.create(name="Neu")

        shortcut = Shortcut.objects.create(
            section=old_section,
            name="Alt",
            url="https://alt.de",
            icon="fa-solid fa-link",
        )

        response = self.client.post(reverse("home"), {
            "action": "edit_shortcut",
            "shortcut_id": shortcut.id,
            "section_id": new_section.id,
            "name": "Neu",
            "url": "http://example.com",
            "icon": "fa-solid fa-code",
            "custom_icon": "",
        })

        self.assertRedirects(response, reverse("home"))

        shortcut.refresh_from_db()
        self.assertEqual(shortcut.section, new_section)
        self.assertEqual(shortcut.name, "Neu")
        self.assertEqual(shortcut.url, "http://example.com")
        self.assertEqual(shortcut.icon, "fa-solid fa-code")

    def test_edit_shortcut_can_remove_existing_image(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="Django",
            url="https://www.djangoproject.com",
            icon="fa-solid fa-code",
            image=self.get_test_image("shortcut.png"),
        )

        response = self.client.post(reverse("home"), {
            "action": "edit_shortcut",
            "shortcut_id": shortcut.id,
            "section_id": section.id,
            "name": "Django",
            "url": "https://www.djangoproject.com",
            "icon": "fa-solid fa-code",
            "custom_icon": "",
            "remove_image": "1",
        })

        self.assertRedirects(response, reverse("home"))

        shortcut.refresh_from_db()
        self.assertFalse(shortcut.image)

    def test_delete_shortcut(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="Django",
            url="https://www.djangoproject.com",
            icon="fa-solid fa-code",
        )

        response = self.client.post(reverse("home"), {
            "action": "delete_shortcut",
            "shortcut_id": shortcut.id,
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(Shortcut.objects.filter(id=shortcut.id).exists())
        self.assertTrue(Shortcut.all_objects.filter(id=shortcut.id, deleted_at__isnull=False).exists())

    def test_toggle_favorite(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="Django",
            url="https://www.djangoproject.com",
            is_favorite=False,
        )

        response = self.client.post(reverse("home"), {
            "action": "toggle_favorite",
            "shortcut_id": shortcut.id,
        })

        self.assertRedirects(response, reverse("home"))

        shortcut.refresh_from_db()
        self.assertTrue(shortcut.is_favorite)

    def test_update_shortcut_order_json(self):
        section_one = ShortcutSection.objects.create(name="Eins")
        section_two = ShortcutSection.objects.create(name="Zwei")

        shortcut = Shortcut.objects.create(
            section=section_one,
            name="Tool",
            url="https://tool.de",
            order=0,
        )

        response = self.client.post(
            reverse("home"),
            data=json.dumps({
                "action": "update_shortcut_order",
                "shortcuts": [
                    {
                        "id": shortcut.id,
                        "section_id": section_two.id,
                        "order": 5,
                    },
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        shortcut.refresh_from_db()
        self.assertEqual(shortcut.section, section_two)
        self.assertEqual(shortcut.order, 5)

    def test_update_section_order_json(self):
        section = ShortcutSection.objects.create(name="Server", order=0)

        response = self.client.post(
            reverse("home"),
            data=json.dumps({
                "action": "update_section_order",
                "sections": [
                    {
                        "id": section.id,
                        "order": 9,
                    },
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        section.refresh_from_db()
        self.assertEqual(section.order, 9)

    def test_invalid_json_returns_error(self):
        response = self.client.post(
            reverse("home"),
            data="{kaputt",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_unknown_json_action_returns_error(self):
        response = self.client.post(
            reverse("home"),
            data=json.dumps({
                "action": "does_not_exist",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])


    def test_add_widget_creates_widget_with_valid_data(self):
        weather_location = WeatherLocation.objects.create(name="Berlin")

        response = self.client.post(reverse("home"), {
            "action": "add_widget",
            "widget_title": "Wetter Berlin",
            "widget_type": HomeWidget.WIDGET_WEATHER,
            "widget_color": "green",
            "weather_location": weather_location.id,
        })

        self.assertRedirects(response, reverse("home"))

        widget = HomeWidget.objects.get(title="Wetter Berlin")
        self.assertEqual(widget.user, self.user)
        self.assertEqual(widget.widget_type, HomeWidget.WIDGET_WEATHER)
        self.assertEqual(widget.color, "green")
        self.assertEqual(widget.weather_location, weather_location)
        self.assertEqual(widget.order, 1)

    def test_add_widget_uses_fallbacks_for_invalid_or_empty_data(self):
        response = self.client.post(reverse("home"), {
            "action": "add_widget",
            "widget_title": "",
            "widget_type": "kaputt",
            "widget_color": "pink",
        })

        self.assertRedirects(response, reverse("home"))

        widget = HomeWidget.objects.get()
        self.assertEqual(widget.title, "Wetter")
        self.assertEqual(widget.widget_type, HomeWidget.WIDGET_WEATHER)
        self.assertEqual(widget.color, "blue")

    def test_edit_widget_updates_widget(self):
        old_location = WeatherLocation.objects.create(name="Berlin")
        new_location = WeatherLocation.objects.create(name="Osnabrück")
        widget = HomeWidget.objects.create(
            user=self.user,
            title="Alt",
            widget_type=HomeWidget.WIDGET_WEATHER,
            color="blue",
            weather_location=old_location,
        )

        response = self.client.post(reverse("home"), {
            "action": "edit_widget",
            "widget_id": widget.id,
            "widget_title": "Neue Notizen",
            "widget_type": HomeWidget.WIDGET_NOTES,
            "widget_color": "purple",
            "weather_location": new_location.id,
        })

        self.assertRedirects(response, reverse("home"))

        widget.refresh_from_db()
        self.assertEqual(widget.title, "Neue Notizen")
        self.assertEqual(widget.widget_type, HomeWidget.WIDGET_NOTES)
        self.assertEqual(widget.color, "purple")
        self.assertEqual(widget.weather_location, new_location)

    def test_delete_widget(self):
        widget = HomeWidget.objects.create(
            user=self.user,
            title="Weg",
            widget_type=HomeWidget.WIDGET_STATS,
        )

        response = self.client.post(reverse("home"), {
            "action": "delete_widget",
            "widget_id": widget.id,
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(HomeWidget.objects.filter(id=widget.id).exists())
        self.assertTrue(HomeWidget.all_objects.filter(id=widget.id, deleted_at__isnull=False).exists())

    def test_update_widget_order_json(self):
        widget = HomeWidget.objects.create(
            user=self.user,
            title="Stats",
            widget_type=HomeWidget.WIDGET_STATS,
            order=0,
        )

        response = self.client.post(
            reverse("home"),
            data=json.dumps({
                "action": "update_widget_order",
                "widgets": [
                    {
                        "id": widget.id,
                        "order": 7,
                    },
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        widget.refresh_from_db()
        self.assertEqual(widget.order, 7)

    def test_update_home_layout_order_json_updates_widgets_and_sections(self):
        section = ShortcutSection.objects.create(name="Server", order=2)
        preference = HomeLayoutPreference.objects.create(user=self.user, widget_area_order=1)

        response = self.client.post(
            reverse("home"),
            data=json.dumps({
                "action": "update_home_layout_order",
                "items": [
                    {
                        "type": "widgets",
                        "order": 5,
                    },
                    {
                        "type": "section",
                        "id": section.id,
                        "order": 6,
                    },
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        preference.refresh_from_db()
        section.refresh_from_db()

        self.assertEqual(preference.widget_area_order, 5)
        self.assertEqual(section.order, 6)


class TrashTests(BaseTestCase):
    def create_deleted_items(self):
        section = ShortcutSection.objects.create(name="Papierkorb-Test")
        note = Note.objects.create(title="Gelöschte Notiz", content="Inhalt")
        widget = HomeWidget.objects.create(title="Gelöschtes Widget", widget_type=HomeWidget.WIDGET_STATS)
        shortcut = Shortcut.objects.create(section=section, name="Gelöschter Link", url="https://example.com")
        share = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("trash.txt", b"trash", content_type="text/plain"),
            original_name="trash.txt",
            size=5,
            content_type="text/plain",
            token="trash-test-token",
            is_public_link=True,
        )
        for item in (note, widget, shortcut, share):
            item.move_to_trash()
        return note, widget, shortcut, share

    def test_trash_page_lists_all_supported_types(self):
        self.create_deleted_items()

        response = self.client.get(reverse("trash"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/trash.html")
        self.assertEqual(response.context["trash_total"], 4)
        self.assertContains(response, "Gelöschte Notiz")
        self.assertContains(response, "Gelöschtes Widget")
        self.assertContains(response, "Gelöschter Link")
        self.assertContains(response, "trash.txt")

    def test_restore_makes_all_supported_types_active_again(self):
        note, widget, shortcut, share = self.create_deleted_items()

        for item_type, item in (
            ("note", note),
            ("widget", widget),
            ("shortcut", shortcut),
            ("file", share),
        ):
            response = self.client.post(reverse("trash_restore", args=[item_type, item.id]))
            self.assertRedirects(response, reverse("trash"))

        self.assertTrue(Note.objects.filter(id=note.id).exists())
        self.assertTrue(HomeWidget.objects.filter(id=widget.id).exists())
        self.assertTrue(Shortcut.objects.filter(id=shortcut.id).exists())
        self.assertTrue(FileShare.objects.filter(id=share.id).exists())

    def test_permanent_file_delete_removes_database_row_and_storage_file(self):
        share = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("permanent.txt", b"bye", content_type="text/plain"),
            original_name="permanent.txt",
            size=3,
            content_type="text/plain",
            token="trash-permanent-token",
        )
        file_name = share.file.name
        storage = share.file.storage
        share.move_to_trash()

        response = self.client.post(reverse("trash_delete", args=["file", share.id]))

        self.assertRedirects(response, reverse("trash"))
        self.assertFalse(FileShare.all_objects.filter(id=share.id).exists())
        self.assertFalse(storage.exists(file_name))

    def test_expired_items_are_purged_after_thirty_days(self):
        old_note = Note.objects.create(title="Alt")
        recent_note = Note.objects.create(title="Neu")
        now = timezone.now()
        old_note.move_to_trash()
        recent_note.move_to_trash()
        Note.all_objects.filter(id=old_note.id).update(deleted_at=now - timedelta(days=31))
        Note.all_objects.filter(id=recent_note.id).update(deleted_at=now - timedelta(days=29))

        deleted_count = purge_expired_trash(user=self.user, now=now)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(Note.all_objects.filter(id=old_note.id).exists())
        self.assertTrue(Note.all_objects.filter(id=recent_note.id).exists())

    def test_users_cannot_view_or_restore_other_users_trash(self):
        other_user = get_user_model().objects.create_user(username="trash-other", password="testpass-123")
        note = Note.objects.create(user=other_user, title="Privat")
        note.move_to_trash()

        response = self.client.get(reverse("trash"))
        restore_response = self.client.post(reverse("trash_restore", args=["note", note.id]))

        self.assertNotContains(response, "Privat")
        self.assertEqual(restore_response.status_code, 404)
        self.assertFalse(Note.objects.filter(id=note.id).exists())

    def test_empty_trash_permanently_deletes_all_owned_items(self):
        self.create_deleted_items()

        response = self.client.post(reverse("trash_empty"))

        self.assertRedirects(response, reverse("trash"))
        self.assertFalse(Note.all_objects.filter(user=self.user, deleted_at__isnull=False).exists())
        self.assertFalse(HomeWidget.all_objects.filter(user=self.user, deleted_at__isnull=False).exists())
        self.assertFalse(Shortcut.all_objects.filter(user=self.user, deleted_at__isnull=False).exists())
        self.assertFalse(FileShare.all_objects.filter(owner=self.user, deleted_at__isnull=False).exists())


class StaticPageTests(BaseTestCase):
    def test_about_page_loads(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/about.html")

    def test_about_page_links_scientific_calculator(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("calculator"))
        self.assertContains(response, "Wissenschaftlicher Rechner")
        self.assertContains(response, "Wurzeln, Potenzen, Logarithmen, Trigonometrie")

    def test_about_page_links_budget_tracker(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("budget_tracker"))
        self.assertContains(response, "Budget-Tracker")
        self.assertContains(response, "Monatsbudget, Einnahmen, Ausgaben, Fixkosten")

    def test_about_page_mentions_stream_deck_voicemod(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("stream-deck"))
        self.assertContains(response, "Stream Deck")
        self.assertContains(response, "Voicemod")

    def test_changelog_mentions_stream_deck_voicemod_update(self):
        response = self.client.get(reverse("changelog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stream Deck mit Voicemod-Steuerung")
        self.assertContains(response, "Voices lassen sich aus Voicemod laden")

    def test_changelog_mentions_file_converter_and_tool_design_update(self):
        response = self.client.get(reverse("changelog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Datei-Konverter und einheitliches Tool-Design")
        self.assertContains(response, "Toolbox-Seiten übernehmen jetzt gemeinsame Theme-Farben")
        self.assertContains(response, "Quality-Workflow startet nicht mehr automatisch")

    def test_about_page_mentions_file_converter_and_image_tools(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("file_converter"))
        self.assertContains(response, reverse("image_tools"))
        self.assertContains(response, "Datei-Konverter")
        self.assertContains(response, "Bild Tools")
        self.assertContains(response, "Kontrastmodus")

    def test_readme_mentions_stream_deck_voicemod(self):
        readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")

        self.assertIn("Spotify, Voicemod und eigene Aktionen", readme)
        self.assertIn("Voicemod-Steuerung mit lokal gespeichertem API-Key", readme)
        self.assertIn("Voice-Auswahl aus der geladenen Voicemod-Liste", readme)

    def test_readme_mentions_file_converter_tool_design_and_manual_quality_checks(self):
        readme = (Path(settings.BASE_DIR) / "README.md").read_text(encoding="utf-8")

        self.assertIn("Datei-Konverter", readme)
        self.assertIn("serverseitig über LibreOffice", readme)
        self.assertIn("Einheitliches Tool-Design", readme)
        self.assertIn("GitHub-Actions-Workflow läuft nur manuell", readme)

    def test_simple_tool_pages_load(self):
        pages = [
            ("obs-dashboard", "app/obs-dashboard.html"),
            ("spritkostenrechner", "app/spritkostenrechner.html"),
            ("budget_tracker", "app/budget_tracker.html"),
            ("calculator", "app/calculator.html"),
            ("human-benchmark", "app/human_benchmark.html"),
            ("genius-search", "app/genius_search.html"),
            ("avatar-wiki", "app/avatar_wiki.html"),
            ("unit_converter", "app/unit_converter.html"),
            ("file_converter", "app/file_converter.html"),
            ("drift-circuit", "app/drift_circuit.html"),
            ("snake-powerups", "app/snake_powerups.html"),
            ("cookie-clicker", "app/cookie_clicker.html"),
            ("cookie-cosmos-v2", "app/cookie_cosmos_v2.html"),
            ("nebula-forge-tycoon", "app/nebula_forge_tycoon.html"),
            ("stream-deck", "app/stream_deck.html"),
        ]

        for url_name, template in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_calculator_page_contains_scientific_controls(self):
        response = self.client.get(reverse("calculator"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="calculator-expression"')
        self.assertContains(response, 'data-insert="sqrt("')
        self.assertContains(response, 'data-insert="cbrt("')
        self.assertContains(response, 'data-insert="root("')
        self.assertContains(response, 'data-insert="^"')
        self.assertContains(response, 'data-action="memory-add"')
        self.assertContains(response, 'data-action="memory-recall"')
        self.assertContains(response, 'data-angle-mode="deg"')
        self.assertContains(response, 'data-angle-mode="rad"')
        self.assertContains(response, 'id="calculator-history"')
        self.assertContains(response, 'calculator-help-list')
        self.assertContains(response, 'window.MyToolsCalculatorI18n')
        self.assertContains(response, 'app/js/calculator.js')


    @override_settings(FONTAWESOME_KIT_KEY="test-kit", USE_FONTAWESOME_KIT=False)
    def test_base_template_uses_core_css_and_optimized_fontawesome_loader(self):
        response = self.client.get(reverse("profile_card_designer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "app/css/core.css")
        self.assertNotContains(response, "app/css/profile_menu.css")
        self.assertNotContains(response, "app/css/contrast.css")
        self.assertContains(response, "cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css")
        self.assertNotContains(response, "kit.fontawesome.com")

    def test_google_analytics_is_disabled_in_tests_by_default(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="mytools-ga-script"')
        self.assertNotContains(response, "app/js/google_analytics.js")

    @override_settings(GOOGLE_ANALYTICS_ENABLED=True, GOOGLE_ANALYTICS_ID="G-TEST123456")
    def test_google_analytics_loader_renders_when_enabled(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="mytools-ga-script"')
        self.assertContains(response, "app/css/google_analytics.css")
        self.assertContains(response, "app/js/google_analytics.js")
        self.assertContains(response, 'data-measurement-id="G-TEST123456"')
        self.assertContains(response, "Analyse-Cookies erlauben?")

    @override_settings(GOOGLE_ANALYTICS_ENABLED=True, GOOGLE_ANALYTICS_ID="G-TEST123456")
    def test_google_analytics_loader_renders_on_login_page_when_enabled(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="mytools-ga-script"')
        self.assertContains(response, "app/js/google_analytics.js")
        self.assertContains(response, 'data-measurement-id="G-TEST123456"')

    def test_google_analytics_js_uses_consent_mode_before_loading_tag(self):
        js = Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "google_analytics.js"
        js_content = js.read_text(encoding="utf-8")

        self.assertIn("window.gtag('consent', 'default'", js_content)
        self.assertIn("analytics_storage: 'denied'", js_content)
        self.assertIn("ad_storage: 'denied'", js_content)
        self.assertIn("mytools_google_analytics_consent_v1", js_content)
        self.assertIn("https://www.googletagmanager.com/gtag/js?id=", js_content)
        self.assertIn("window.gtag('consent', 'update'", js_content)

    def test_core_css_uses_correct_relative_icon_paths(self):
        css = Path(settings.BASE_DIR) / "app" / "static" / "app" / "css" / "core.css"
        css_content = css.read_text(encoding="utf-8")

        self.assertIn('../icons/icons8-gemini-ai.svg', css_content)
        self.assertNotIn('../../icons/icons8-gemini-ai.svg', css_content)

    def test_profile_menu_defers_large_avatar_and_obfuscates_email(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("menu-avatar.png", self.get_test_image("menu-avatar.png"), save=True)
        self.user.email = "menu@example.com"
        self.user.save(update_fields=["email"])

        response = self.client.get(reverse("profile_card_designer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js-deferred-image")
        self.assertContains(response, "data-src=", html=False)
        self.assertContains(response, 'data-email-local="menu"')
        self.assertContains(response, 'data-email-domain="example.com"')
        self.assertNotContains(response, "menu@example.com")

    def test_base_js_contains_live_status_singleton_and_deferred_image_hydration(self):
        js = Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "base.js"
        js_content = js.read_text(encoding="utf-8")

        self.assertIn("__myToolsBaseInitialized", js_content)
        self.assertIn("__myToolsLiveStatusState", js_content)
        self.assertIn("hydrateDeferredImages", js_content)
        self.assertIn("js-obfuscated-email", js_content)
        self.assertIn("liveStatusUrl ? 15000 : 7000", js_content)

    def test_calculator_static_assets_cover_core_features(self):
        js = Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "calculator.js"
        css = Path(settings.BASE_DIR) / "app" / "static" / "app" / "css" / "calculator.css"

        js_content = js.read_text(encoding="utf-8")
        css_content = css.read_text(encoding="utf-8")

        self.assertIn("class Parser", js_content)
        self.assertIn('case "sqrt"', js_content)
        self.assertIn('case "cbrt"', js_content)
        self.assertIn('case "root"', js_content)
        self.assertIn('case "sin"', js_content)
        self.assertIn('case "log"', js_content)
        self.assertIn('function factorial', js_content)
        self.assertIn('memory-add', js_content)
        self.assertIn('MyToolsCalculatorI18n', js_content)
        self.assertIn('window.MyToolsCalculator', js_content)
        self.assertIn('.calculator-help-list', css_content)
        self.assertIn('text-align: left;', css_content)


    def test_stream_deck_contains_obs_audio_controls(self):
        response = self.client.get(reverse("stream-deck"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="obs-audio"')
        self.assertContains(response, 'id="obs-audio-fields"')
        self.assertContains(response, 'id="edit-audio-input"')
        self.assertContains(response, 'value="toggle-mute"')
        self.assertContains(response, 'value="volume-up"')
        self.assertContains(response, 'value="volume-down"')

    def test_stream_deck_contains_fullscreen_controls(self):
        response = self.client.get(reverse("stream-deck"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="deck-fullscreen-btn"')
        self.assertContains(response, 'id="exit-deck-fullscreen-btn"')

    def test_stream_deck_lazy_loads_obs_websocket_module(self):
        js = Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "stream_deck.js"
        js_content = js.read_text(encoding="utf-8")

        self.assertIn('OBS_WEBSOCKET_MODULE_URL = "https://cdn.jsdelivr.net/npm/obs-websocket-js@5.0.6/+esm"', js_content)
        self.assertIn("function loadObsWebSocketClass()", js_content)
        self.assertIn("import(OBS_WEBSOCKET_MODULE_URL)", js_content)
        self.assertIn("warmObsWebSocketModule", js_content)
        self.assertIn('elements.connectBtn.addEventListener("pointerenter", warmObsWebSocketModule', js_content)
        self.assertNotIn('import OBSWebSocket from "https://cdn.jsdelivr.net/npm/obs-websocket-js@5.0.6/+esm"', js_content)

    def test_stream_deck_contains_voicemod_controls(self):
        response = self.client.get(reverse("stream-deck"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("stream-deck-voicemod-action"))
        self.assertContains(response, 'id="voicemod-status-dot"')
        self.assertContains(response, 'id="voicemod-voices-select"')
        self.assertContains(response, 'data-voicemod-quick="toggleVoiceChanger"')
        self.assertContains(response, 'value="voicemod"')
        self.assertContains(response, 'id="voicemod-fields"')
        self.assertContains(response, 'id="edit-voicemod-action"')
        self.assertContains(response, 'id="edit-voicemod-voice-id"')
        self.assertContains(response, 'id="load-editor-voicemod-voices-btn"')
        self.assertContains(response, 'id="voicemod-api-key-input"')
        self.assertContains(response, 'id="save-voicemod-api-key-btn"')
        self.assertContains(response, 'id="clear-voicemod-api-key-btn"')

    def test_stream_deck_populates_voicemod_editor_voice_dropdown(self):
        js = Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "stream_deck.js"
        js_content = js.read_text(encoding="utf-8")

        self.assertIn("let voicemodVoices = []", js_content)
        self.assertIn("renderVoicemodVoiceSelect(elements.editVoicemodVoiceId", js_content)
        self.assertIn("ensureVoicemodVoiceOption(button.voicemodVoiceId)", js_content)
        self.assertIn('elements.loadEditorVoicemodVoicesBtn.addEventListener("click", loadVoicemodVoices)', js_content)
        self.assertIn("voicemodApiKey", js_content)
        self.assertIn("function saveVoicemodApiKey()", js_content)
        self.assertIn('throw new Error("Kein Voicemod API-Key verbunden.")', js_content)

    @patch("app.views.get_env_value")
    @patch("app.views.send_voicemod_action")
    def test_stream_deck_voicemod_action_uses_posted_key(self, mock_send_voicemod_action, mock_get_env_value):
        mock_get_env_value.side_effect = lambda name: {
            "VOICEMOD_HOST": "",
            "VOICEMOD_PORTS": "59129",
        }.get(name, "")
        mock_send_voicemod_action.return_value = {"port": 59129, "messages": []}

        response = self.client.post(
            reverse("stream-deck-voicemod-action"),
            data=json.dumps({"action": "loadVoice", "payload": {"voiceID": "robot"}, "apiKey": "posted-voicemod-key"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        mock_send_voicemod_action.assert_called_once_with(
            "posted-voicemod-key",
            "loadVoice",
            {"voiceID": "robot"},
            host="127.0.0.1",
            ports=[59129],
        )

    @patch("app.views.get_env_value")
    @patch("app.views.send_voicemod_action")
    def test_stream_deck_voicemod_action_prefers_posted_key(self, mock_send_voicemod_action, mock_get_env_value):
        mock_get_env_value.side_effect = lambda name: {
            "VOICEMOD_HOST": "",
            "VOICEMOD_PORTS": "59129",
        }.get(name, "")
        mock_send_voicemod_action.return_value = {"port": 59129, "messages": []}

        response = self.client.post(
            reverse("stream-deck-voicemod-action"),
            data=json.dumps({"action": "toggleMuteMic", "apiKey": "posted-voicemod-key"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_send_voicemod_action.assert_called_once_with(
            "posted-voicemod-key",
            "toggleMuteMic",
            {},
            host="127.0.0.1",
            ports=[59129],
        )

    @patch("app.views.send_voicemod_action")
    def test_stream_deck_voicemod_action_without_key_returns_error(self, mock_send_voicemod_action):
        response = self.client.post(
            reverse("stream-deck-voicemod-action"),
            data=json.dumps({"action": "toggleMuteMic"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Kein Voicemod API-Key verbunden.")
        mock_send_voicemod_action.assert_not_called()

    @patch("app.views.send_voicemod_action")
    def test_stream_deck_voicemod_action_rejects_unknown_action(self, mock_send_voicemod_action):
        response = self.client.post(
            reverse("stream-deck-voicemod-action"),
            data=json.dumps({"action": "deleteEverything"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        mock_send_voicemod_action.assert_not_called()


class SecurityDashboardAndQrToolTests(BaseTestCase):
    def test_security_dashboard_loads_and_shows_account_status(self):
        response = self.client.get(reverse("security_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/security_dashboard.html")
        self.assertContains(response, "Sicherheits-Dashboard")
        self.assertContains(response, "Aktive Sitzungen")
        self.assertContains(response, reverse("two_factor_settings"))

    def test_security_dashboard_does_not_show_profile_messages(self):
        session = self.client.session
        session["_messages"] = MessageEncoder().encode([
            Message(message_constants.SUCCESS, "Dein Profil wurde gespeichert."),
        ])
        session.save()

        response = self.client.get(reverse("security_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Dein Profil wurde gespeichert.")

    def test_security_dashboard_still_shows_security_messages(self):
        response = self.client.post(
            reverse("security_dashboard"),
            {"action": "revoke_session"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Es wurde keine Sitzung")

    def test_security_event_is_created_for_two_factor_enable(self):
        response = self.client.post(reverse("two_factor_settings"), {"action": "start_setup"})
        self.assertRedirects(response, reverse("two_factor_settings"))

        settings_obj = UserTwoFactorSettings.objects.get(user=self.user)
        token = current_totp(settings_obj.secret_key)
        response = self.client.post(reverse("two_factor_settings"), {
            "action": "confirm_setup",
            "token": token,
        })

        self.assertRedirects(response, reverse("two_factor_settings"))
        self.assertTrue(SecurityEvent.objects.filter(
            user=self.user,
            event_type=SecurityEvent.EVENT_TWO_FACTOR_ENABLED,
        ).exists())

    def test_security_dashboard_can_revoke_other_session(self):
        other_client = self.client_class()
        other_client.force_login(self.user)
        other_session_key = other_client.session.session_key

        response = self.client.post(reverse("security_dashboard"), {
            "action": "revoke_session",
            "session_key": other_session_key,
        })

        self.assertRedirects(response, reverse("security_dashboard"))
        from django.contrib.sessions.models import Session
        self.assertFalse(Session.objects.filter(session_key=other_session_key).exists())
        self.assertTrue(SecurityEvent.objects.filter(
            user=self.user,
            event_type=SecurityEvent.EVENT_SESSION_REVOKED,
        ).exists())

    def test_qr_code_tool_loads(self):
        response = self.client.get(reverse("qr_code_tool"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/qr_code_tool.html")
        self.assertContains(response, "QR-Code Tool")
        self.assertContains(response, "app/js/qr_code_tool.js")

    def test_qr_code_tool_generates_text_qr_code(self):
        response = self.client.post(reverse("qr_code_tool"), {
            "qr_type": "text",
            "text": "Mein Test QR",
            "foreground": "#111827",
            "background": "#ffffff",
            "error_level": "M",
            "box_size": "8",
            "border": "4",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, "Mein Test QR")
        self.assertContains(response, "PNG herunterladen")

    def test_base_template_links_security_dashboard_and_qr_tool(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("security_dashboard"))
        self.assertContains(response, reverse("qr_code_tool"))

    def test_file_converter_page_loads_and_is_linked(self):
        response = self.client.get(reverse("file_converter"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/file_converter.html")
        self.assertContains(response, "Datei-Konverter")
        self.assertContains(response, "DOCX")
        self.assertContains(response, "app/js/file_converter.js")
        self.assertContains(response, "app/css/file_converter.css")

        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, reverse("file_converter"))


class FileConverterTests(BaseTestCase):
    def test_image_file_can_be_converted_to_jpg(self):
        response = self.client.post(reverse("file_converter"), {
            "target": "jpg",
            "file": self.get_test_image("avatar.png"),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn('filename="avatar-konvertiert.jpg"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xff\xd8"))

    @patch("app.file_converter_views._office_converter_binary", return_value=None)
    def test_docx_to_pdf_shows_message_when_libreoffice_is_missing(self, _binary_mock):
        response = self.client.post(reverse("file_converter"), {
            "target": "pdf",
            "file": SimpleUploadedFile(
                "bericht.docx",
                b"not-a-real-docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/file_converter.html")
        self.assertContains(response, "LibreOffice ist auf dem Server nicht installiert")

    @patch("app.file_converter_views._office_converter_binary", return_value="/usr/bin/libreoffice")
    @patch("app.file_converter_views.subprocess.run")
    def test_docx_to_pdf_downloads_generated_pdf(self, run_mock, _binary_mock):
        def fake_run(command, **kwargs):
            output_dir = Path(command[command.index("--outdir") + 1])
            source_path = Path(command[-1])
            (output_dir / f"{source_path.stem}.pdf").write_bytes(b"%PDF-1.4 fake pdf")
            return Mock(stdout=b"", stderr=b"", returncode=0)

        run_mock.side_effect = fake_run

        response = self.client.post(reverse("file_converter"), {
            "target": "pdf",
            "file": SimpleUploadedFile(
                "bericht.docx",
                b"fake-docx-content",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.content, b"%PDF-1.4 fake pdf")
        self.assertIn('filename="bericht-konvertiert.pdf"', response["Content-Disposition"])
        run_mock.assert_called_once()

    def test_non_image_cannot_be_converted_to_jpg(self):
        response = self.client.post(reverse("file_converter"), {
            "target": "jpg",
            "file": SimpleUploadedFile("text.txt", b"Hallo", content_type="text/plain"),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dieses Zielformat ist aktuell nur für Bilder verfügbar")


class ChatEnhancementTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.other_user = get_user_model().objects.create_user(username="chatfriend", password="testpass-123")
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.ROOM_DIRECT,
            direct_key=ChatRoom.direct_key_for_users(self.user, self.other_user),
            created_by=self.user,
        )
        ChatRoomMember.objects.create(room=self.room, user=self.user, is_admin=True)
        ChatRoomMember.objects.create(room=self.room, user=self.other_user)
        self.message = ChatMessage.objects.create(room=self.room, sender=self.other_user, text="Merken")

    def test_set_chat_theme_updates_room(self):
        response = self.client.post(reverse("chat_theme", args=[self.room.id]), {"theme": ChatRoom.THEME_FOREST})

        self.assertRedirects(response, reverse("chat_room", args=[self.room.id]))
        self.room.refresh_from_db()
        self.assertEqual(self.room.theme, ChatRoom.THEME_FOREST)

    def test_pin_chat_message_toggles_pinned_message(self):
        response = self.client.post(
            reverse("chat_message_pin", args=[self.room.id, self.message.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.pinned_message, self.message)
        self.assertEqual(response.json()["pinned_message"]["id"], self.message.id)

        response = self.client.post(
            reverse("chat_message_pin", args=[self.room.id, self.message.id]),
            {"action": "unpin"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertIsNone(self.room.pinned_message)
        self.assertIsNone(response.json()["pinned_message"])

    def test_chat_page_renders_theme_menu_and_pinned_message(self):
        self.room.theme = ChatRoom.THEME_GRAPE
        self.room.pinned_message = self.message
        self.room.save(update_fields=["theme", "pinned_message"])

        response = self.client.get(reverse("chat_room", args=[self.room.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chat-theme-grape")
        self.assertContains(response, "chat-pinned-message")
        self.assertContains(response, "Merken")

    def test_chat_page_renders_day_separators_and_profile_card(self):
        old_message = ChatMessage.objects.create(room=self.room, sender=self.user, text="Gestern")
        ChatMessage.objects.filter(id=old_message.id).update(
            created_at=timezone.now() - timezone.timedelta(days=1)
        )

        response = self.client.get(reverse("chat_room", args=[self.room.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chat-date-separator")
        self.assertContains(response, "Heute")
        self.assertContains(response, "Gestern")
        self.assertContains(response, "chat-profile-card")
        self.assertContains(response, reverse("public_profile", args=[self.other_user.id]))

    def test_messages_api_includes_day_and_sender_profile_payload(self):
        response = self.client.get(reverse("chat_messages_api", args=[self.room.id]))

        self.assertEqual(response.status_code, 200)
        message = response.json()["messages"][0]
        self.assertIn("day_key", message)
        self.assertIn("day_label", message)
        self.assertEqual(message["sender"]["profile_url"], reverse("public_profile", args=[self.other_user.id]))

    def test_user_can_edit_own_message(self):
        own_message = ChatMessage.objects.create(room=self.room, sender=self.user, text="Alt")

        response = self.client.post(
            reverse("chat_message_edit", args=[self.room.id, own_message.id]),
            {"text": "Neu @chatfriend"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        own_message.refresh_from_db()
        self.assertEqual(own_message.text, "Neu @chatfriend")
        self.assertIsNotNone(own_message.edited_at)
        self.assertTrue(InboxItem.objects.filter(user=self.other_user, title__icontains="erwaehnt").exists())

    def test_typing_api_marks_user_as_typing_and_messages_api_returns_it(self):
        response = self.client.post(
            reverse("chat_typing_api", args=[self.room.id]),
            {"is_typing": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ChatTypingStatus.objects.filter(room=self.room, user=self.user, is_typing=True).exists())

        self.client.force_login(self.other_user)
        response = self.client.get(reverse("chat_messages_api", args=[self.room.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["typing_users"][0]["username"], self.user.username)


    @patch("app.chat_views.broadcast_chat_event")
    def test_chat_write_actions_broadcast_realtime_events(self, mock_broadcast):
        send_response = self.client.post(
            reverse("chat_send", args=[self.room.id]),
            {"text": "Hallo live"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(send_response.status_code, 200)
        own_message_id = send_response.json()["message"]["id"]
        mock_broadcast.assert_any_call(self.room.id, "message_created", message_id=own_message_id)

        edit_response = self.client.post(
            reverse("chat_message_edit", args=[self.room.id, own_message_id]),
            {"text": "Hallo live bearbeitet"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(edit_response.status_code, 200)
        mock_broadcast.assert_any_call(self.room.id, "message_updated", message_id=own_message_id)

        reaction_response = self.client.post(
            reverse("chat_message_react", args=[self.room.id, self.message.id]),
            {"emoji": "👍"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(reaction_response.status_code, 200)
        mock_broadcast.assert_any_call(self.room.id, "reaction_updated", message_id=self.message.id)

        pin_response = self.client.post(
            reverse("chat_message_pin", args=[self.room.id, self.message.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(pin_response.status_code, 200)
        mock_broadcast.assert_any_call(self.room.id, "pinned_updated")

        typing_response = self.client.post(
            reverse("chat_typing_api", args=[self.room.id]),
            {"is_typing": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(typing_response.status_code, 200)
        mock_broadcast.assert_any_call(self.room.id, "typing")

        delete_response = self.client.post(
            reverse("chat_message_delete", args=[self.room.id, own_message_id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(delete_response.status_code, 200)
        mock_broadcast.assert_any_call(self.room.id, "message_deleted", message_id=own_message_id)


class ModerationDashboardTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.target = get_user_model().objects.create_user(username="moderated", password="testpass-123")

    def test_staff_can_suspend_and_unsuspend_user_with_audit_log(self):
        response = self.client.post(reverse("moderation_user_status", args=[self.target.id]), {
            "action": "suspend",
            "duration_hours": "24",
            "reason": "Test",
        })

        self.assertRedirects(response, reverse("moderation"))
        suspension = UserSuspension.objects.get(user=self.target)
        self.assertTrue(suspension.is_current)
        self.assertEqual(suspension.reason, "Test")
        self.assertTrue(ModerationAuditLog.objects.filter(action=ModerationAuditLog.ACTION_USER_SUSPENDED, target_user=self.target).exists())

        response = self.client.post(reverse("moderation_user_status", args=[self.target.id]), {
            "action": "unsuspend",
        })

        self.assertRedirects(response, reverse("moderation"))
        suspension.refresh_from_db()
        self.assertFalse(suspension.is_active)
        self.assertTrue(ModerationAuditLog.objects.filter(action=ModerationAuditLog.ACTION_USER_UNSUSPENDED, target_user=self.target).exists())


class WeatherViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def mocked_current_weather_response(self, status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {
            "name": "Berlin",
            "timezone": 3600,
            "sys": {
                "country": "DE",
                "sunrise": 1715148000,
                "sunset": 1715202000,
            },
            "main": {
                "temp": 18.4,
                "humidity": 61,
                "pressure": 1014,
            },
            "weather": [
                {
                    "description": "klarer Himmel",
                    "icon": "01d",
                }
            ],
            "wind": {
                "speed": 3.2,
            },
        }
        return response

    def mocked_forecast_response(self, status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {
            "list": [
                {
                    "dt": 1715155200,
                    "dt_txt": "2024-05-08 12:00:00",
                    "main": {"temp": 19.1},
                    "weather": [{"description": "leicht bewölkt", "icon": "02d"}],
                    "pop": 0.2,
                },
                {
                    "dt": 1715166000,
                    "dt_txt": "2024-05-08 15:00:00",
                    "main": {"temp": 20.2},
                    "weather": [{"description": "leicht bewölkt", "icon": "02d"}],
                    "pop": 0.1,
                },
                {
                    "dt": 1715241600,
                    "dt_txt": "2024-05-09 12:00:00",
                    "main": {"temp": 21.5},
                    "weather": [{"description": "sonnig", "icon": "01d"}],
                    "pop": 0,
                },
                {
                    "dt": 1715328000,
                    "dt_txt": "2024-05-10 12:00:00",
                    "main": {"temp": 17.8},
                    "weather": [{"description": "Regen", "icon": "10d"}],
                    "pop": 0.8,
                },
                {
                    "dt": 1715414400,
                    "dt_txt": "2024-05-11 12:00:00",
                    "main": {"temp": 16.6},
                    "weather": [{"description": "bewölkt", "icon": "03d"}],
                    "pop": 0.4,
                },
                {
                    "dt": 1715500800,
                    "dt_txt": "2024-05-12 12:00:00",
                    "main": {"temp": 22.0},
                    "weather": [{"description": "sonnig", "icon": "01d"}],
                    "pop": 0,
                },
            ]
        }
        return response

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_loads_with_api_data(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        response = self.client.get(reverse("weather"), {
            "city": "Berlin",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/weather.html")

        self.assertEqual(response.context["city"], "Berlin")
        self.assertEqual(response.context["country"], "DE")
        self.assertEqual(response.context["temperature"], 18.4)
        self.assertEqual(response.context["description"], "klarer Himmel")
        self.assertEqual(response.context["icon"], "01d")
        self.assertEqual(response.context["wind_speed"], 3.2)
        self.assertEqual(response.context["humidity"], 61)
        self.assertEqual(response.context["pressure"], 1014)
        self.assertEqual(response.context["sunrise"], "07:00")
        self.assertEqual(response.context["sunset"], "22:00")
        self.assertEqual(len(response.context["forecast"]), 5)
        self.assertEqual(len(response.context["hourly_forecast"]), 6)
        self.assertContains(response, reverse("weather_icon", args=["01d", "4x"]))
        self.assertContains(response, reverse("weather_icon", args=["02d", "2x"]))
        self.assertNotContains(response, "openweathermap.org/img/wn")

    @patch("app.views.requests.get")
    def test_weather_icon_view_converts_and_caches_openweather_icon_as_webp(self, mock_get):
        icon_file = self.get_test_image("icon.png")
        upstream_response = Mock(status_code=200, content=icon_file.read())
        upstream_response.raise_for_status = Mock()
        mock_get.return_value = upstream_response

        response = self.client.get(reverse("weather_icon", args=["03d", "2x"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("immutable", response["Cache-Control"])
        self.assertGreater(len(response.content), 0)

        cached_response = self.client.get(reverse("weather_icon", args=["03d", "2x"]))

        self.assertEqual(cached_response.status_code, 200)
        self.assertEqual(mock_get.call_count, 1)

    @patch("app.views.requests.get")
    def test_weather_icon_view_rejects_invalid_icon_codes(self, mock_get):
        response = self.client.get(reverse("weather_icon", args=["abc", "2x"]))

        self.assertEqual(response.status_code, 404)
        mock_get.assert_not_called()

    @patch("app.views.get_env_value", return_value="")
    @patch("app.views.requests.get")
    def test_weather_page_handles_missing_api_key(self, mock_get, mock_get_env_value):
        response = self.client.get(reverse("weather"), {
            "city": "Berlin",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], "OPENWEATHER_API_KEY fehlt in der .env.")
        mock_get.assert_not_called()

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_falls_back_to_berlin_without_saved_location(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        response = self.client.get(reverse("weather"))

        self.assertEqual(response.status_code, 200)

        first_call_params = mock_get.call_args_list[0].kwargs["params"]

        self.assertEqual(first_call_params["q"], "Berlin")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_uses_saved_default_city(self, mock_get, mock_get_env_value):
        WeatherLocation.objects.create(name="Berlin", order=1)
        WeatherLocation.objects.create(name="Hamburg", is_default=True, order=2)
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        response = self.client.get(reverse("weather"))

        self.assertEqual(response.status_code, 200)

        first_call_params = mock_get.call_args_list[0].kwargs["params"]

        self.assertEqual(first_call_params["q"], "Hamburg")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_can_use_lat_lon(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        response = self.client.get(reverse("weather"), {
            "lat": "52.52",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 200)

        first_call_params = mock_get.call_args_list[0].kwargs["params"]

        self.assertEqual(first_call_params["lat"], "52.52")
        self.assertEqual(first_call_params["lon"], "13.405")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_handles_city_not_found(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_current_weather_response(
            status_code=404,
            json_data={
                "message": "city not found",
            },
        )

        response = self.client.get(reverse("weather"), {
            "city": "UnbekannteStadt",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], "Standort nicht gefunden.")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_handles_invalid_current_weather_response(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_current_weather_response(json_data=[])

        response = self.client.get(reverse("weather"), {
            "city": "Berlin",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], "Ungültige Antwort der OpenWeather API.")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_handles_forecast_error(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(
                status_code=500,
                json_data={
                    "message": "error",
                },
            ),
        ]

        response = self.client.get(reverse("weather"), {
            "city": "Berlin",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], "Wettervorhersage konnte nicht geladen werden.")

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_handles_connection_error(self, mock_get, mock_get_env_value):
        mock_get.side_effect = Exception("API nicht erreichbar")

        response = self.client.get(reverse("weather"), {
            "city": "Berlin",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("Verbindungsfehler", response.context["error"])
        self.assertIn("API nicht erreichbar", response.context["error"])

    def test_add_weather_location(self):
        response = self.client.post(reverse("weather"), {
            "action": "add_weather_location",
            "location_name": "Osnabrück",
        })

        self.assertRedirects(
            response,
            f"{reverse('weather')}?city=Osnabrück",
            fetch_redirect_response=False,
        )
        location = WeatherLocation.objects.get(name="Osnabrück")
        self.assertTrue(location.is_default)

    def test_add_empty_weather_location_redirects_without_creating(self):
        response = self.client.post(reverse("weather"), {
            "action": "add_weather_location",
            "location_name": "",
        })

        self.assertRedirects(
            response,
            reverse("weather"),
            fetch_redirect_response=False,
        )
        self.assertEqual(WeatherLocation.objects.count(), 0)

    def test_delete_weather_location(self):
        location = WeatherLocation.objects.create(name="Berlin")

        response = self.client.post(reverse("weather"), {
            "action": "delete_weather_location",
            "location_id": location.id,
            "current_city": "Berlin",
        })

        self.assertRedirects(
            response,
            f"{reverse('weather')}?city=Berlin",
            fetch_redirect_response=False,
        )
        self.assertFalse(WeatherLocation.objects.filter(id=location.id).exists())

    def test_set_default_weather_location(self):
        old_location = WeatherLocation.objects.create(name="Berlin", is_default=True, order=1)
        new_location = WeatherLocation.objects.create(name="Hamburg", order=2)

        response = self.client.post(reverse("weather"), {
            "action": "set_default_weather_location",
            "location_id": new_location.id,
            "current_city": "Berlin",
        })

        self.assertRedirects(
            response,
            f"{reverse('weather')}?city=Hamburg",
            fetch_redirect_response=False,
        )

        old_location.refresh_from_db()
        new_location.refresh_from_db()
        self.assertFalse(old_location.is_default)
        self.assertTrue(new_location.is_default)

    def test_delete_default_weather_location_promotes_next_location(self):
        default_location = WeatherLocation.objects.create(name="Berlin", is_default=True, order=1)
        next_location = WeatherLocation.objects.create(name="Hamburg", order=2)

        response = self.client.post(reverse("weather"), {
            "action": "delete_weather_location",
            "location_id": default_location.id,
            "current_city": "Berlin",
        })

        self.assertRedirects(
            response,
            f"{reverse('weather')}?city=Hamburg",
            fetch_redirect_response=False,
        )

        next_location.refresh_from_db()
        self.assertFalse(WeatherLocation.objects.filter(id=default_location.id).exists())
        self.assertTrue(next_location.is_default)


    @patch("app.views.requests.get")
    def test_cached_openweather_json_reuses_successful_response_without_api_key_in_cache_key(self, mock_get):
        from app.views import cached_openweather_json

        mock_get.return_value = self.mocked_current_weather_response()
        first_status, first_data = cached_openweather_json(
            "weather",
            {"appid": "first-key", "q": "Berlin", "units": "metric", "lang": "de"},
        )
        second_status, second_data = cached_openweather_json(
            "weather",
            {"appid": "second-key", "q": "Berlin", "units": "metric", "lang": "de"},
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_data["name"], "Berlin")
        self.assertEqual(second_data["name"], "Berlin")
        self.assertEqual(mock_get.call_count, 1)

    @patch("app.views.requests.get")
    def test_cached_openweather_json_does_not_cache_failed_responses(self, mock_get):
        from app.views import cached_openweather_json

        mock_get.return_value = self.mocked_current_weather_response(
            status_code=500,
            json_data={"message": "temporär nicht erreichbar"},
        )

        cached_openweather_json("weather", {"appid": "key", "q": "Berlin"})
        cached_openweather_json("weather", {"appid": "key", "q": "Berlin"})

        self.assertEqual(mock_get.call_count, 2)

    @patch("app.views.get_env_value", return_value="test-weather-key")
    @patch("app.views.requests.get")
    def test_weather_page_reuses_cached_current_and_forecast_data(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        first_response = self.client.get(reverse("weather"), {"city": "Berlin"})
        second_response = self.client.get(reverse("weather"), {"city": "Berlin"})

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)


class NoteFormTests(BaseTestCase):
    def test_note_form_removes_dangerous_html_but_keeps_allowed_formatting(self):
        form = NoteForm(data={
            "title": "Test",
            "content": '<p style="text-align:center">Hallo</p><script>alert(1)</script><strong>Wichtig</strong>',
            "tags": "schule, test",
            "color": "blue",
            "is_pinned": "on",
        })

        self.assertTrue(form.is_valid())

        cleaned_content = form.cleaned_data["content"]

        self.assertIn("<p style=", cleaned_content)
        self.assertIn("<strong>Wichtig</strong>", cleaned_content)
        self.assertNotIn("<script>", cleaned_content)

    def test_note_form_keeps_checklist_markup(self):
        form = NoteForm(data={
            "title": "Aufgaben",
            "content": '<ul class="note-checklist"><li data-checked="false">Backup</li></ul>',
            "tags": "todo",
            "color": "blue",
        })

        self.assertTrue(form.is_valid())
        self.assertIn('class="note-checklist"', form.cleaned_data["content"])
        self.assertIn('data-checked="false"', form.cleaned_data["content"])


class NotesViewTests(BaseTestCase):
    def test_notes_page_loads_and_splits_pinned_and_normal_notes(self):
        pinned = Note.objects.create(title="Angepinnt", is_pinned=True)
        normal = Note.objects.create(title="Normal", is_pinned=False)
        Note.objects.create(title="Archiv", is_archived=True)

        response = self.client.get(reverse("notes"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/notes.html")
        self.assertIn(pinned, response.context["pinned_notes"])
        self.assertIn(normal, response.context["normal_notes"])
        self.assertEqual(response.context["note_count"], 2)

    def test_notes_search_filters_title_content_and_tags(self):
        matching_title = Note.objects.create(title="Docker")
        matching_content = Note.objects.create(title="Notiz", content="Postgres Backup")
        matching_tag = Note.objects.create(title="Tag", tags="server")
        Note.objects.create(title="Andere Notiz", content="Nichts")

        response = self.client.get(reverse("notes"), {
            "q": "server",
        })

        all_results = list(response.context["pinned_notes"]) + list(response.context["normal_notes"])

        self.assertIn(matching_tag, all_results)
        self.assertNotIn(matching_title, all_results)
        self.assertNotIn(matching_content, all_results)

        response = self.client.get(reverse("notes"), {
            "q": "Docker",
        })

        all_results = list(response.context["pinned_notes"]) + list(response.context["normal_notes"])

        self.assertIn(matching_title, all_results)

        response = self.client.get(reverse("notes"), {
            "q": "Postgres",
        })

        all_results = list(response.context["pinned_notes"]) + list(response.context["normal_notes"])

        self.assertIn(matching_content, all_results)

    def test_archived_notes_are_shown_when_archived_parameter_is_set(self):
        archived = Note.objects.create(title="Archiv", is_archived=True)
        Note.objects.create(title="Aktiv", is_archived=False)

        response = self.client.get(reverse("notes"), {
            "archived": "1",
        })

        self.assertEqual(response.context["note_count"], 1)
        self.assertIn(archived, list(response.context["normal_notes"]))
        self.assertTrue(response.context["show_archived"])

    def test_notes_scope_can_show_shared_notes(self):
        other_user = get_user_model().objects.create_user(
            username="notizfreund",
            password="testpass-123",
        )
        own_note = Note.objects.create(title="Eigene Notiz")
        shared_note = Note.objects.create(user=other_user, title="Geteilte Notiz")
        shared_note.shared_with.add(self.user)

        response = self.client.get(reverse("notes"), {"scope": "shared"})

        all_results = list(response.context["pinned_notes"]) + list(response.context["normal_notes"])
        self.assertIn(shared_note, all_results)
        self.assertNotIn(own_note, all_results)
        self.assertEqual(response.context["shared_note_count"], 1)

    def test_notes_scope_can_show_reminders_and_due_count(self):
        due_note = Note.objects.create(
            title="Faellige Erinnerung",
            reminder_at=timezone.now() - timezone.timedelta(minutes=5),
        )
        future_note = Note.objects.create(
            title="Spaeter",
            reminder_at=timezone.now() + timezone.timedelta(days=1),
        )
        Note.objects.create(title="Ohne Erinnerung")

        response = self.client.get(reverse("notes"), {"scope": "reminders"})

        all_results = list(response.context["pinned_notes"]) + list(response.context["normal_notes"])
        self.assertIn(due_note, all_results)
        self.assertIn(future_note, all_results)
        self.assertEqual(response.context["reminder_note_count"], 2)
        self.assertEqual(response.context["due_reminder_count"], 1)

    def test_create_note(self):
        response = self.client.post(reverse("note_create"), {
            "title": "Neue Notiz",
            "content": "<p>Hallo</p>",
            "tags": "schule",
            "color": "green",
        })

        self.assertRedirects(response, reverse("notes"))

        note = Note.objects.get(title="Neue Notiz")

        self.assertEqual(note.color, "green")

    def test_create_note_can_set_reminder_and_share_with_friend(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        reminder_at = (timezone.now() + timezone.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")

        response = self.client.post(reverse("note_create"), {
            "title": "Geteilte Aufgabe",
            "content": "<p>Bitte lesen</p>",
            "tags": "team",
            "color": "green",
            "reminder_at": reminder_at,
            "shared_with": [str(friend.id)],
        })

        self.assertRedirects(response, reverse("notes"))
        note = Note.objects.get(title="Geteilte Aufgabe")
        self.assertEqual(list(note.shared_with.all()), [friend])
        self.assertIsNotNone(note.reminder_at)
        self.assertTrue(InboxItem.objects.filter(user=friend, title="Notiz geteilt").exists())

    def test_edit_note(self):
        note = Note.objects.create(title="Alt", content="Alt")

        response = self.client.post(reverse("note_edit", args=[note.id]), {
            "title": "Neu",
            "content": "<p>Neu</p>",
            "tags": "updated",
            "color": "purple",
        })

        self.assertRedirects(response, reverse("notes"))

        note.refresh_from_db()

        self.assertEqual(note.title, "Neu")
        self.assertEqual(note.color, "purple")

    def test_shared_note_detail_is_readable_but_not_editable_by_recipient(self):
        owner = get_user_model().objects.create_user(
            username="besitzer",
            password="testpass-123",
        )
        note = Note.objects.create(user=owner, title="Freigegeben", content="<p>Volltext</p>")
        note.shared_with.add(self.user)

        detail_response = self.client.get(reverse("note_detail", args=[note.id]))
        edit_response = self.client.get(reverse("note_edit", args=[note.id]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Volltext")
        self.assertEqual(edit_response.status_code, 404)

    def test_delete_note_requires_post_and_deletes_note(self):
        note = Note.objects.create(title="Weg")

        get_response = self.client.get(reverse("note_delete", args=[note.id]))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("note_delete", args=[note.id]))

        self.assertRedirects(post_response, reverse("notes"))
        self.assertFalse(Note.objects.filter(id=note.id).exists())
        self.assertTrue(Note.all_objects.filter(id=note.id, deleted_at__isnull=False).exists())

    def test_toggle_pin_note(self):
        note = Note.objects.create(title="Pin", is_pinned=False)

        response = self.client.post(reverse("note_toggle_pin", args=[note.id]))

        self.assertRedirects(response, reverse("notes"))

        note.refresh_from_db()

        self.assertTrue(note.is_pinned)

    def test_toggle_archive_note(self):
        note = Note.objects.create(title="Archiv", is_archived=False)

        response = self.client.post(reverse("note_toggle_archive", args=[note.id]))

        self.assertRedirects(response, reverse("notes"))

        note.refresh_from_db()

        self.assertTrue(note.is_archived)


class AvatarApiTests(BaseTestCase):
    def test_avatar_characters_api_get_returns_characters(self):
        character = AvatarCharacter.objects.create(
            name="Katara",
            nation="Wasser",
            link="https://example.com/katara",
            description="Wasserbändigerin",
            image=self.get_test_image(),
            order=2,
        )

        response = self.client.get(reverse("avatar-characters-api"))

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["characters"][0]["id"], character.id)
        self.assertEqual(data["characters"][0]["name"], "Katara")
        self.assertEqual(data["characters"][0]["nation"], "Wasser")

    def test_avatar_characters_api_post_creates_character(self):
        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "Zuko",
            "nation": "Feuer",
            "link": "https://example.com/zuko",
            "description": "Prinz der Feuernation",
            "image": self.get_test_image(),
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(AvatarCharacter.objects.filter(name="Zuko").exists())

    def test_avatar_characters_api_validates_required_fields(self):
        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "",
            "nation": "Feuer",
            "image": self.get_test_image(),
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Name fehlt.")

        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "Toph",
            "nation": "Metall",
            "image": self.get_test_image(),
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Ungültige Nation.")

        response = self.client.post(reverse("avatar-characters-api"), {
            "name": "Toph",
            "nation": "Erde",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Bild fehlt.")

    def test_avatar_characters_api_update_order_json(self):
        first = AvatarCharacter.objects.create(
            name="Aang",
            nation="Luft",
            image=self.get_test_image("aang.png"),
            order=0,
        )
        second = AvatarCharacter.objects.create(
            name="Toph",
            nation="Erde",
            image=self.get_test_image("toph.png"),
            order=1,
        )

        response = self.client.post(
            reverse("avatar-characters-api"),
            data=json.dumps({
                "action": "update_order",
                "character_ids": [
                    second.id,
                    first.id,
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(first.order, 1)
        self.assertEqual(second.order, 0)

    def test_avatar_characters_api_rejects_invalid_json_action(self):
        response = self.client.post(
            reverse("avatar-characters-api"),
            data=json.dumps({
                "action": "unknown",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Unbekannte Aktion.")

    def test_avatar_character_detail_api_updates_character(self):
        character = AvatarCharacter.objects.create(
            name="Alt",
            nation="Feuer",
            image=self.get_test_image("old.png"),
        )

        response = self.client.post(reverse("avatar-character-detail-api", args=[character.id]), {
            "name": "Azula",
            "nation": "Feuer",
            "link": "https://example.com/azula",
            "description": "Blitzbändigerin",
        })

        self.assertEqual(response.status_code, 200)

        character.refresh_from_db()

        self.assertEqual(character.name, "Azula")
        self.assertEqual(character.link, "https://example.com/azula")

    def test_avatar_character_detail_api_delete_character(self):
        character = AvatarCharacter.objects.create(
            name="Sokka",
            nation="Wasser",
            image=self.get_test_image(),
        )

        response = self.client.delete(reverse("avatar-character-detail-api", args=[character.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertFalse(AvatarCharacter.objects.filter(id=character.id).exists())

    def test_avatar_character_detail_api_rejects_wrong_method(self):
        character = AvatarCharacter.objects.create(
            name="Suki",
            nation="Erde",
            image=self.get_test_image(),
        )

        response = self.client.get(reverse("avatar-character-detail-api", args=[character.id]))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["message"], "Methode nicht erlaubt.")



class HumanBenchmarkTests(BaseTestCase):
    def post_score(self, payload):
        return self.client.post(
            reverse("human-benchmark-score-api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_human_benchmark_page_contains_score_data(self):
        HumanBenchmarkScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=210,
            display_score="210 ms",
        )
        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=210,
            display_score="210 ms",
        )

        response = self.client.get(reverse("human-benchmark"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/human_benchmark.html")
        self.assertIn("score_data", response.context)
        self.assertIn("reaction", response.context["score_data"]["games"])
        self.assertEqual(
            response.context["score_data"]["games"]["reaction"]["highscore"]["display_score"],
            "210 ms",
        )

    def test_human_benchmark_score_api_rejects_invalid_json(self):
        response = self.client.post(
            reverse("human-benchmark-score-api"),
            data="{kaputt",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Ungültige Anfrage.")

    def test_human_benchmark_score_api_rejects_unknown_game(self):
        response = self.post_score({
            "game": "unknown",
            "score": 123,
            "display_score": "123",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Unbekannter Spielmodus.")

    def test_human_benchmark_score_api_rejects_invalid_score(self):
        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_REACTION,
            "score": "abc",
            "display_score": "abc",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Ungültiger Score.")

        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_REACTION,
            "score": -1,
            "display_score": "-1 ms",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Ungültiger Score.")

    def test_human_benchmark_score_api_saves_score_and_first_highscore(self):
        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_AIM,
            "score": 5500,
            "display_score": "5.50 s",
            "details": {
                "accuracy": 92,
                "hits": 30,
                "misses": 2,
            },
        })

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["new_highscore"])
        self.assertEqual(HumanBenchmarkScore.objects.count(), 1)
        self.assertEqual(HumanBenchmarkHighScore.objects.count(), 1)

        highscore = HumanBenchmarkHighScore.objects.get(
            user=self.user,
            game=HumanBenchmarkScore.GAME_AIM,
        )

        self.assertEqual(highscore.score, 5500)
        self.assertEqual(highscore.display_score, "5.50 s")
        self.assertEqual(highscore.details["accuracy"], 92)

    def test_human_benchmark_lower_score_is_better_for_reaction(self):
        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=300,
            display_score="300 ms",
        )

        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_REACTION,
            "score": 240,
            "display_score": "240 ms",
            "details": {
                "attempts": 5,
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["new_highscore"])

        highscore = HumanBenchmarkHighScore.objects.get(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
        )

        self.assertEqual(highscore.score, 240)
        self.assertEqual(highscore.display_score, "240 ms")

    def test_human_benchmark_worse_reaction_score_does_not_replace_highscore(self):
        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=240,
            display_score="240 ms",
        )

        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_REACTION,
            "score": 300,
            "display_score": "300 ms",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["new_highscore"])

        highscore = HumanBenchmarkHighScore.objects.get(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
        )

        self.assertEqual(highscore.score, 240)
        self.assertEqual(highscore.display_score, "240 ms")
        self.assertEqual(HumanBenchmarkScore.objects.count(), 1)

    def test_human_benchmark_higher_score_is_better_for_typing(self):
        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_TYPING,
            score=60,
            display_score="60 WPM",
        )

        response = self.post_score({
            "game": HumanBenchmarkScore.GAME_TYPING,
            "score": 75,
            "display_score": "75 WPM",
            "details": {
                "accuracy": 98,
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["new_highscore"])

        highscore = HumanBenchmarkHighScore.objects.get(
            user=self.user,
            game=HumanBenchmarkScore.GAME_TYPING,
        )

        self.assertEqual(highscore.score, 75)
        self.assertEqual(highscore.display_score, "75 WPM")
        self.assertEqual(highscore.details["accuracy"], 98)

    def test_human_benchmark_recent_scores_are_limited_to_last_ten(self):
        for index in range(12):
            HumanBenchmarkScore.objects.create(
                user=self.user,
                game=HumanBenchmarkScore.GAME_VISUAL,
                score=index,
                display_score=f"Level {index}",
            )

        response = self.client.get(reverse("human-benchmark"))

        recent = response.context["score_data"]["games"]["visual"]["recent"]

        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0]["display_score"], "Level 11")
        self.assertEqual(recent[-1]["display_score"], "Level 2")

    def test_human_benchmark_leaderboard_is_per_game_and_sorted(self):
        other_user = get_user_model().objects.create_user(
            username="anderer",
            password="testpass-123",
        )
        HumanBenchmarkHighScore.objects.create(
            user=self.user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=240,
            display_score="240 ms",
        )
        HumanBenchmarkHighScore.objects.create(
            user=other_user,
            game=HumanBenchmarkScore.GAME_REACTION,
            score=180,
            display_score="180 ms",
        )

        response = self.client.get(reverse("human-benchmark"))

        leaderboard = response.context["score_data"]["games"]["reaction"]["leaderboard"]

        self.assertEqual(leaderboard[0]["username"], "anderer")
        self.assertEqual(leaderboard[0]["display_score"], "180 ms")
        self.assertEqual(leaderboard[1]["username"], "testuser")
        self.assertEqual(leaderboard[1]["display_score"], "240 ms")


class GeniusSearchApiTests(BaseTestCase):
    def mocked_genius_response(self, status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {
            "meta": {
                "status": 200,
            },
            "response": {
                "hits": [
                    {
                        "result": {
                            "title": "Harder Better Faster Stronger",
                            "url": "https://genius.com/daft-punk",
                            "song_art_image_thumbnail_url": "https://example.com/img.jpg",
                            "primary_artist": {
                                "name": "Daft Punk",
                            },
                        }
                    }
                ]
            },
        }
        return response

    def test_genius_search_api_requires_query(self):
        response = self.client.get(reverse("genius-search-api"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Suchbegriff fehlt.")

    @patch("app.views.get_env_value", return_value="")
    def test_genius_search_api_handles_missing_api_key(self, mock_get_env_value):
        response = self.client.get(reverse("genius-search-api"), {
            "q": "Daft Punk",
        })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "GENIUS_API_KEY fehlt in der .env.")

    @patch("app.views.get_env_value", return_value="test-genius-key")
    @patch("app.views.requests.get")
    def test_genius_search_api_returns_results(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_genius_response()

        response = self.client.get(reverse("genius-search-api"), {
            "q": "Daft Punk",
            "page": "2",
            "per_page": "8",
        })

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["results"][0]["title"], "Harder Better Faster Stronger")
        self.assertEqual(data["results"][0]["artist"], "Daft Punk")
        self.assertEqual(mock_get.call_args.kwargs["params"]["page"], 2)
        self.assertEqual(mock_get.call_args.kwargs["params"]["per_page"], 8)

    @patch("app.views.get_env_value", return_value="test-genius-key")
    def test_genius_search_api_rejects_invalid_pagination(self, mock_get_env_value):
        response = self.client.get(reverse("genius-search-api"), {
            "q": "Daft Punk",
            "page": "abc",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Pagination-Parameter sind ungültig.")

    @patch("app.views.get_env_value", return_value="test-genius-key")
    @patch("app.views.requests.get")
    def test_genius_search_api_handles_api_error(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_genius_response(
            status_code=401,
            json_data={
                "meta": {
                    "message": "Unauthorized",
                },
            },
        )

        response = self.client.get(reverse("genius-search-api"), {
            "q": "Daft Punk",
        })

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Unauthorized")

    @patch("app.views.get_env_value", return_value="test-genius-key")
    @patch("app.views.requests.get")
    def test_genius_search_api_handles_connection_error(self, mock_get, mock_get_env_value):
        mock_get.side_effect = requests.RequestException()

        response = self.client.get(reverse("genius-search-api"), {
            "q": "Daft Punk",
        })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Genius API konnte nicht erreicht werden.")


class SkribbleLobbyTests(BaseTestCase):
    def create_lobby(self):
        lobby = DrawingGameLobby.objects.create(
            owner=self.user,
            name="Test-Lobby",
            code="ABC123",
        )
        DrawingGamePlayer.objects.create(lobby=lobby, user=self.user, display_name="Testuser")
        return lobby

    def test_state_api_reports_deleted_lobby_for_open_clients(self):
        lobby = self.create_lobby()
        code = lobby.code
        lobby.delete()

        response = self.client.get(reverse("skribble_state_api", args=[code]))

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["lobbyDeleted"])
        self.assertEqual(response.json()["redirectUrl"], reverse("skribble_home"))

    def test_deleted_lobby_page_redirects_to_skribble_home(self):
        lobby = self.create_lobby()
        code = lobby.code
        lobby.delete()

        response = self.client.get(reverse("skribble_lobby", args=[code]))

        self.assertRedirects(response, reverse("skribble_home"))

    def test_non_host_cannot_delete_lobby(self):
        lobby = self.create_lobby()
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        DrawingGamePlayer.objects.create(lobby=lobby, user=other_user, display_name="Gegner")
        self.client.force_login(other_user)

        response = self.client.post(reverse("skribble_delete_lobby", args=[lobby.code]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(DrawingGameLobby.objects.filter(code=lobby.code).exists())

    def test_draw_api_appends_segment_batches_without_losing_lines(self):
        lobby = self.create_lobby()
        lobby.status = DrawingGameLobby.STATUS_PLAYING
        lobby.current_word = "Haus"
        lobby.save(update_fields=["status", "current_word"])

        response = self.client.post(reverse("skribble_draw_api", args=[lobby.code]), {
            "action": "segments",
            "segments": json.dumps([
                {"id": "segment-2", "order": 2, "points": "2,2;3,3", "color": "#111827", "size": "7"},
                {"id": "segment-1", "order": 1, "points": "1,1;2,2", "color": "#111827", "size": "7"},
            ]),
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["drawingRevision"], 2)

        lobby.refresh_from_db()
        self.assertEqual(len(lobby.current_drawing), 2)
        self.assertEqual(lobby.current_drawing[0]["id"], "segment-1")
        self.assertEqual(lobby.current_drawing[1]["id"], "segment-2")

    def test_draw_api_deduplicates_retried_segments(self):
        lobby = self.create_lobby()
        lobby.status = DrawingGameLobby.STATUS_PLAYING
        lobby.current_word = "Haus"
        lobby.save(update_fields=["status", "current_word"])

        payload = json.dumps([
            {"id": "segment-1", "order": 1, "points": "1,1;2,2", "color": "#111827", "size": "7"},
        ])
        for _ in range(2):
            response = self.client.post(reverse("skribble_draw_api", args=[lobby.code]), {
                "action": "segments",
                "segments": payload,
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ok"])
            self.assertEqual(response.json()["drawingRevision"], 1)

        lobby.refresh_from_db()
        self.assertEqual(len(lobby.current_drawing), 1)
        self.assertEqual(lobby.current_drawing[0]["id"], "segment-1")

    def test_state_api_returns_drawing_delta_after_revision(self):
        lobby = self.create_lobby()
        lobby.current_drawing = [
            {"id": "segment-1", "order": 1, "points": "1,1;2,2", "color": "#111827", "size": 7},
            {"id": "segment-2", "order": 2, "points": "2,2;3,3", "color": "#111827", "size": 7},
        ]
        lobby.save(update_fields=["current_drawing"])

        response = self.client.get(reverse("skribble_state_api", args=[lobby.code]), {"after": "1"})

        self.assertEqual(response.status_code, 200)
        state = response.json()["state"]
        self.assertEqual(state["drawingRevision"], 2)
        self.assertEqual(state["drawing"], [])
        self.assertEqual(len(state["drawingDelta"]), 1)
        self.assertEqual(state["drawingDelta"][0]["id"], "segment-2")


class FileShareTests(BaseTestCase):
    def test_file_share_view_uses_default_profile_limit(self):
        response = self.client.get(reverse("file_share"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["max_share_mb"], "50 MB")
        self.assertEqual(response.context["max_share_bytes"], 50 * 1024 * 1024)
        self.assertFalse(response.context["max_share_unlimited"])

    def test_file_share_view_uses_custom_profile_limit(self):
        profile, _created = UserProfile.objects.get_or_create(user=self.user)
        profile.file_share_limit = UserProfile.FILE_SHARE_LIMIT_500
        profile.save(update_fields=["file_share_limit"])

        response = self.client.get(reverse("file_share"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["max_share_mb"], "500 MB")
        self.assertEqual(response.context["max_share_bytes"], 500 * 1024 * 1024)

    def test_file_share_upload_accepts_multiple_files(self):
        response = self.client.post(reverse("file_share_upload"), {
            "is_public_link": "on",
            "files": [
                SimpleUploadedFile("a.txt", b"a", content_type="text/plain"),
                SimpleUploadedFile("b.txt", b"b", content_type="text/plain"),
            ],
        })

        self.assertRedirects(response, reverse("file_share"))
        self.assertEqual(FileShare.objects.filter(owner=self.user).count(), 2)

    def test_owner_delete_moves_file_share_to_trash_and_keeps_file(self):
        share = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("restore-me.txt", b"keep me", content_type="text/plain"),
            original_name="restore-me.txt",
            size=7,
            content_type="text/plain",
            token="trash-file-token",
        )
        stored_name = share.file.name

        response = self.client.post(reverse("file_share_delete", args=[share.id]))

        self.assertRedirects(response, reverse("file_share"))
        self.assertFalse(FileShare.objects.filter(id=share.id).exists())
        trashed_share = FileShare.all_objects.get(id=share.id)
        self.assertIsNotNone(trashed_share.deleted_at)
        self.assertTrue(trashed_share.file.storage.exists(stored_name))

    def test_public_file_share_access_states_do_not_require_login(self):
        locked = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("locked.txt", b"secret", content_type="text/plain"),
            original_name="locked.txt",
            size=6,
            content_type="text/plain",
            token="locked-public-token",
            is_public_link=True,
            password_hash=make_password("pw"),
        )
        expired = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("expired.txt", b"old", content_type="text/plain"),
            original_name="expired.txt",
            size=3,
            content_type="text/plain",
            token="expired-public-token",
            is_public_link=True,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        limited = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("limited.txt", b"done", content_type="text/plain"),
            original_name="limited.txt",
            size=4,
            content_type="text/plain",
            token="limited-public-token",
            is_public_link=True,
            max_downloads=1,
            download_count=1,
        )

        self.client.logout()

        password_url = reverse("file_share_download", args=[locked.token])
        self.assertEqual(self.client.get(password_url).status_code, 200)
        self.assertEqual(self.client.get(reverse("file_share_download", args=[expired.token])).status_code, 410)
        self.assertEqual(self.client.get(reverse("file_share_download", args=[limited.token])).status_code, 410)

        password_response = self.client.post(password_url, {"password": "pw"})
        self.assertEqual(password_response.status_code, 302)
        download_response = self.client.get(password_url)
        self.assertEqual(download_response.status_code, 200)
        locked.refresh_from_db()
        self.assertEqual(locked.download_count, 1)


class ModerationTests(BaseTestCase):
    def make_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

    def test_moderation_requires_staff_user(self):
        response = self.client.get(reverse("moderation"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_staff_dashboard_shows_moderation_sources(self):
        self.make_staff()
        other_user = get_user_model().objects.create_user(
            username="reported-user",
            password="testpass-123",
            email="reported@example.com",
        )
        UserReport.objects.create(
            reporter=self.user,
            reported=other_user,
            reason=UserReport.REASON_SPAM,
            message="Spam im Profil",
        )
        ToolFeedback.objects.create(
            user=other_user,
            tool_key="chat",
            feedback_type=ToolFeedback.TYPE_BUG,
            title="Chat Fehler",
            message="Nachrichten laden langsam.",
        )
        FileShare.objects.create(
            owner=other_user,
            file=SimpleUploadedFile("proof.txt", b"hi", content_type="text/plain"),
            original_name="proof.txt",
            size=2,
            content_type="text/plain",
            token="moderation-proof-token",
            is_public_link=True,
        )
        UserBlock.objects.create(blocker=self.user, blocked=other_user)
        InboxItem.objects.create(user=other_user, title="System Hinweis", message="Test")

        response = self.client.get(reverse("moderation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "reported-user")
        self.assertContains(response, "Chat Fehler")
        self.assertContains(response, "proof.txt")
        self.assertContains(response, "System Hinweis")

    def test_staff_can_update_tool_access_rules_from_moderation(self):
        self.make_staff()

        response = self.client.post(reverse("moderation_tool_access"), {
            "access_cookie_cosmos_v2": SiteAccessSettings.TOOL_ACCESS_ADMIN,
            "access_calculator": SiteAccessSettings.TOOL_ACCESS_HIDDEN,
        })

        self.assertRedirects(response, reverse("moderation"))
        settings_obj = SiteAccessSettings.get_solo()
        self.assertEqual(settings_obj.get_tool_access_level("cookie_cosmos_v2"), SiteAccessSettings.TOOL_ACCESS_ADMIN)
        self.assertEqual(settings_obj.get_tool_access_level("calculator"), SiteAccessSettings.TOOL_ACCESS_HIDDEN)
        self.assertEqual(settings_obj.get_tool_access_level("notes"), SiteAccessSettings.TOOL_ACCESS_ALL)
        self.assertTrue(
            ModerationAuditLog.objects.filter(action=ModerationAuditLog.ACTION_TOOL_ACCESS_UPDATED).exists()
        )

    def test_tool_access_admin_level_blocks_normal_user_and_allows_staff(self):
        settings_obj = SiteAccessSettings.get_solo()
        settings_obj.set_tool_access_rules({"calculator": SiteAccessSettings.TOOL_ACCESS_ADMIN})
        settings_obj.save(update_fields=["tool_access_rules"])

        response = self.client.get(reverse("calculator"))
        self.assertRedirects(response, reverse("favorites"))

        json_response = self.client.get(
            reverse("calculator"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(json_response.status_code, 403)

        self.make_staff()
        response = self.client.get(reverse("calculator"))
        self.assertEqual(response.status_code, 200)

    def test_tool_access_legacy_none_level_is_treated_as_unpublished(self):
        settings_obj = SiteAccessSettings.get_solo()
        settings_obj.tool_access_rules = {"calculator": SiteAccessSettings.TOOL_ACCESS_NONE}
        settings_obj.save(update_fields=["tool_access_rules"])

        response = self.client.get(reverse("calculator"))
        self.assertRedirects(response, reverse("favorites"))

        self.make_staff()
        response = self.client.get(reverse("calculator"))
        self.assertEqual(response.status_code, 200)

    def test_tool_access_hidden_level_hides_tool_from_normal_user_but_allows_staff(self):
        settings_obj = SiteAccessSettings.get_solo()
        settings_obj.set_tool_access_rules({"calculator": SiteAccessSettings.TOOL_ACCESS_HIDDEN})
        settings_obj.save(update_fields=["tool_access_rules"])

        favorites_response = self.client.get(reverse("favorites"))
        self.assertEqual(favorites_response.status_code, 200)
        self.assertFalse(any(tool["key"] == "calculator" for tool in favorites_response.context["tools"]))

        search_response = self.client.get(reverse("global_search_api"), {"q": "calculator"})
        self.assertEqual(search_response.status_code, 200)
        self.assertFalse(any(result["url"] == reverse("calculator") for result in search_response.json()["results"]))

        direct_response = self.client.get(reverse("calculator"))
        self.assertRedirects(direct_response, reverse("favorites"))

        self.make_staff()
        staff_favorites_response = self.client.get(reverse("favorites"))
        self.assertEqual(staff_favorites_response.status_code, 200)
        staff_calculator = next(
            tool for tool in staff_favorites_response.context["tools"] if tool["key"] == "calculator"
        )
        self.assertTrue(staff_calculator["can_access"])
        self.assertEqual(staff_calculator["access_badge"], "Versteckt")

        staff_direct_response = self.client.get(reverse("calculator"))
        self.assertEqual(staff_direct_response.status_code, 200)

    def test_report_action_marks_report_resolved(self):
        self.make_staff()
        other_user = get_user_model().objects.create_user(
            username="reported-user",
            password="testpass-123",
        )
        report = UserReport.objects.create(
            reporter=self.user,
            reported=other_user,
            reason=UserReport.REASON_OTHER,
        )

        response = self.client.post(reverse("moderation_report_action", args=[report.id]))

        self.assertRedirects(response, reverse("moderation"))
        report.refresh_from_db()
        self.assertTrue(report.is_resolved)

    def test_feedback_status_action_updates_feedback(self):
        self.make_staff()
        feedback = ToolFeedback.objects.create(
            user=self.user,
            tool_key="notes",
            title="Mehr Farbe",
            message="Bitte weitere Notizfarben.",
        )

        response = self.client.post(
            reverse("moderation_feedback_status", args=[feedback.id]),
            {"status": ToolFeedback.STATUS_PLANNED},
        )

        self.assertRedirects(response, reverse("moderation"))
        feedback.refresh_from_db()
        self.assertEqual(feedback.status, ToolFeedback.STATUS_PLANNED)

    def test_file_share_delete_action_removes_share(self):
        self.make_staff()
        share = FileShare.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("remove.txt", b"bye", content_type="text/plain"),
            original_name="remove.txt",
            size=3,
            content_type="text/plain",
            token="moderation-remove-token",
        )

        response = self.client.post(reverse("moderation_file_share_delete", args=[share.id]))

        self.assertRedirects(response, reverse("moderation"))
        self.assertFalse(FileShare.objects.filter(id=share.id).exists())

    def test_media_optimize_action_converts_existing_profile_images_to_webp(self):
        self.make_staff()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)
        old_name = profile.avatar.name
        old_size = profile.avatar.size

        response = self.client.post(reverse("moderation_media_optimize"))

        self.assertRedirects(response, reverse("moderation"))
        profile.refresh_from_db()
        self.assertTrue(profile.avatar.name.endswith(".webp"))
        self.assertNotEqual(profile.avatar.name, old_name)
        self.assertLess(profile.avatar.size, old_size)
        self.assertFalse(profile.avatar.storage.exists(old_name))
        self.assertTrue(ModerationAuditLog.objects.filter(action="media_optimized").exists())


    def test_media_optimize_action_compresses_static_page_images(self):
        self.make_staff()
        with tempfile.TemporaryDirectory() as tempdir:
            relative_path = "app/img/test-static-background.webp"
            static_file = Path(tempdir) / relative_path
            static_file.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1800, 1200), "white").save(static_file, "WEBP", quality=95)
            old_size = static_file.stat().st_size

            static_targets = (
                {
                    "path": relative_path,
                    "label": "Test-Hintergrund",
                    "max_size": (300, 200),
                    "quality": 60,
                },
            )
            with override_settings(STATIC_ROOT=tempdir), patch("app.moderation_views.STATIC_IMAGE_TARGETS", static_targets):
                response = self.client.post(reverse("moderation_media_optimize"))

            self.assertRedirects(response, reverse("moderation"))
            self.assertTrue(static_file.exists())
            self.assertLess(static_file.stat().st_size, old_size)
            audit_log = ModerationAuditLog.objects.filter(action="media_optimized").latest("created_at")
            self.assertGreaterEqual(audit_log.metadata["converted"], 1)

    def test_media_optimize_action_converts_image_file_shares(self):
        self.make_staff()
        share = FileShare.objects.create(
            owner=self.user,
            file=self.get_large_test_image("shared.bmp"),
            original_name="shared.bmp",
            size=1,
            content_type="image/bmp",
            token="image-share-token",
        )

        response = self.client.post(reverse("moderation_media_optimize"))

        self.assertRedirects(response, reverse("moderation"))
        share.refresh_from_db()
        self.assertTrue(share.file.name.endswith(".webp"))
        self.assertEqual(share.content_type, "image/webp")
        self.assertEqual(share.size, share.file.size)


class TicTacToeTests(BaseTestCase):
    def test_home_post_creates_room_for_current_user(self):
        response = self.client.post(reverse("tictactoe_home"), {
            "action": "create",
            "name": "Freunde-Runde",
        })

        game = TicTacToeGame.objects.get()

        self.assertRedirects(response, reverse("tictactoe_lobby", args=[game.code]))
        self.assertEqual(game.owner, self.user)
        self.assertEqual(game.player_x, self.user)
        self.assertEqual(game.status, TicTacToeGame.STATUS_WAITING)
        self.assertEqual(game.normalized_board, [""] * 9)

    def test_second_user_joins_as_o_and_starts_game(self):
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse("tictactoe_lobby", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.player_o, other_user)
        self.assertEqual(game.status, TicTacToeGame.STATUS_PLAYING)

    def test_move_api_rejects_wrong_turn_and_detects_win(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=other_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_PLAYING,
            board=["X", "X", "", "O", "O", "", "", "", ""],
            current_symbol=TicTacToeGame.SYMBOL_X,
        )

        self.client.force_login(other_user)
        response = self.client.post(reverse("tictactoe_move_api", args=[game.code]), {"index": 5})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Du bist noch nicht am Zug.")

        self.client.force_login(self.user)
        response = self.client.post(reverse("tictactoe_move_api", args=[game.code]), {"index": 2})

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.status, TicTacToeGame.STATUS_FINISHED)
        self.assertEqual(game.winner_symbol, TicTacToeGame.SYMBOL_X)
        self.assertEqual(game.winning_line, [0, 1, 2])

    def test_reset_api_starts_new_round(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=other_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_FINISHED,
            board=["X", "X", "X", "O", "O", "", "", "", ""],
            winner_symbol=TicTacToeGame.SYMBOL_X,
            winning_line=[0, 1, 2],
        )

        response = self.client.post(reverse("tictactoe_reset_api", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.status, TicTacToeGame.STATUS_PLAYING)
        self.assertEqual(game.normalized_board, [""] * 9)
        self.assertEqual(game.round_number, 2)
        self.assertEqual(game.current_symbol, TicTacToeGame.SYMBOL_X)

    def test_player_can_invite_friend(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )

        response = self.client.post(reverse("tictactoe_invite_friend", args=[game.code]), {
            "friend_id": friend.id,
        })

        self.assertRedirects(response, reverse("tictactoe_lobby", args=[game.code]))
        invite = TicTacToeInvite.objects.get(game=game, to_user=friend)
        self.assertEqual(invite.from_user, self.user)
        self.assertEqual(invite.status, TicTacToeInvite.STATUS_PENDING)

    def test_invite_acceptance_redirects_to_game_and_joins_as_o(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )
        invite = TicTacToeInvite.objects.create(
            game=game,
            from_user=self.user,
            to_user=friend,
        )
        self.client.force_login(friend)

        response = self.client.post(reverse("tictactoe_invite_response", args=[invite.id]), {
            "action": "accept",
        })

        self.assertRedirects(response, reverse("tictactoe_lobby", args=[game.code]), fetch_redirect_response=False)
        invite.refresh_from_db()
        self.assertEqual(invite.status, TicTacToeInvite.STATUS_ACCEPTED)

        self.client.get(reverse("tictactoe_lobby", args=[game.code]))
        game.refresh_from_db()
        self.assertEqual(game.player_o, friend)
        self.assertEqual(game.status, TicTacToeGame.STATUS_PLAYING)

    def test_full_game_rejects_additional_invites(self):
        second_user = get_user_model().objects.create_user(
            username="zweiter",
            password="testpass-123",
        )
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=second_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_PLAYING,
            board=[""] * 9,
        )

        response = self.client.post(reverse("tictactoe_invite_friend", args=[game.code]), {
            "friend_id": friend.id,
        })

        self.assertRedirects(response, reverse("tictactoe_lobby", args=[game.code]))
        self.assertFalse(TicTacToeInvite.objects.filter(game=game, to_user=friend).exists())

    def test_third_user_cannot_join_full_game(self):
        second_user = get_user_model().objects.create_user(
            username="zweiter",
            password="testpass-123",
        )
        third_user = get_user_model().objects.create_user(
            username="dritter",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=second_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_PLAYING,
            board=[""] * 9,
        )
        self.client.force_login(third_user)

        response = self.client.get(reverse("tictactoe_lobby", args=[game.code]))

        self.assertRedirects(response, reverse("tictactoe_home"))
        game.refresh_from_db()
        self.assertEqual(game.player_o, second_user)

    def test_delete_view_removes_game(self):
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )

        response = self.client.post(reverse("tictactoe_delete", args=[game.code]))

        self.assertRedirects(response, reverse("tictactoe_home"))
        self.assertFalse(TicTacToeGame.objects.filter(code="TTT123").exists())

    def test_non_host_cannot_delete_game(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=other_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_PLAYING,
            board=[""] * 9,
        )
        self.client.force_login(other_user)

        response = self.client.post(reverse("tictactoe_delete", args=[game.code]))

        self.assertRedirects(response, reverse("tictactoe_home"))
        self.assertTrue(TicTacToeGame.objects.filter(code=game.code).exists())

    def test_state_api_reports_deleted_game_for_open_clients(self):
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )
        code = game.code
        game.delete()

        response = self.client.get(reverse("tictactoe_state_api", args=[code]))

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["gameDeleted"])
        self.assertEqual(response.json()["redirectUrl"], reverse("tictactoe_home"))

    def test_leaving_empty_game_deletes_it(self):
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )

        response = self.client.post(reverse("tictactoe_leave", args=[game.code]))

        self.assertRedirects(response, reverse("tictactoe_home"))
        self.assertFalse(TicTacToeGame.objects.filter(code="TTT123").exists())

    def test_remaining_player_is_kept_when_opponent_leaves(self):
        second_user = get_user_model().objects.create_user(
            username="zweiter",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=second_user,
            code="TTT123",
            status=TicTacToeGame.STATUS_PLAYING,
            board=["X", "", "", "", "", "", "", "", ""],
            current_symbol=TicTacToeGame.SYMBOL_O,
        )
        self.client.force_login(second_user)

        response = self.client.post(reverse("tictactoe_leave", args=[game.code]))

        self.assertRedirects(response, reverse("tictactoe_home"))
        game.refresh_from_db()
        self.assertEqual(game.player_x, self.user)
        self.assertIsNone(game.player_o)
        self.assertEqual(game.status, TicTacToeGame.STATUS_WAITING)
        self.assertEqual(game.normalized_board, [""] * 9)

    def test_home_state_api_returns_current_games_and_invites(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            name="Live-Raum",
            board=[""] * 9,
        )
        invite_game = TicTacToeGame.objects.create(
            owner=friend,
            player_x=friend,
            code="INV123",
            name="Einladung",
            board=[""] * 9,
        )
        TicTacToeInvite.objects.create(
            game=invite_game,
            from_user=friend,
            to_user=self.user,
        )

        response = self.client.get(reverse("tictactoe_home_state_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["games"][0]["code"], game.code)
        self.assertEqual(data["games"][0]["name"], "Live-Raum")
        self.assertEqual(data["invites"][0]["gameName"], "Einladung")
        self.assertEqual(data["invites"][0]["fromUser"], "freund")

    def test_home_state_api_drops_deleted_games(self):
        game = TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            code="TTT123",
            board=[""] * 9,
        )

        first_response = self.client.get(reverse("tictactoe_home_state_api"))
        self.assertEqual(first_response.json()["games"][0]["code"], game.code)

        game.delete()
        second_response = self.client.get(reverse("tictactoe_home_state_api"))

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["games"], [])


class ConnectFourTests(BaseTestCase):
    def create_game(self, **overrides):
        data = {
            "owner": self.user,
            "player_red": self.user,
            "code": "CFO123",
        }
        data.update(overrides)
        return ConnectFourGame.objects.create(**data)

    def test_owner_can_delete_game(self):
        game = self.create_game()

        response = self.client.post(reverse("connectfour_delete", args=[game.code]))

        self.assertRedirects(response, reverse("connectfour_home"))
        self.assertFalse(ConnectFourGame.objects.filter(code=game.code).exists())

    def test_non_host_cannot_delete_game(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_yellow=other_user,
            status=ConnectFourGame.STATUS_PLAYING,
        )
        self.client.force_login(other_user)

        response = self.client.post(reverse("connectfour_delete", args=[game.code]))

        self.assertRedirects(response, reverse("connectfour_home"))
        self.assertTrue(ConnectFourGame.objects.filter(code=game.code).exists())

    def test_state_api_reports_deleted_game_for_open_clients(self):
        game = self.create_game()
        code = game.code
        game.delete()

        response = self.client.get(reverse("connectfour_state_api", args=[code]))

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["gameDeleted"])
        self.assertEqual(response.json()["redirectUrl"], reverse("connectfour_home"))


class StadtLandFlussTests(BaseTestCase):
    def create_lobby(self):
        lobby = StadtLandFlussLobby.objects.create(
            owner=self.user,
            name="SLF-Runde",
            code="SLF123",
        )
        StadtLandFlussPlayer.objects.create(lobby=lobby, user=self.user, display_name=self.user.username)
        return lobby

    def test_owner_can_delete_lobby(self):
        lobby = self.create_lobby()

        response = self.client.post(reverse("stadtlandfluss_delete", args=[lobby.code]))

        self.assertRedirects(response, reverse("stadtlandfluss_home"))
        self.assertFalse(StadtLandFlussLobby.objects.filter(code=lobby.code).exists())

    def test_non_host_cannot_delete_lobby(self):
        lobby = self.create_lobby()
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        StadtLandFlussPlayer.objects.create(lobby=lobby, user=other_user, display_name="Gegner")
        self.client.force_login(other_user)

        response = self.client.post(reverse("stadtlandfluss_delete", args=[lobby.code]))

        self.assertRedirects(response, reverse("stadtlandfluss_lobby", args=[lobby.code]))
        self.assertTrue(StadtLandFlussLobby.objects.filter(code=lobby.code).exists())

    def test_state_api_reports_deleted_lobby_for_open_clients(self):
        lobby = self.create_lobby()
        code = lobby.code
        lobby.delete()

        response = self.client.get(reverse("stadtlandfluss_state_api", args=[code]))

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["lobbyDeleted"])
        self.assertEqual(response.json()["redirectUrl"], reverse("stadtlandfluss_home"))


class UnoTests(BaseTestCase):
    def create_started_game(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = UnoGame.objects.create(
            owner=self.user,
            code="UNO123",
            status=UnoGame.STATUS_PLAYING,
            current_color="red",
            discard_pile=[{"id": "red-5-a", "color": "red", "value": "5", "type": "number", "label": "5"}],
            deck=[{"id": "green-1-a", "color": "green", "value": "1", "type": "number", "label": "1"}],
            hands={
                str(self.user.id): [
                    {"id": "red-7-a", "color": "red", "value": "7", "type": "number", "label": "7"},
                    {"id": "blue-9-a", "color": "blue", "value": "9", "type": "number", "label": "9"},
                ],
                str(other_user.id): [
                    {"id": "yellow-2-a", "color": "yellow", "value": "2", "type": "number", "label": "2"},
                ],
            },
        )
        UnoPlayer.objects.create(game=game, user=self.user, seat=0)
        UnoPlayer.objects.create(game=game, user=other_user, seat=1)
        return game

    def test_uno_can_be_called_before_playing_penultimate_card(self):
        game = self.create_started_game()

        call_response = self.client.post(reverse("uno_call_api", args=[game.code]))
        self.assertEqual(call_response.status_code, 200)
        self.assertTrue(call_response.json()["game"]["players"][0]["saidUno"])

        play_response = self.client.post(reverse("uno_play_api", args=[game.code]), {
            "card_id": "red-7-a",
        })

        self.assertEqual(play_response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(len(game.hands[str(self.user.id)]), 1)
        self.assertEqual(game.hands[str(self.user.id)][0]["id"], "blue-9-a")
        self.assertTrue((game.uno_calls or {}).get(str(self.user.id)))

    def test_forgetting_uno_before_penultimate_card_draws_one_penalty_card(self):
        game = self.create_started_game()

        response = self.client.post(reverse("uno_play_api", args=[game.code]), {
            "card_id": "red-7-a",
        })

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(len(game.hands[str(self.user.id)]), 2)
        self.assertEqual(
            [card["id"] for card in game.hands[str(self.user.id)]],
            ["blue-9-a", "green-1-a"],
        )
        self.assertFalse((game.uno_calls or {}).get(str(self.user.id)))
        self.assertIn("Uno vergessen", " ".join(game.action_log))


class KniffelTests(BaseTestCase):
    def create_game_with_players(self, player_count=2, **overrides):
        game = KniffelGame.objects.create(
            owner=self.user,
            code=overrides.pop("code", "KNF123"),
            **overrides,
        )
        KniffelPlayer.objects.create(game=game, user=self.user, seat=0)
        players = [self.user]
        for index in range(1, player_count):
            user = get_user_model().objects.create_user(
                username=f"kniffel{index}",
                password="testpass-123",
            )
            KniffelPlayer.objects.create(game=game, user=user, seat=index)
            players.append(user)
        return game, players

    def test_home_post_creates_room_for_current_user(self):
        response = self.client.post(reverse("kniffel_home"), {
            "action": "create",
            "name": "Wuerfelrunde",
            "max_players": "5",
        })

        game = KniffelGame.objects.get()

        self.assertRedirects(response, reverse("kniffel_lobby", args=[game.code]))
        self.assertEqual(game.owner, self.user)
        self.assertEqual(game.players.get().user, self.user)
        self.assertEqual(game.max_players, 5)

    def test_player_can_invite_friend_and_friend_accepts(self):
        friend = get_user_model().objects.create_user(
            username="kniffelfreund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        game, _players = self.create_game_with_players(player_count=1)

        response = self.client.post(reverse("kniffel_invite_friend", args=[game.code]), {
            "friend_id": friend.id,
        })

        self.assertRedirects(response, reverse("kniffel_lobby", args=[game.code]))
        invite = KniffelInvite.objects.get(game=game, to_user=friend)
        self.assertEqual(invite.status, KniffelInvite.STATUS_PENDING)

        self.client.force_login(friend)
        response = self.client.post(reverse("kniffel_invite_response", args=[invite.id]), {
            "action": "accept",
        })

        self.assertRedirects(response, reverse("kniffel_lobby", args=[game.code]), fetch_redirect_response=False)
        invite.refresh_from_db()
        self.assertEqual(invite.status, KniffelInvite.STATUS_ACCEPTED)

        lobby_response = self.client.get(reverse("kniffel_lobby", args=[game.code]))

        self.assertEqual(lobby_response.status_code, 200)
        self.assertTrue(KniffelPlayer.objects.filter(game=game, user=friend).exists())

    def test_roll_score_and_leave_keeps_three_player_game_running(self):
        game, players = self.create_game_with_players(player_count=3)

        start_response = self.client.post(reverse("kniffel_start_api", args=[game.code]))
        self.assertEqual(start_response.status_code, 200)

        roll_response = self.client.post(reverse("kniffel_roll_api", args=[game.code]), {
            "kept_indices": "[]",
        })
        self.assertEqual(roll_response.status_code, 200)
        dice = roll_response.json()["game"]["dice"]
        self.assertEqual(len(dice), 5)

        score_response = self.client.post(reverse("kniffel_score_api", args=[game.code]), {
            "category": "chance",
        })
        self.assertEqual(score_response.status_code, 200)
        game.refresh_from_db()
        self.assertIn("chance", game.scores[str(self.user.id)])
        self.assertEqual(game.current_player_index, 1)

        self.client.force_login(players[2])
        leave_response = self.client.post(reverse("kniffel_leave", args=[game.code]))

        self.assertRedirects(leave_response, reverse("kniffel_home"))
        game.refresh_from_db()
        self.assertEqual(game.status, KniffelGame.STATUS_PLAYING)
        self.assertEqual(game.players.count(), 2)


class BattleshipTests(BaseTestCase):
    def create_game(self, **overrides):
        data = {
            "owner": self.user,
            "player_a": self.user,
            "code": "SEA123",
        }
        data.update(overrides)
        return BattleshipGame.objects.create(**data)

    def test_home_post_creates_room_for_current_user(self):
        response = self.client.post(reverse("battleship_home"), {
            "action": "create",
            "name": "Flottenrunde",
        })

        game = BattleshipGame.objects.get()

        self.assertRedirects(response, reverse("battleship_lobby", args=[game.code]))
        self.assertEqual(game.owner, self.user)
        self.assertEqual(game.player_a, self.user)
        self.assertEqual(game.status, BattleshipGame.STATUS_WAITING)

    def test_second_user_joins_and_starts_setup(self):
        game = self.create_game()
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse("battleship_lobby", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.player_b, other_user)
        self.assertEqual(game.status, BattleshipGame.STATUS_SETUP)

    def test_full_game_rejects_additional_invites_and_third_join(self):
        second_user = get_user_model().objects.create_user(
            username="zweiter",
            password="testpass-123",
        )
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        game = self.create_game(
            player_b=second_user,
            status=BattleshipGame.STATUS_SETUP,
        )

        response = self.client.post(reverse("battleship_invite_friend", args=[game.code]), {
            "friend_id": friend.id,
        })

        self.assertRedirects(response, reverse("battleship_lobby", args=[game.code]))
        self.assertFalse(BattleshipInvite.objects.filter(game=game, to_user=friend).exists())

        self.client.force_login(friend)
        response = self.client.get(reverse("battleship_lobby", args=[game.code]))

        self.assertRedirects(response, reverse("battleship_home"))

    def test_player_can_invite_friend_and_friend_accepts(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        Friendship.objects.create(
            from_user=self.user,
            to_user=friend,
            status=Friendship.STATUS_ACCEPTED,
        )
        game = self.create_game()

        response = self.client.post(reverse("battleship_invite_friend", args=[game.code]), {
            "friend_id": friend.id,
        })

        self.assertRedirects(response, reverse("battleship_lobby", args=[game.code]))
        invite = BattleshipInvite.objects.get(game=game, to_user=friend)
        self.assertEqual(invite.status, BattleshipInvite.STATUS_PENDING)

        self.client.force_login(friend)
        response = self.client.post(reverse("battleship_invite_response", args=[invite.id]), {
            "action": "accept",
        })

        self.assertRedirects(response, reverse("battleship_lobby", args=[game.code]), fetch_redirect_response=False)
        invite.refresh_from_db()
        self.assertEqual(invite.status, BattleshipInvite.STATUS_ACCEPTED)

        self.client.get(reverse("battleship_lobby", args=[game.code]))
        game.refresh_from_db()
        self.assertEqual(game.player_b, friend)
        self.assertEqual(game.status, BattleshipGame.STATUS_SETUP)

    def test_place_api_sets_ready_and_game_starts_when_both_ready(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_SETUP,
        )

        response = self.client.post(reverse("battleship_place_api", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertTrue(game.ready_a)
        self.assertEqual(len(game.fleet_a), 5)
        self.assertEqual(game.status, BattleshipGame.STATUS_SETUP)

        self.client.force_login(other_user)
        response = self.client.post(reverse("battleship_place_api", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertTrue(game.ready_b)
        self.assertEqual(game.status, BattleshipGame.STATUS_PLAYING)

    def test_place_api_accepts_manual_fleet(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_SETUP,
        )
        fleet = [
            {"id": "carrier", "length": 4, "cells": [0, 1, 2, 3]},
            {"id": "cruiser", "length": 3, "cells": [8, 9, 10]},
            {"id": "submarine", "length": 3, "cells": [16, 24, 32]},
            {"id": "destroyer", "length": 2, "cells": [20, 21]},
            {"id": "patrol", "length": 2, "cells": [30, 38]},
        ]

        response = self.client.post(reverse("battleship_place_api", args=[game.code]), {
            "fleet": json.dumps(fleet),
        })

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertTrue(game.ready_a)
        self.assertEqual(game.fleet_a[0]["id"], "carrier")
        self.assertEqual(game.fleet_a[0]["cells"], [0, 1, 2, 3])

    def test_place_api_rejects_overlapping_manual_fleet(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_SETUP,
        )
        fleet = [
            {"id": "carrier", "length": 4, "cells": [0, 1, 2, 3]},
            {"id": "cruiser", "length": 3, "cells": [1, 9, 17]},
            {"id": "submarine", "length": 3, "cells": [16, 24, 32]},
            {"id": "destroyer", "length": 2, "cells": [20, 21]},
            {"id": "patrol", "length": 2, "cells": [30, 38]},
        ]

        response = self.client.post(reverse("battleship_place_api", args=[game.code]), {
            "fleet": json.dumps(fleet),
        })

        self.assertEqual(response.status_code, 400)
        game.refresh_from_db()
        self.assertFalse(game.ready_a)

    def test_attack_api_rejects_wrong_turn_and_detects_win(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_PLAYING,
            ready_a=True,
            ready_b=True,
            fleet_a=[{"id": "a", "length": 1, "cells": [10]}],
            fleet_b=[{"id": "b", "length": 1, "cells": [7]}],
            current_turn=BattleshipGame.SIDE_A,
        )

        self.client.force_login(other_user)
        response = self.client.post(reverse("battleship_attack_api", args=[game.code]), {"index": 10})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Du bist noch nicht am Zug.")

        self.client.force_login(self.user)
        response = self.client.post(reverse("battleship_attack_api", args=[game.code]), {"index": 7})

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.status, BattleshipGame.STATUS_FINISHED)
        self.assertEqual(game.winner_side, BattleshipGame.SIDE_A)
        self.assertEqual(game.shots_a, [7])

    def test_attack_hit_keeps_current_turn_and_miss_switches_turn(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_PLAYING,
            ready_a=True,
            ready_b=True,
            fleet_a=[{"id": "a", "length": 2, "cells": [10, 11]}],
            fleet_b=[{"id": "b", "length": 2, "cells": [7, 8]}],
            current_turn=BattleshipGame.SIDE_A,
        )

        response = self.client.post(reverse("battleship_attack_api", args=[game.code]), {"index": 7})

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.current_turn, BattleshipGame.SIDE_A)
        self.assertEqual(game.status, BattleshipGame.STATUS_PLAYING)

        response = self.client.post(reverse("battleship_attack_api", args=[game.code]), {"index": 20})

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.current_turn, BattleshipGame.SIDE_B)

    def test_only_host_can_reset_game(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_FINISHED,
            ready_a=True,
            ready_b=True,
            winner_side=BattleshipGame.SIDE_A,
        )

        self.client.force_login(other_user)
        response = self.client.post(reverse("battleship_reset_api", args=[game.code]))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Nur der Host kann eine neue Runde starten.")

        self.client.force_login(self.user)
        response = self.client.post(reverse("battleship_reset_api", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.status, BattleshipGame.STATUS_SETUP)
        self.assertEqual(game.round_number, 2)

    def test_delete_and_empty_leave_remove_game(self):
        game = self.create_game()

        response = self.client.post(reverse("battleship_delete", args=[game.code]))

        self.assertRedirects(response, reverse("battleship_home"))
        self.assertFalse(BattleshipGame.objects.filter(code=game.code).exists())

    def test_non_host_cannot_delete_game(self):
        other_user = get_user_model().objects.create_user(
            username="gegner",
            password="testpass-123",
        )
        game = self.create_game(
            player_b=other_user,
            status=BattleshipGame.STATUS_SETUP,
        )
        self.client.force_login(other_user)

        response = self.client.post(reverse("battleship_delete", args=[game.code]))

        self.assertRedirects(response, reverse("battleship_home"))
        self.assertTrue(BattleshipGame.objects.filter(code=game.code).exists())

    def test_state_api_reports_deleted_game_for_open_clients(self):
        game = self.create_game()
        code = game.code
        game.delete()

        response = self.client.get(reverse("battleship_state_api", args=[code]))

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["gameDeleted"])
        self.assertEqual(response.json()["redirectUrl"], reverse("battleship_home"))

        game = self.create_game(code="SEA124")
        response = self.client.post(reverse("battleship_leave", args=[game.code]))

        self.assertRedirects(response, reverse("battleship_home"))
        self.assertFalse(BattleshipGame.objects.filter(code=game.code).exists())

    def test_home_state_api_returns_games_and_invites(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        game = self.create_game(name="Live-Flotte")
        invite_game = BattleshipGame.objects.create(
            owner=friend,
            player_a=friend,
            code="INV123",
            name="Einladung",
        )
        BattleshipInvite.objects.create(
            game=invite_game,
            from_user=friend,
            to_user=self.user,
        )

        response = self.client.get(reverse("battleship_home_state_api"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["games"][0]["name"], "Live-Flotte")
        self.assertEqual(data["invites"][0]["gameName"], "Einladung")
        self.assertEqual(data["invites"][0]["fromUser"], "freund")

    def test_battleship_invites_are_counted_in_notifications(self):
        friend = get_user_model().objects.create_user(
            username="freund",
            password="testpass-123",
        )
        game = BattleshipGame.objects.create(
            owner=friend,
            player_a=friend,
            code="INV123",
            name="Einladung",
        )
        BattleshipInvite.objects.create(
            game=game,
            from_user=friend,
            to_user=self.user,
        )

        counts = get_notification_counts(self.user)

        self.assertEqual(counts["battleship_invites"], 1)
        self.assertGreaterEqual(counts["total_notifications"], 1)

    def test_notification_center_counts_reminders_file_shares_and_game_turns(self):
        friend = get_user_model().objects.create_user(
            username="sharefreund",
            password="testpass-123",
        )
        Note.objects.create(
            user=self.user,
            title="Faellige Erinnerung",
            reminder_at=timezone.now() - timezone.timedelta(minutes=5),
        )
        share = FileShare.objects.create(
            owner=friend,
            file=SimpleUploadedFile("shared.txt", b"shared", content_type="text/plain"),
            original_name="shared.txt",
            size=6,
            content_type="text/plain",
            token="notification-share-token",
        )
        share.recipients.add(self.user)
        TicTacToeGame.objects.create(
            owner=self.user,
            player_x=self.user,
            player_o=friend,
            code="NOTIFTTT",
            status=TicTacToeGame.STATUS_PLAYING,
            board=[""] * 9,
            current_symbol=TicTacToeGame.SYMBOL_X,
        )

        counts = get_notification_counts(self.user)
        items = get_notification_items(self.user, limit=20)
        item_types = {item["type"] for item in items}

        self.assertEqual(counts["note_reminders"], 1)
        self.assertEqual(counts["shared_files"], 1)
        self.assertEqual(counts["game_turns"], 1)
        self.assertIn("reminder", item_types)
        self.assertIn("file_share", item_types)
        self.assertIn("game_turn", item_types)


class TankstellenApiTests(BaseTestCase):
    def mocked_tanker_response(self, status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {
            "ok": True,
            "stations": [
                {
                    "name": "Test Tankstelle",
                    "price": 1.75,
                    "dist": 1.2,
                },
            ],
        }
        return response

    def test_tankstellen_api_requires_lat_lon(self):
        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "52.52",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Latitude und Longitude fehlen.")

    def test_tankstellen_api_rejects_invalid_coordinates(self):
        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "abc",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Latitude und Longitude müssen Zahlen sein.")

    @patch("app.views.get_env_value", return_value="")
    def test_tankstellen_api_handles_missing_api_key(self, mock_get_env_value):
        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "52.52",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "TANKERKOENIG_API_KEY fehlt in der .env.")

    @patch("app.views.get_env_value", return_value="test-tanker-key")
    @patch("app.views.requests.get")
    def test_tankstellen_api_returns_external_data(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_tanker_response()

        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "52.52",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["stations"][0]["name"], "Test Tankstelle")
        self.assertEqual(mock_get.call_args.kwargs["params"]["lat"], 52.52)
        self.assertEqual(mock_get.call_args.kwargs["params"]["lng"], 13.405)

    @patch("app.views.get_env_value", return_value="test-tanker-key")
    @patch("app.views.requests.get")
    def test_tankstellen_api_handles_api_error(self, mock_get, mock_get_env_value):
        mock_get.return_value = self.mocked_tanker_response(
            status_code=403,
            json_data={
                "message": "Invalid API key",
            },
        )

        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "52.52",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["message"], "Invalid API key")

    @patch("app.views.get_env_value", return_value="test-tanker-key")
    @patch("app.views.requests.get")
    def test_tankstellen_api_handles_connection_error(self, mock_get, mock_get_env_value):
        mock_get.side_effect = requests.RequestException()

        response = self.client.get(reverse("tankstellen-api"), {
            "lat": "52.52",
            "lon": "13.405",
        })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Tankerkönig API konnte nicht erreicht werden.")



class Game2048Tests(BaseTestCase):
    def post_score(self, payload):
        return self.client.post(
            reverse("game-2048-score-api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_2048_page_renders(self):
        response = self.client.get(reverse("game-2048"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/game_2048.html")
        self.assertContains(response, "2048")
        self.assertContains(response, reverse("game-2048-score-api"))

    def test_2048_score_api_creates_and_keeps_best_score(self):
        response = self.post_score({
            "score": 4096,
            "best_tile": 512,
            "moves": 120,
            "duration_seconds": 180,
            "won": False,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["new_highscore"])
        highscore = Game2048HighScore.objects.get(user=self.user)
        self.assertEqual(highscore.score, 4096)
        self.assertEqual(highscore.best_tile, 512)
        self.assertEqual(highscore.games_played, 1)

        lower_response = self.post_score({
            "score": 2000,
            "best_tile": 1024,
            "moves": 80,
            "duration_seconds": 90,
            "won": True,
        })

        self.assertEqual(lower_response.status_code, 200)
        self.assertFalse(lower_response.json()["new_highscore"])
        highscore.refresh_from_db()
        self.assertEqual(highscore.score, 4096)
        self.assertEqual(highscore.best_tile, 512)
        self.assertEqual(highscore.games_played, 2)
        self.assertTrue(highscore.won)

    def test_2048_score_api_rejects_invalid_score(self):
        response = self.post_score({
            "score": -1,
            "best_tile": 2,
            "moves": 0,
            "duration_seconds": 0,
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Game2048HighScore.objects.filter(user=self.user).exists())

    def test_2048_activity_api_sets_presence_status(self):
        response = self.client.post(reverse("game-2048-activity-api"))

        self.assertEqual(response.status_code, 200)
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "2048")
        self.assertEqual(presence.active_game_label, "spielt 2048")
        self.assertIsNotNone(presence.active_game_updated_at)

    def test_2048_highscore_counts_for_achievements(self):
        Game2048HighScore.objects.create(
            user=self.user,
            score=22000,
            best_tile=2048,
            moves=360,
            duration_seconds=420,
            won=True,
            games_played=10,
        )

        summary = get_achievement_summary(self.user)
        unlocked_keys = {achievement["key"] for achievement in summary["unlocked"]}

        self.assertIn("tile_1024", unlocked_keys)
        self.assertIn("tile_2048", unlocked_keys)
        self.assertIn("game_2048_regular", unlocked_keys)
        self.assertEqual(summary["metrics"]["game_2048_best_tile"], 2048)
        self.assertEqual(summary["metrics"]["game_2048_runs"], 10)


class PongMultiplayerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pong_a", password="pw")
        self.friend = get_user_model().objects.create_user(username="pong_b", password="pw")
        Friendship.objects.create(from_user=self.user, to_user=self.friend, status=Friendship.STATUS_ACCEPTED)
        self.client.login(username="pong_a", password="pw")

    def test_pong_home_creates_room_with_owner_as_left_player(self):
        response = self.client.post(reverse("pong_home"), {"action": "create", "name": "Arcade Night", "target_score": "11"})

        game = PongGame.objects.get(name="Arcade Night")
        self.assertRedirects(response, reverse("pong_lobby", args=[game.code]))
        self.assertEqual(game.owner, self.user)
        self.assertEqual(game.player_left, self.user)
        self.assertEqual(game.target_score, 11)
        self.assertEqual(game.status, PongGame.STATUS_WAITING)

    def test_second_player_joins_and_game_starts(self):
        game = PongGame.objects.create(owner=self.user, player_left=self.user, name="Pong", code="PNG123")
        self.client.logout()
        self.client.login(username="pong_b", password="pw")

        response = self.client.get(reverse("pong_lobby", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.player_right, self.friend)
        self.assertEqual(game.status, PongGame.STATUS_PLAYING)

    def test_pong_invite_counts_in_notifications(self):
        game = PongGame.objects.create(owner=self.user, player_left=self.user, name="Pong", code="INV123")
        PongInvite.objects.create(game=game, from_user=self.user, to_user=self.friend)

        counts = get_notification_counts(self.friend)
        items = get_notification_items(self.friend)

        self.assertEqual(counts["pong_invites"], 1)
        self.assertTrue(any(item["type"] == "pong" for item in items))

    def test_pong_paddle_api_updates_own_paddle_and_presence(self):
        game = PongGame.objects.create(
            owner=self.user,
            player_left=self.user,
            player_right=self.friend,
            name="Pong",
            code="PAD123",
            status=PongGame.STATUS_PLAYING,
        )

        response = self.client.post(reverse("pong_paddle_api", args=[game.code]), {"y": "82"})

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertAlmostEqual(game.paddle_left_y, 82.0)
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.active_game, "pong")
        self.assertEqual(presence.active_game_label, "spielt Pong")

    def test_pong_finished_match_unlocks_achievements(self):
        PongGame.objects.create(
            owner=self.user,
            player_left=self.user,
            player_right=self.friend,
            name="Finale",
            code="WIN123",
            status=PongGame.STATUS_FINISHED,
            winner_side=PongGame.SIDE_LEFT,
            score_left=7,
            score_right=4,
            best_rally=12,
        )

        summary = get_achievement_summary(self.user)
        unlocked_keys = {achievement["key"] for achievement in summary["unlocked"]}

        self.assertIn("pong_first_match", unlocked_keys)
        self.assertIn("pong_rally", unlocked_keys)
        self.assertEqual(summary["metrics"]["pong_matches"], 1)
        self.assertEqual(summary["metrics"]["pong_wins"], 1)
        self.assertEqual(summary["metrics"]["pong_best_rally"], 12)


class ColorPaletteToolTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="coloruser", password="testpass123")

    def test_color_palette_requires_login(self):
        response = self.client.get(reverse("color_palette_tool"))
        self.assertEqual(response.status_code, 302)

    def test_color_palette_page_loads_for_logged_in_user(self):
        self.client.login(username="coloruser", password="testpass123")
        response = self.client.get(reverse("color_palette_tool"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Color Palette Tool")
        self.assertContains(response, "color_palette_tool.css")
        self.assertContains(response, "color_palette_tool.js")

class RoadmapAchievementAndServerStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="roadmap_user", password="testpass123")
        self.staff = get_user_model().objects.create_user(username="roadmap_admin", password="testpass123", is_staff=True)

    def test_roadmap_requires_login(self):
        response = self.client.get(reverse("roadmap"))
        self.assertEqual(response.status_code, 302)

    def test_roadmap_creates_idea_and_toggles_vote(self):
        self.client.login(username="roadmap_user", password="testpass123")
        response = self.client.post(reverse("roadmap"), {
            "action": "create",
            "title": "Push Benachrichtigungen",
            "description": "PWA Push für Spiel-Einladungen und Chat.",
            "category": FeatureIdea.CATEGORY_TOOL,
            "priority": FeatureIdea.PRIORITY_HIGH,
        })

        self.assertRedirects(response, reverse("roadmap"))
        idea = FeatureIdea.objects.get(title="Push Benachrichtigungen")
        self.assertEqual(idea.author, self.user)
        self.assertEqual(idea.status, FeatureIdea.STATUS_SUGGESTED)

        vote_response = self.client.post(reverse("roadmap"), {"action": "vote", "idea_id": idea.id})
        self.assertRedirects(vote_response, reverse("roadmap"))
        self.assertTrue(FeatureVote.objects.filter(idea=idea, user=self.user).exists())

        unvote_response = self.client.post(reverse("roadmap"), {"action": "vote", "idea_id": idea.id})
        self.assertRedirects(unvote_response, reverse("roadmap"))
        self.assertFalse(FeatureVote.objects.filter(idea=idea, user=self.user).exists())

    def test_roadmap_comments_and_staff_status_update(self):
        idea = FeatureIdea.objects.create(author=self.user, title="Serverstatus", description="Admin Monitor")
        self.client.login(username="roadmap_user", password="testpass123")

        comment_response = self.client.post(reverse("roadmap"), {
            "action": "comment",
            "idea_id": idea.id,
            "text": "Wäre sehr nützlich.",
        })

        self.assertRedirects(comment_response, reverse("roadmap"))
        self.assertTrue(FeatureComment.objects.filter(idea=idea, user=self.user, text="Wäre sehr nützlich.").exists())

        self.client.logout()
        self.client.login(username="roadmap_admin", password="testpass123")
        status_response = self.client.post(reverse("roadmap"), {
            "action": "update_status",
            "idea_id": idea.id,
            "status": FeatureIdea.STATUS_IN_PROGRESS,
            "admin_note": "Wird umgesetzt.",
        })

        self.assertRedirects(status_response, reverse("roadmap"))
        idea.refresh_from_db()
        self.assertEqual(idea.status, FeatureIdea.STATUS_IN_PROGRESS)
        self.assertEqual(idea.admin_note, "Wird umgesetzt.")

    def test_achievement_center_renders_with_user_progress(self):
        self.client.login(username="roadmap_user", password="testpass123")
        Game2048HighScore.objects.create(
            user=self.user,
            score=5000,
            best_tile=1024,
            moves=120,
            duration_seconds=180,
            games_played=3,
        )

        response = self.client.get(reverse("achievement_center"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Achievement-Center")
        self.assertContains(response, "1024-Kachel")
        self.assertContains(response, "XP-Ranking")

    def test_server_status_requires_staff(self):
        self.client.login(username="roadmap_user", password="testpass123")
        response = self.client.get(reverse("server_status"))
        self.assertEqual(response.status_code, 302)

    def test_server_status_renders_for_staff(self):
        self.client.login(username="roadmap_admin", password="testpass123")
        response = self.client.get(reverse("server_status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Serverstatus")
        self.assertContains(response, "Datenbank")
        self.assertContains(response, "Speicherplatz")

