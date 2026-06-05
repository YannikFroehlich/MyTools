import json
import shutil
import tempfile
from unittest.mock import Mock, patch

import requests

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import pre_save
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.forms import NoteForm
from app.models import (
    AvatarCharacter,
    BattleshipGame,
    BattleshipInvite,
    ConnectFourGame,
    DrawingGameLobby,
    DrawingGamePlayer,
    FileShare,
    Friendship,
    HomeLayoutPreference,
    HomeWidget,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    HangmanLobby,
    HangmanPlayer,
    KniffelGame,
    KniffelInvite,
    KniffelPlayer,
    Note,
    Shortcut,
    ShortcutSection,
    StadtLandFlussLobby,
    StadtLandFlussPlayer,
    TicTacToeGame,
    TicTacToeInvite,
    UnoGame,
    UnoPlayer,
    UserProfile,
    WeatherLocation,
)
from app.notification_utils import get_notification_counts


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaseTestCase(TestCase):
    user_scoped_models = (
        AvatarCharacter,
        HomeWidget,
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
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="testpass-123",
        )
        self.client.force_login(self.user)
        self._connect_user_signal()

    def tearDown(self):
        self._disconnect_user_signal()
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
        return SimpleUploadedFile(
            name,
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde"
                b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01"
                b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

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


class MediaThumbnailTests(BaseTestCase):
    def test_media_thumbnail_creates_cached_preview_without_login(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)
        self.client.logout()

        response = self.client.get(reverse("media_thumbnail", args=["avatar-small", profile.avatar.name]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=31536000", response["Cache-Control"])
        self.assertTrue(response.streaming)

    def test_media_thumbnail_rejects_unknown_spec(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar.save("avatar.bmp", self.get_large_test_image("avatar.bmp"), save=True)

        response = self.client.get(reverse("media_thumbnail", args=["unknown", profile.avatar.name]))

        self.assertEqual(response.status_code, 404)


class AuthViewTests(BaseTestCase):
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


class ProfileViewTests(BaseTestCase):
    def test_profile_page_loads_and_creates_profile(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/profile.html")
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

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

    def test_profile_post_keeps_existing_banner_without_new_upload(self):
        profile = UserProfile.objects.create(
            user=self.user,
            profile_banner=self.get_test_image("banner.png"),
        )
        original_banner_name = profile.profile_banner.name

        response = self.client.post(reverse("profile"), {
            "username": self.user.username,
            "first_name": "",
            "last_name": "",
            "email": "",
            "bio": "Banner bleibt",
        })

        self.assertRedirects(response, reverse("profile"))

        profile.refresh_from_db()
        self.assertEqual(profile.profile_banner.name, original_banner_name)

    def test_profile_banner_rejects_files_larger_than_five_mb(self):
        response = self.client.post(reverse("profile"), {
            "username": self.user.username,
            "first_name": "",
            "last_name": "",
            "email": "",
            "bio": "",
            "profile_banner": self.get_large_test_image(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "profile_banner",
            "Das Profilbanner darf maximal 5 MB groß sein.",
        )

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


class HomeViewTests(BaseTestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/home.html")
        self.assertIn("sections", response.context)
        self.assertIn("home_labels", response.context)

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

        response = self.client.post(reverse("home"), {
            "action": "delete_section",
            "section_id": section.id,
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(ShortcutSection.objects.filter(id=section.id).exists())

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


class StaticPageTests(BaseTestCase):
    def test_about_page_loads(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/about.html")

    def test_simple_tool_pages_load(self):
        pages = [
            ("obs-dashboard", "app/obs-dashboard.html"),
            ("spritkostenrechner", "app/spritkostenrechner.html"),
            ("human-benchmark", "app/human_benchmark.html"),
            ("genius-search", "app/genius_search.html"),
            ("avatar-wiki", "app/avatar_wiki.html"),
            ("unit_converter", "app/unit_converter.html"),
            ("drift-circuit", "app/drift_circuit.html"),
            ("stream-deck", "app/stream_deck.html"),
        ]

        for url_name, template in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)


class WeatherViewTests(BaseTestCase):
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
    def test_weather_page_uses_default_city(self, mock_get, mock_get_env_value):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response(),
        ]

        response = self.client.get(reverse("weather"))

        self.assertEqual(response.status_code, 200)

        first_called_url = mock_get.call_args_list[0][0][0]

        self.assertIn("q=Berlin", first_called_url)

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

        first_called_url = mock_get.call_args_list[0][0][0]

        self.assertIn("lat=52.52", first_called_url)
        self.assertIn("lon=13.405", first_called_url)

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
        self.assertTrue(WeatherLocation.objects.filter(name="Osnabrück").exists())

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

    def test_delete_note_requires_post_and_deletes_note(self):
        note = Note.objects.create(title="Weg")

        get_response = self.client.get(reverse("note_delete", args=[note.id]))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("note_delete", args=[note.id]))

        self.assertRedirects(post_response, reverse("notes"))
        self.assertFalse(Note.objects.filter(id=note.id).exists())

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
