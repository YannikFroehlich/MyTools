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

from app.forms import NoteForm
from app.models import (
    AvatarCharacter,
    HomeLayoutPreference,
    HomeWidget,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    Note,
    Shortcut,
    ShortcutSection,
    UserProfile,
    WeatherLocation,
)


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

    def test_users_page_uses_profile_banner_as_card_background(self):
        other_user = get_user_model().objects.create_user(
            username="bannerlistuser",
            password="testpass-123",
        )
        UserProfile.objects.create(
            user=other_user,
            profile_banner=self.get_test_image("list-banner.png"),
        )

        response = self.client.get(reverse("users"))

        self.assertContains(response, "has-profile-banner")
        self.assertContains(response, "profile_banners/list-banner")

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
        self.assertTrue(UserProfile.objects.filter(user=other_user).exists())

    def test_public_profile_uses_profile_banner(self):
        other_user = get_user_model().objects.create_user(
            username="banneruser",
            password="testpass-123",
        )
        UserProfile.objects.create(
            user=other_user,
            profile_banner=self.get_test_image("profile-banner.png"),
        )

        response = self.client.get(reverse("public_profile", args=[other_user.id]))

        self.assertContains(response, "has-profile-banner")
        self.assertContains(response, "profile_banners/profile-banner")

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
