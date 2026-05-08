from unittest.mock import patch, Mock

from django.test import TestCase
from django.urls import reverse

from app.models import Shortcut, ShortcutSection


class ShortcutModelTests(TestCase):
    def test_shortcut_section_str_returns_name(self):
        section = ShortcutSection.objects.create(name="Server")

        self.assertEqual(str(section), "Server")

    def test_shortcut_str_returns_name(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="GitHub",
            url="https://github.com",
            icon="fa-brands fa-github"
        )

        self.assertEqual(str(shortcut), "GitHub")

    def test_shortcut_belongs_to_section(self):
        section = ShortcutSection.objects.create(name="Verknüpfungen")
        shortcut = Shortcut.objects.create(
            section=section,
            name="YouTube",
            url="https://youtube.com",
            icon="fa-brands fa-youtube"
        )

        self.assertEqual(shortcut.section, section)
        self.assertIn(shortcut, section.shortcuts.all())


class HomeViewTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/home.html")

    def test_home_creates_default_section(self):
        self.assertFalse(
            ShortcutSection.objects.filter(name="Verknüpfungen").exists()
        )

        self.client.get(reverse("home"))

        self.assertTrue(
            ShortcutSection.objects.filter(name="Verknüpfungen").exists()
        )

    def test_old_shortcuts_without_section_are_moved_to_default_section(self):
        shortcut = Shortcut.objects.create(
            section=None,
            name="Altes Tool",
            url="https://example.com",
            icon="fa-solid fa-link"
        )

        self.client.get(reverse("home"))

        shortcut.refresh_from_db()

        self.assertIsNotNone(shortcut.section)
        self.assertEqual(shortcut.section.name, "Verknüpfungen")

    def test_add_section(self):
        response = self.client.post(reverse("home"), {
            "action": "add_section",
            "section_name": "Server"
        })

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(
            ShortcutSection.objects.filter(name="Server").exists()
        )

    def test_add_empty_section_does_not_create_section(self):
        response = self.client.post(reverse("home"), {
            "action": "add_section",
            "section_name": ""
        })

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(ShortcutSection.objects.count(), 1)
        self.assertTrue(
            ShortcutSection.objects.filter(name="Verknüpfungen").exists()
        )

    def test_delete_section(self):
        section = ShortcutSection.objects.create(name="Server")

        response = self.client.post(reverse("home"), {
            "action": "delete_section",
            "section_id": section.id
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(
            ShortcutSection.objects.filter(id=section.id).exists()
        )

    def test_default_section_cannot_be_deleted(self):
        default_section = ShortcutSection.objects.create(name="Verknüpfungen")

        response = self.client.post(reverse("home"), {
            "action": "delete_section",
            "section_id": default_section.id
        })

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(
            ShortcutSection.objects.filter(id=default_section.id).exists()
        )

    def test_add_shortcut(self):
        section = ShortcutSection.objects.create(name="Coding")

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "GitHub",
            "url": "github.com",
            "icon": "fa-brands fa-github",
            "custom_icon": ""
        })

        self.assertRedirects(response, reverse("home"))

        shortcut = Shortcut.objects.get(name="GitHub")

        self.assertEqual(shortcut.section, section)
        self.assertEqual(shortcut.url, "https://github.com")
        self.assertEqual(shortcut.icon, "fa-brands fa-github")

    def test_add_shortcut_with_custom_icon_overwrites_selected_icon(self):
        section = ShortcutSection.objects.create(name="Server")

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "CasaOS",
            "url": "https://casaos.io",
            "icon": "fa-solid fa-link",
            "custom_icon": "fa-solid fa-server"
        })

        self.assertRedirects(response, reverse("home"))

        shortcut = Shortcut.objects.get(name="CasaOS")

        self.assertEqual(shortcut.icon, "fa-solid fa-server")

    def test_add_shortcut_without_icon_uses_default_icon(self):
        section = ShortcutSection.objects.create(name="Sonstiges")

        response = self.client.post(reverse("home"), {
            "action": "add_shortcut",
            "section_id": section.id,
            "name": "Example",
            "url": "example.com",
            "icon": "",
            "custom_icon": ""
        })

        self.assertRedirects(response, reverse("home"))

        shortcut = Shortcut.objects.get(name="Example")

        self.assertEqual(shortcut.icon, "fa-solid fa-link")

    def test_delete_shortcut(self):
        section = ShortcutSection.objects.create(name="Coding")
        shortcut = Shortcut.objects.create(
            section=section,
            name="Django",
            url="https://www.djangoproject.com",
            icon="fa-solid fa-code"
        )

        response = self.client.post(reverse("home"), {
            "action": "delete_shortcut",
            "shortcut_id": shortcut.id
        })

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(
            Shortcut.objects.filter(id=shortcut.id).exists()
        )


class AboutViewTests(TestCase):
    def test_about_page_loads(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/about.html")


class WeatherViewTests(TestCase):
    def mocked_current_weather_response(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "name": "Berlin",
            "timezone": 3600,
            "sys": {
                "country": "DE",
                "sunrise": 1715148000,
                "sunset": 1715202000
            },
            "main": {
                "temp": 18.4,
                "humidity": 61,
                "pressure": 1014
            },
            "weather": [
                {
                    "description": "klarer Himmel",
                    "icon": "01d"
                }
            ],
            "wind": {
                "speed": 3.2
            }
        }
        return response

    def mocked_forecast_response(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "list": [
                {
                    "dt": 1715155200,
                    "dt_txt": "2024-05-08 12:00:00",
                    "main": {
                        "temp": 19.1
                    },
                    "weather": [
                        {
                            "description": "leicht bewölkt",
                            "icon": "02d"
                        }
                    ],
                    "pop": 0.2
                },
                {
                    "dt": 1715166000,
                    "dt_txt": "2024-05-08 15:00:00",
                    "main": {
                        "temp": 20.2
                    },
                    "weather": [
                        {
                            "description": "leicht bewölkt",
                            "icon": "02d"
                        }
                    ],
                    "pop": 0.1
                },
                {
                    "dt": 1715241600,
                    "dt_txt": "2024-05-09 12:00:00",
                    "main": {
                        "temp": 21.5
                    },
                    "weather": [
                        {
                            "description": "sonnig",
                            "icon": "01d"
                        }
                    ],
                    "pop": 0
                },
                {
                    "dt": 1715328000,
                    "dt_txt": "2024-05-10 12:00:00",
                    "main": {
                        "temp": 17.8
                    },
                    "weather": [
                        {
                            "description": "Regen",
                            "icon": "10d"
                        }
                    ],
                    "pop": 0.8
                },
                {
                    "dt": 1715414400,
                    "dt_txt": "2024-05-11 12:00:00",
                    "main": {
                        "temp": 16.6
                    },
                    "weather": [
                        {
                            "description": "bewölkt",
                            "icon": "03d"
                        }
                    ],
                    "pop": 0.4
                },
                {
                    "dt": 1715500800,
                    "dt_txt": "2024-05-12 12:00:00",
                    "main": {
                        "temp": 22.0
                    },
                    "weather": [
                        {
                            "description": "sonnig",
                            "icon": "01d"
                        }
                    ],
                    "pop": 0
                }
            ]
        }
        return response

    @patch("app.views.requests.get")
    def test_weather_page_loads_with_api_data(self, mock_get):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response()
        ]

        response = self.client.get(reverse("weather"), {
            "city": "Berlin"
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

        self.assertIn("sunrise", response.context)
        self.assertIn("sunset", response.context)

        self.assertEqual(len(response.context["forecast"]), 5)
        self.assertEqual(len(response.context["hourly_forecast"]), 6)

    @patch("app.views.requests.get")
    def test_weather_page_uses_default_city(self, mock_get):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response()
        ]

        response = self.client.get(reverse("weather"))

        self.assertEqual(response.status_code, 200)

        first_called_url = mock_get.call_args_list[0][0][0]

        self.assertIn("q=Berlin", first_called_url)

    @patch("app.views.requests.get")
    def test_weather_page_can_use_lat_lon(self, mock_get):
        mock_get.side_effect = [
            self.mocked_current_weather_response(),
            self.mocked_forecast_response()
        ]

        response = self.client.get(reverse("weather"), {
            "lat": "52.52",
            "lon": "13.405"
        })

        self.assertEqual(response.status_code, 200)

        first_called_url = mock_get.call_args_list[0][0][0]

        self.assertIn("lat=52.52", first_called_url)
        self.assertIn("lon=13.405", first_called_url)

    @patch("app.views.requests.get")
    def test_weather_page_handles_city_not_found(self, mock_get):
        response_mock = Mock()
        response_mock.status_code = 404
        response_mock.json.return_value = {
            "message": "city not found"
        }

        mock_get.return_value = response_mock

        response = self.client.get(reverse("weather"), {
            "city": "UnbekannteStadt"
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], "Standort nicht gefunden.")

    @patch("app.views.requests.get")
    def test_weather_page_handles_connection_error(self, mock_get):
        mock_get.side_effect = Exception("API nicht erreichbar")

        response = self.client.get(reverse("weather"), {
            "city": "Berlin"
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("Verbindungsfehler", response.context["error"])
        self.assertIn("API nicht erreichbar", response.context["error"])