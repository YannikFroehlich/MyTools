import os
from collections import defaultdict
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
import requests
from django.conf import settings
from django.utils import translation
from django.utils.formats import date_format
from datetime import datetime, timezone
from django.utils.translation import gettext as _

from dotenv import dotenv_values, load_dotenv

from app.models import AvatarCharacter, ClockSettings, ClockTimerPreset, ClockWorldCity, HomeLayoutPreference, HomeWidget, HumanBenchmarkHighScore, HumanBenchmarkScore, Shortcut, \
    ShortcutSection, WeatherLocation

import json

from django.db.models import Max, Prefetch
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Note
from .forms import NoteForm, SignUpForm

from django.views.decorators.csrf import ensure_csrf_cookie

env_path = settings.BASE_DIR / ".env"
load_dotenv(env_path)


def get_env_value(name):
    return os.getenv(name) or dotenv_values(env_path).get(name)


def missing_env_message(name):
    return _("%(name)s fehlt in der .env.") % {"name": name}


def api_error_response(message, status=400):
    return JsonResponse({
        "status": "error",
        "message": message,
    }, status=status)


CLOCK_TIMEZONE_CHOICES = [
    ("Europe/Berlin", "Berlin / Deutschland"),
    ("Europe/London", "London / Großbritannien"),
    ("Europe/Paris", "Paris / Frankreich"),
    ("Europe/Madrid", "Madrid / Spanien"),
    ("Europe/Rome", "Rom / Italien"),
    ("Europe/Istanbul", "Istanbul / Türkei"),
    ("America/New_York", "New York / USA"),
    ("America/Chicago", "Chicago / USA"),
    ("America/Denver", "Denver / USA"),
    ("America/Los_Angeles", "Los Angeles / USA"),
    ("America/Sao_Paulo", "São Paulo / Brasilien"),
    ("Asia/Dubai", "Dubai / VAE"),
    ("Asia/Kolkata", "Mumbai / Indien"),
    ("Asia/Bangkok", "Bangkok / Thailand"),
    ("Asia/Shanghai", "Shanghai / China"),
    ("Asia/Tokyo", "Tokio / Japan"),
    ("Asia/Seoul", "Seoul / Südkorea"),
    ("Australia/Sydney", "Sydney / Australien"),
    ("Pacific/Auckland", "Auckland / Neuseeland"),
    ("UTC", "UTC"),
]


@login_required
def clock_view(request):
    settings_obj, created = ClockSettings.objects.get_or_create(user=request.user)
    valid_timezones = {timezone for timezone, label in CLOCK_TIMEZONE_CHOICES}
    valid_ringtones = {choice[0] for choice in ClockSettings.RINGTONE_CHOICES}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_world_city":
            label = request.POST.get("label", "").strip()
            timezone_name = request.POST.get("timezone", "").strip()

            if not label and timezone_name in valid_timezones:
                label = dict(CLOCK_TIMEZONE_CHOICES).get(timezone_name, timezone_name)

            if label and timezone_name in valid_timezones:
                max_order = ClockWorldCity.objects.filter(user=request.user).aggregate(Max("order"))["order__max"] or 0
                ClockWorldCity.objects.create(
                    user=request.user,
                    label=label[:80],
                    timezone=timezone_name,
                    order=max_order + 1,
                )
                messages.success(request, _("Weltuhr-Ort wurde hinzugefügt."))
            else:
                messages.error(request, _("Bitte wähle einen gültigen Ort aus."))

            return redirect("clock")

        if action == "delete_world_city":
            city_id = request.POST.get("city_id")
            ClockWorldCity.objects.filter(id=city_id, user=request.user).delete()
            messages.success(request, _("Weltuhr-Ort wurde gelöscht."))
            return redirect("clock")

        if action == "add_timer_preset":
            name = request.POST.get("timer_name", "").strip()
            try:
                hours = max(0, min(int(request.POST.get("hours") or 0), 23))
                minutes = max(0, min(int(request.POST.get("minutes") or 0), 59))
                seconds = max(0, min(int(request.POST.get("seconds") or 0), 59))
            except ValueError:
                hours, minutes, seconds = 0, 0, 0

            total_seconds = (hours * 3600) + (minutes * 60) + seconds

            if name and total_seconds > 0:
                max_order = ClockTimerPreset.objects.filter(user=request.user).aggregate(Max("order"))["order__max"] or 0
                ClockTimerPreset.objects.create(
                    user=request.user,
                    name=name[:80],
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                    order=max_order + 1,
                )
                messages.success(request, _("Timer wurde gespeichert."))
            else:
                messages.error(request, _("Bitte gib einen Namen und eine Dauer größer als 0 Sekunden ein."))

            return redirect("clock")

        if action == "delete_timer_preset":
            timer_id = request.POST.get("timer_id")
            ClockTimerPreset.objects.filter(id=timer_id, user=request.user).delete()
            messages.success(request, _("Timer wurde gelöscht."))
            return redirect("clock")

        if action == "update_clock_settings":
            try:
                volume = int(request.POST.get("volume") or 80)
            except ValueError:
                volume = 80

            ringtone = request.POST.get("ringtone", ClockSettings.RINGTONE_BELL).strip()
            uploaded_sound = request.FILES.get("custom_sound")

            settings_obj.volume = max(0, min(volume, 100))
            if ringtone in valid_ringtones:
                settings_obj.ringtone = ringtone

            if uploaded_sound:
                if uploaded_sound.size > 5 * 1024 * 1024:
                    messages.error(request, _("Der eigene Klingelton darf maximal 5 MB groß sein."))
                    return redirect("clock")

                content_type = getattr(uploaded_sound, "content_type", "") or ""
                if content_type and not content_type.startswith("audio/"):
                    messages.error(request, _("Bitte lade eine Audio-Datei hoch."))
                    return redirect("clock")

                settings_obj.custom_sound = uploaded_sound
                settings_obj.ringtone = ClockSettings.RINGTONE_CUSTOM

            settings_obj.save()
            messages.success(request, _("Uhr-Einstellungen wurden gespeichert."))
            return redirect("clock")

        if action == "remove_custom_sound":
            if settings_obj.custom_sound:
                settings_obj.custom_sound.delete(save=False)
                settings_obj.custom_sound = None
                if settings_obj.ringtone == ClockSettings.RINGTONE_CUSTOM:
                    settings_obj.ringtone = ClockSettings.RINGTONE_BELL
                settings_obj.save()
                messages.success(request, _("Eigener Klingelton wurde gelöscht."))
            return redirect("clock")

    if not ClockWorldCity.objects.filter(user=request.user).exists():
        ClockWorldCity.objects.bulk_create([
            ClockWorldCity(user=request.user, label="Berlin", timezone="Europe/Berlin", order=1),
            ClockWorldCity(user=request.user, label="New York", timezone="America/New_York", order=2),
            ClockWorldCity(user=request.user, label="Tokio", timezone="Asia/Tokyo", order=3),
        ])

    context = {
        "world_cities": ClockWorldCity.objects.filter(user=request.user),
        "timer_presets": ClockTimerPreset.objects.filter(user=request.user),
        "clock_settings": settings_obj,
        "timezone_choices": CLOCK_TIMEZONE_CHOICES,
        "ringtone_choices": ClockSettings.RINGTONE_CHOICES,
    }
    return render(request, "app/clock.html", context)


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _("Dein Account wurde erstellt."))
            return redirect("home")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {
        "form": form,
    })



def get_home_weather_data(request, user, widget):
    api_key = get_env_value("OPENWEATHER_API_KEY")
    units = request.GET.get("units", "metric")
    if units not in {"metric", "imperial"}:
        units = "metric"

    location = widget.weather_location or WeatherLocation.objects.filter(user=user).first()
    city = location.name if location else "Berlin"
    current_lang = translation.get_language()
    temperature_unit = "°F" if units == "imperial" else "°C"

    if not api_key:
        return {
            "city": city,
            "temperature_unit": temperature_unit,
            "error": missing_env_message("OPENWEATHER_API_KEY"),
        }

    try:
        params = {
            "q": city,
            "appid": api_key,
            "units": units,
            "lang": current_lang,
        }
        response = requests.get(
            "http://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=6,
        )
        data = response.json()

        if response.status_code != 200:
            return {
                "city": city,
                "temperature_unit": temperature_unit,
                "error": data.get("message") or _("Wetter konnte nicht geladen werden."),
            }

        weather_info = (data.get("weather") or [{}])[0]
        main_info = data.get("main") or {}
        wind_info = data.get("wind") or {}

        return {
            "city": data.get("name") or city,
            "temperature": round(main_info.get("temp", 0)),
            "feels_like": round(main_info.get("feels_like", 0)),
            "description": weather_info.get("description", _("Keine Beschreibung")),
            "icon": weather_info.get("icon"),
            "humidity": main_info.get("humidity"),
            "wind": round(wind_info.get("speed", 0), 1),
            "temperature_unit": temperature_unit,
            "wind_unit": "mph" if units == "imperial" else "m/s",
            "url": f"{request.path.rstrip('/')}/weather/" if False else None,
        }
    except (requests.RequestException, ValueError):
        return {
            "city": city,
            "temperature_unit": temperature_unit,
            "error": _("Wetter konnte nicht geladen werden."),
        }


def build_home_widget_data(request, user):
    widgets = list(
        HomeWidget.objects
        .filter(user=user, is_enabled=True)
        .select_related("weather_location")
        .order_by("order", "created_at")
    )

    note_count = Note.objects.filter(user=user, is_archived=False).count()
    pinned_notes = Note.objects.filter(user=user, is_archived=False, is_pinned=True).order_by("-updated_at")[:3]

    benchmark_highscores = {
        highscore.game: highscore
        for highscore in HumanBenchmarkHighScore.objects.filter(user=user)
    }
    benchmark_rows = [
        {
            "key": game_key,
            "name": game_name,
            "highscore": benchmark_highscores.get(game_key),
        }
        for game_key, game_name in HumanBenchmarkScore.GAME_CHOICES
    ]

    shortcut_count = Shortcut.objects.filter(user=user).count()
    section_count = ShortcutSection.objects.filter(user=user).count()
    weather_location_count = WeatherLocation.objects.filter(user=user).count()

    widget_context = []

    for widget in widgets:
        data = {}

        if widget.widget_type == HomeWidget.WIDGET_WEATHER:
            data = get_home_weather_data(request, user, widget)

        elif widget.widget_type == HomeWidget.WIDGET_NOTES:
            data = {
                "note_count": note_count,
                "pinned_notes": pinned_notes,
            }

        elif widget.widget_type == HomeWidget.WIDGET_BENCHMARK:
            data = {
                "rows": benchmark_rows,
            }

        elif widget.widget_type == HomeWidget.WIDGET_CLOCK:
            data = {}

        elif widget.widget_type == HomeWidget.WIDGET_STATS:
            data = {
                "shortcut_count": shortcut_count,
                "section_count": section_count,
                "note_count": note_count,
                "weather_location_count": weather_location_count,
            }

        widget_context.append({
            "widget": widget,
            "data": data,
        })

    return widget_context


def home(request):
    user = request.user
    home_labels = {
        "newShortcut": _("Neue Verknüpfung"),
        "shortcutForSection": _("für \"%(section)s\""),
        "editShortcut": _("Verknüpfung bearbeiten"),
        "shortcutInSection": _("in \"%(section)s\""),
        "newSection": _("Neuer Bereich"),
        "createSection": _("Bereich erstellen"),
        "editSection": _("Bereich bearbeiten"),
        "saveChanges": _("Änderungen speichern"),
        "noFileSelected": _("Keine Datei ausgewählt"),
        "newWidget": _("Neues Widget"),
        "editWidget": _("Widget bearbeiten"),
        "addWidget": _("Widget hinzufügen"),
        "saveWidget": _("Widget speichern"),
    }

    default_section, created = ShortcutSection.objects.get_or_create(
        user=user,
        name="Verknüpfungen",
        defaults={
            "color": "blue",
            "order": 0
        }
    )

    Shortcut.objects.filter(user=user, section__isnull=True).update(section=default_section)

    if request.method == "POST":
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"success": False, "error": _("Ungültiges JSON")}, status=400)

            action = data.get("action")

            if action == "update_shortcut_order":
                shortcuts = data.get("shortcuts", [])

                for item in shortcuts:
                    shortcut_id = item.get("id")
                    section_id = item.get("section_id")
                    order = item.get("order", 0)

                    if section_id and not ShortcutSection.objects.filter(id=section_id, user=user).exists():
                        continue

                    Shortcut.objects.filter(id=shortcut_id, user=user).update(
                        section_id=section_id,
                        order=order
                    )

                return JsonResponse({"success": True})

            if action == "update_section_order":
                sections = data.get("sections", [])

                for item in sections:
                    section_id = item.get("id")
                    order = item.get("order", 0)

                    ShortcutSection.objects.filter(
                        id=section_id,
                        user=user,
                    ).exclude(name="Verknüpfungen").update(order=order)

                ShortcutSection.objects.filter(id=default_section.id, user=user).update(order=0)

                return JsonResponse({"success": True})

            if action == "update_home_layout_order":
                items = data.get("items", [])
                layout_preference, layout_created = HomeLayoutPreference.objects.get_or_create(user=user)

                for item in items:
                    item_type = item.get("type")
                    order = item.get("order", 1)

                    if item_type == "widgets":
                        layout_preference.widget_area_order = order
                        continue

                    if item_type == "section":
                        section_id = item.get("id")
                        ShortcutSection.objects.filter(
                            id=section_id,
                            user=user,
                        ).exclude(name="Verknüpfungen").update(order=order)

                layout_preference.save(update_fields=["widget_area_order", "updated_at"])
                ShortcutSection.objects.filter(id=default_section.id, user=user).update(order=0)

                return JsonResponse({"success": True})

            if action == "update_widget_order":
                widgets = data.get("widgets", [])

                for item in widgets:
                    widget_id = item.get("id")
                    order = item.get("order", 0)

                    HomeWidget.objects.filter(id=widget_id, user=user).update(order=order)

                return JsonResponse({"success": True})

            return JsonResponse({"success": False, "error": _("Unbekannte Aktion")}, status=400)

        action = request.POST.get("action")

        if action == "add_widget":
            title = request.POST.get("widget_title", "").strip()
            widget_type = request.POST.get("widget_type", HomeWidget.WIDGET_WEATHER).strip()
            widget_color = request.POST.get("widget_color", "blue").strip()
            weather_location_id = request.POST.get("weather_location") or None
            clock_design = request.POST.get("clock_design", HomeWidget.CLOCK_DESIGN_MINIMAL).strip()
            clock_style = request.POST.get("clock_style", HomeWidget.CLOCK_STYLE_CLASSIC).strip()

            valid_widget_types = {choice[0] for choice in HomeWidget.WIDGET_CHOICES}
            valid_colors = {choice[0] for choice in HomeWidget.COLOR_CHOICES}
            valid_clock_designs = {choice[0] for choice in HomeWidget.CLOCK_DESIGN_CHOICES}
            valid_clock_styles = {choice[0] for choice in HomeWidget.CLOCK_STYLE_CHOICES}

            if widget_type not in valid_widget_types:
                widget_type = HomeWidget.WIDGET_WEATHER

            if widget_color not in valid_colors:
                widget_color = "blue"

            if clock_design not in valid_clock_designs:
                clock_design = HomeWidget.CLOCK_DESIGN_MINIMAL

            if clock_style not in valid_clock_styles:
                clock_style = HomeWidget.CLOCK_STYLE_CLASSIC

            if not title:
                title = dict(HomeWidget.WIDGET_CHOICES).get(widget_type, _("Widget"))

            max_order = HomeWidget.objects.filter(user=user).aggregate(Max("order"))["order__max"] or 0

            weather_location = None
            if weather_location_id:
                weather_location = WeatherLocation.objects.filter(id=weather_location_id, user=user).first()

            HomeWidget.objects.create(
                user=user,
                title=title,
                widget_type=widget_type,
                color=widget_color,
                weather_location=weather_location,
                weather_design=HomeWidget.WEATHER_DESIGN_CLEAN,
                weather_style=HomeWidget.WEATHER_STYLE_CLASSIC,
                clock_design=clock_design,
                clock_style=clock_style,
                order=max_order + 1,
            )

            return redirect("home")

        if action == "edit_widget":
            widget_id = request.POST.get("widget_id")
            title = request.POST.get("widget_title", "").strip()
            widget_type = request.POST.get("widget_type", HomeWidget.WIDGET_WEATHER).strip()
            widget_color = request.POST.get("widget_color", "blue").strip()
            weather_location_id = request.POST.get("weather_location") or None
            clock_design = request.POST.get("clock_design", HomeWidget.CLOCK_DESIGN_MINIMAL).strip()
            clock_style = request.POST.get("clock_style", HomeWidget.CLOCK_STYLE_CLASSIC).strip()

            widget = get_object_or_404(HomeWidget, id=widget_id, user=user)
            valid_widget_types = {choice[0] for choice in HomeWidget.WIDGET_CHOICES}
            valid_colors = {choice[0] for choice in HomeWidget.COLOR_CHOICES}
            valid_clock_designs = {choice[0] for choice in HomeWidget.CLOCK_DESIGN_CHOICES}
            valid_clock_styles = {choice[0] for choice in HomeWidget.CLOCK_STYLE_CHOICES}

            if widget_type not in valid_widget_types:
                widget_type = HomeWidget.WIDGET_WEATHER

            if widget_color not in valid_colors:
                widget_color = "blue"

            if clock_design not in valid_clock_designs:
                clock_design = HomeWidget.CLOCK_DESIGN_MINIMAL

            if clock_style not in valid_clock_styles:
                clock_style = HomeWidget.CLOCK_STYLE_CLASSIC

            weather_location = None
            if weather_location_id:
                weather_location = WeatherLocation.objects.filter(id=weather_location_id, user=user).first()

            widget.title = title or dict(HomeWidget.WIDGET_CHOICES).get(widget_type, _("Widget"))
            widget.widget_type = widget_type
            widget.color = widget_color
            widget.weather_location = weather_location
            widget.weather_design = HomeWidget.WEATHER_DESIGN_CLEAN
            widget.weather_style = HomeWidget.WEATHER_STYLE_CLASSIC
            widget.clock_design = clock_design
            widget.clock_style = clock_style
            widget.save()

            return redirect("home")

        if action == "delete_widget":
            widget_id = request.POST.get("widget_id")
            widget = get_object_or_404(HomeWidget, id=widget_id, user=user)
            widget.delete()

            return redirect("home")

        if action == "add_section":
            section_name = request.POST.get("section_name", "").strip()
            section_color = request.POST.get("section_color", "blue").strip()

            if section_name:
                layout_preference, layout_created = HomeLayoutPreference.objects.get_or_create(user=user)
                max_section_order = ShortcutSection.objects.filter(user=user).aggregate(Max("order"))["order__max"] or 0
                max_order = max(max_section_order, layout_preference.widget_area_order)

                ShortcutSection.objects.create(
                    user=user,
                    name=section_name,
                    color=section_color,
                    order=max_order + 1
                )

            return redirect("home")

        if action == "edit_section":
            section_id = request.POST.get("section_id")
            section_name = request.POST.get("section_name", "").strip()
            section_color = request.POST.get("section_color", "blue").strip()

            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if section_name:
                if section.name != "Verknüpfungen":
                    section.name = section_name
                section.color = section_color
                section.save()

            return redirect("home")

        if action == "delete_section":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if section.name != "Verknüpfungen":
                section.delete()

            return redirect("home")

        if action == "toggle_section_collapse":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            section.is_collapsed = not section.is_collapsed
            section.save()

            return redirect("home")

        if action == "add_shortcut":
            section_id = request.POST.get("section_id")
            name = request.POST.get("name", "").strip()
            url = request.POST.get("url", "").strip()
            icon = request.POST.get("icon", "").strip()
            custom_icon = request.POST.get("custom_icon", "").strip()
            image = request.FILES.get("image")

            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if custom_icon:
                icon = custom_icon

            if name and url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                max_order = Shortcut.objects.filter(user=user, section=section).aggregate(Max("order"))[
                                "order__max"] or 0

                Shortcut.objects.create(
                    user=user,
                    section=section,
                    name=name,
                    url=url,
                    icon=icon or "fa-solid fa-link",
                    image=image,
                    order=max_order + 1
                )

            return redirect("home")

        if action == "edit_shortcut":
            shortcut_id = request.POST.get("shortcut_id")
            section_id = request.POST.get("section_id")
            name = request.POST.get("name", "").strip()
            url = request.POST.get("url", "").strip()
            icon = request.POST.get("icon", "").strip()
            custom_icon = request.POST.get("custom_icon", "").strip()
            image = request.FILES.get("image")

            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)
            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if custom_icon:
                icon = custom_icon

            if name and url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                shortcut.section = section
                shortcut.name = name
                shortcut.url = url
                shortcut.icon = icon or "fa-solid fa-link"

                if image:
                    shortcut.image = image

                shortcut.save()

            return redirect("home")

        if action == "delete_shortcut":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)
            shortcut.delete()

            return redirect("home")

        if action == "toggle_favorite":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)

            shortcut.is_favorite = not shortcut.is_favorite
            shortcut.save()

            return redirect("home")

    sections = list(
        ShortcutSection.objects
        .filter(user=user)
        .prefetch_related(Prefetch("shortcuts", queryset=Shortcut.objects.filter(user=user)))
        .order_by("order", "created_at")
    )

    default_section = next((section for section in sections if section.name == "Verknüpfungen"), default_section)
    custom_sections = [section for section in sections if section.name != "Verknüpfungen"]

    layout_preference, layout_created = HomeLayoutPreference.objects.get_or_create(user=user)
    home_widgets = build_home_widget_data(request, user)
    weather_locations = WeatherLocation.objects.filter(user=user)

    movable_home_items = [
        {
            "type": "widgets",
            "order": layout_preference.widget_area_order,
        }
    ]

    movable_home_items.extend(
        {
            "type": "section",
            "section": section,
            "order": section.order,
        }
        for section in custom_sections
    )

    movable_home_items.sort(key=lambda item: (item["order"], 0 if item["type"] == "widgets" else 1))

    return render(request, "app/home.html", {
        "sections": sections,
        "default_section": default_section,
        "movable_home_items": movable_home_items,
        "home_widgets": home_widgets,
        "weather_locations": weather_locations,
        "widget_types": [(value, _(label)) for value, label in HomeWidget.WIDGET_CHOICES],
        "widget_colors": [(value, _(label)) for value, label in HomeWidget.COLOR_CHOICES],
        "clock_designs": [(value, _(label)) for value, label in HomeWidget.CLOCK_DESIGN_CHOICES],
        "clock_styles": [(value, _(label)) for value, label in HomeWidget.CLOCK_STYLE_CHOICES],
        "home_labels": home_labels,
    })


def about(request):
    template_name = 'app/about.html'
    return render(request, template_name)


def weather(request):
    user = request.user
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    city = request.GET.get("city", "Berlin")
    units = request.GET.get("units") or request.POST.get("units") or "metric"
    if units not in {"metric", "imperial"}:
        units = "metric"

    temperature_unit = "°F" if units == "imperial" else "°C"
    wind_unit = "mph" if units == "imperial" else "m/s"
    current_lang = translation.get_language()
    api_key = get_env_value("OPENWEATHER_API_KEY")

    def weather_redirect_url(**params):
        if units != "metric":
            params["units"] = units
        return f"{request.path}?{urlencode(params)}"

    def weather_context(**extra):
        context = {
            "city": city,
            "units": units,
            "temperature_unit": temperature_unit,
            "wind_unit": wind_unit,
        }
        context.update(extra)
        return context

    # ───── Gespeicherte Wetter-Orte: Hinzufügen / Löschen ─────
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_weather_location":
            location_name = request.POST.get("location_name", "").strip()

            if location_name:
                max_order = WeatherLocation.objects.filter(user=user).aggregate(Max("order"))["order__max"] or 0

                WeatherLocation.objects.get_or_create(
                    user=user,
                    name=location_name,
                    defaults={
                        "order": max_order + 1
                    }
                )

                return redirect(weather_redirect_url(city=location_name))

            return redirect(request.path)

        if action == "delete_weather_location":
            location_id = request.POST.get("location_id")
            current_city = request.POST.get("current_city", city).strip() or "Berlin"

            if location_id:
                WeatherLocation.objects.filter(id=location_id, user=user).delete()

            return redirect(weather_redirect_url(city=current_city))

        return redirect(request.path)

    saved_locations = WeatherLocation.objects.filter(user=user)

    if not api_key:
        return render(request, 'app/weather.html', weather_context(
            saved_locations=saved_locations,
            error=missing_env_message("OPENWEATHER_API_KEY"),
        ))

    params = f"&appid={api_key}&units={units}&lang={current_lang}"
    location_query = f"lat={lat}&lon={lon}" if lat and lon else f"q={city}"

    try:
        curr_url = f"http://api.openweathermap.org/data/2.5/weather?{location_query}{params}"
        curr_response = requests.get(curr_url, timeout=10)
        curr_data = curr_response.json()

        if not isinstance(curr_data, dict):
            context = {
                'city': city,
                'saved_locations': saved_locations,
                'error': _("Ungültige Antwort der OpenWeather API.")
            }
            context.update(weather_context())
            return render(request, 'app/weather.html', context)

        if curr_response.status_code == 200:
            fore_url = f"http://api.openweathermap.org/data/2.5/forecast?{location_query}{params}"
            fore_response = requests.get(fore_url, timeout=10)
            fore_data = fore_response.json()

            if not isinstance(fore_data, dict):
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("Ungültige Antwort der OpenWeather API.")
                }
                context.update(weather_context())
                return render(request, 'app/weather.html', context)

            if fore_response.status_code != 200:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("Wettervorhersage konnte nicht geladen werden.")
                }
                context.update(weather_context())
                return render(request, 'app/weather.html', context)

            daily_groups = defaultdict(list)

            for item in fore_data.get('list', []):
                date_key = item['dt_txt'].split(' ')[0]
                daily_groups[date_key].append(item)

            # ───── 5 Tage Forecast ─────

            forecast_list = []

            for date_str, items in list(daily_groups.items())[:5]:
                temps = [i['main']['temp'] for i in items]

                midday_item = next(
                    (i for i in items if "12:00:00" in i['dt_txt']),
                    items[0]
                )

                dt_obj = datetime.fromtimestamp(midday_item['dt'])

                forecast_list.append({
                    'day': date_format(dt_obj, "D"),
                    'date': dt_obj.strftime("%d.%m"),
                    'temp_max': round(max(temps), 1),
                    'temp_min': round(min(temps), 1),
                    'description': midday_item['weather'][0]['description'],
                    'icon': midday_item['weather'][0]['icon'],
                    'rain': round(midday_item.get('pop', 0) * 100)
                })

            # ───── Stündliche Vorhersage ─────

            hourly_forecast = []

            for item in fore_data['list'][:8]:
                dt_obj = datetime.fromtimestamp(item['dt'])

                hourly_forecast.append({
                    'time': dt_obj.strftime("%H:%M"),
                    'temp': round(item['main']['temp']),
                    'icon': item['weather'][0]['icon'],
                    'rain': round(item.get('pop', 0) * 100)
                })

            # ───── Sonnenaufgang / Untergang ─────

            timezone_offset = curr_data.get("timezone", 0)

            sunrise = datetime.fromtimestamp(
                curr_data["sys"]["sunrise"] + timezone_offset,
                tz=timezone.utc
            ).strftime("%H:%M")

            sunset = datetime.fromtimestamp(
                curr_data["sys"]["sunset"] + timezone_offset,
                tz=timezone.utc
            ).strftime("%H:%M")

            context = {
                'city': curr_data['name'],
                'country': curr_data['sys']['country'],
                'temperature': round(curr_data['main']['temp'], 1),
                'temperature_unit': temperature_unit,
                'description': curr_data['weather'][0]['description'],
                'icon': curr_data['weather'][0]['icon'],
                'wind_speed': round(curr_data['wind']['speed'], 1),
                'wind_unit': wind_unit,
                'humidity': curr_data['main']['humidity'],
                'pressure': curr_data['main']['pressure'],
                'forecast': forecast_list,
                'hourly_forecast': hourly_forecast,
                'sunrise': sunrise,
                'sunset': sunset,
                'units': units,
                'current_lang': current_lang,
                'saved_locations': saved_locations,
            }

        else:
            api_message = curr_data.get("message")

            if curr_response.status_code == 401:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("OpenWeather API-Key ist ungültig.")
                }
            elif curr_response.status_code == 404:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("Standort nicht gefunden.")
                }
            elif api_message:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("OpenWeather Fehler: %(message)s") % {"message": api_message}
                }
            else:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("Standort nicht gefunden.")
                }

    except requests.RequestException as e:
        context = {
            'city': city,
            'saved_locations': saved_locations,
            'error': _("Verbindungsfehler: %(error)s") % {"error": str(e)}
        }

    except (KeyError, IndexError, TypeError, ValueError):
        context = {
            'city': city,
            'saved_locations': saved_locations,
            'error': _("Ungültige Antwort der OpenWeather API.")
        }

    except Exception as e:
        context = {
            'city': city,
            'saved_locations': saved_locations,
            'error': _("Verbindungsfehler: %(error)s") % {"error": str(e)}
        }

    context.update(weather_context(**context))
    return render(request, 'app/weather.html', context)


def obs_dashboard(request):
    return render(request, "app/obs-dashboard.html")


def spritkostenrechner(request):
    return render(request, "app/spritkostenrechner.html")


HUMAN_BENCHMARK_GAMES = ["reaction", "aim", "typing", "visual"]

HUMAN_BENCHMARK_LOWER_IS_BETTER = {
    "reaction": True,
    "aim": True,
    "typing": False,
    "visual": False,
}

HUMAN_BENCHMARK_GAME_LABELS = {
    "reaction": _("Reaktion"),
    "aim": _("Aim Trainer"),
    "typing": _("Typing Test"),
    "visual": _("Visual Memory"),
}


def is_better_human_benchmark_score(game, new_score, old_score):
    if old_score is None:
        return True

    if HUMAN_BENCHMARK_LOWER_IS_BETTER.get(game, False):
        return new_score < old_score

    return new_score > old_score


def serialize_human_benchmark_score(score):
    score_date = getattr(score, "created_at", None) or getattr(score, "achieved_at", None)

    return {
        "game": score.game,
        "score": score.score,
        "display_score": score.display_score,
        "details": score.details or {},
        "created_at": date_format(score_date, "d.m.Y H:i") if score_date else "",
    }


def get_human_benchmark_score_data(user):
    data = {
        "games": {
            game: {
                "label": str(HUMAN_BENCHMARK_GAME_LABELS.get(game, game)),
                "lower_is_better": HUMAN_BENCHMARK_LOWER_IS_BETTER.get(game, False),
                "recent": [],
                "highscore": None,
                "leaderboard": [],
            }
            for game in HUMAN_BENCHMARK_GAMES
        }
    }

    for game in HUMAN_BENCHMARK_GAMES:
        recent_scores = HumanBenchmarkScore.objects.filter(
            user=user,
            game=game,
        ).order_by("-created_at")[:10]

        highscore = HumanBenchmarkHighScore.objects.filter(
            user=user,
            game=game,
        ).first()

        order_field = "score" if HUMAN_BENCHMARK_LOWER_IS_BETTER.get(game, False) else "-score"

        leaderboard = (
            HumanBenchmarkHighScore.objects
            .filter(game=game)
            .select_related("user")
            .order_by(order_field, "achieved_at")[:10]
        )

        data["games"][game]["recent"] = [
            serialize_human_benchmark_score(score)
            for score in recent_scores
        ]

        data["games"][game]["highscore"] = (
            serialize_human_benchmark_score(highscore)
            if highscore
            else None
        )

        data["games"][game]["leaderboard"] = [
            {
                "rank": index + 1,
                "username": entry.user.get_full_name() or entry.user.username,
                "display_score": entry.display_score,
                "score": entry.score,
                "achieved_at": date_format(entry.achieved_at, "d.m.Y H:i"),
            }
            for index, entry in enumerate(leaderboard)
        ]

    return data


@ensure_csrf_cookie
def human_benchmark(request):
    benchmark_labels = {
        "loading": _("Lade Text..."),
        "translating": _("Übersetze..."),
        "nextTest": _("Nächster Test"),
        "loadingButton": _("Lädt..."),
        "startTest": _("Test starten"),
        "newHighscore": _("Neuer Highscore!"),
        "saved": _("Ergebnis gespeichert."),
        "noResults": _("Noch keine Ergebnisse."),
        "rank": _("Platz"),
        "player": _("Nutzer"),
        "score": _("Score"),
        "date": _("Datum"),
    }

    return render(request, "app/human_benchmark.html", {
        "benchmark_labels": benchmark_labels,
        "score_data": get_human_benchmark_score_data(request.user),
    })


@require_POST
def human_benchmark_score_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungültige Anfrage."), status=400)

    game = payload.get("game")

    if game not in HUMAN_BENCHMARK_GAMES:
        return api_error_response(_("Unbekannter Spielmodus."), status=400)

    try:
        score_value = float(payload.get("score"))
    except (TypeError, ValueError):
        return api_error_response(_("Ungültiger Score."), status=400)

    if score_value < 0:
        return api_error_response(_("Ungültiger Score."), status=400)

    display_score = str(payload.get("display_score") or score_value)[:80]
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}

    score = HumanBenchmarkScore.objects.create(
        user=request.user,
        game=game,
        score=score_value,
        display_score=display_score,
        details=details,
    )

    highscore, created = HumanBenchmarkHighScore.objects.get_or_create(
        user=request.user,
        game=game,
        defaults={
            "score": score_value,
            "display_score": display_score,
            "details": details,
        },
    )

    is_new_highscore = created or is_better_human_benchmark_score(
        game,
        score_value,
        highscore.score,
    )

    if is_new_highscore and not created:
        highscore.score = score_value
        highscore.display_score = display_score
        highscore.details = details
        highscore.save(update_fields=["score", "display_score", "details", "achieved_at"])

    return JsonResponse({
        "status": "ok",
        "new_highscore": is_new_highscore,
        "saved_score": serialize_human_benchmark_score(score),
        "score_data": get_human_benchmark_score_data(request.user),
    })


def genius_search(request):
    return render(request, "app/genius_search.html")


def avatar_wiki(request):
    return render(request, "app/avatar_wiki.html")


def serialize_avatar_character(character):
    return {
        "id": character.id,
        "name": character.name,
        "nation": character.nation,
        "link": character.link,
        "description": character.description,
        "image": character.image.url if character.image else "",
        "order": character.order,
    }


def avatar_characters_api(request):
    user = request.user

    if request.method == "GET":
        try:
            characters = AvatarCharacter.objects.filter(user=user)
            return JsonResponse({
                "status": "ok",
                "characters": [serialize_avatar_character(character) for character in characters],
            })
        except (OperationalError, ProgrammingError):
            return JsonResponse({
                "status": "error",
                "message": _("Datenbanktabelle fehlt. Bitte Migration ausführen: python manage.py migrate")
            }, status=500)

    if request.method == "POST":
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({
                    "status": "error",
                    "message": _("Ungültiges JSON.")
                }, status=400)

            if data.get("action") == "update_order":
                character_ids = data.get("character_ids", [])

                for order, character_id in enumerate(character_ids):
                    AvatarCharacter.objects.filter(id=character_id, user=user).update(order=order)

                return JsonResponse({"status": "ok"})

            return JsonResponse({
                "status": "error",
                "message": _("Unbekannte Aktion.")
            }, status=400)

        name = request.POST.get("name", "").strip()
        nation = request.POST.get("nation", "").strip()
        link = request.POST.get("link", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.FILES.get("image")

        valid_nations = {choice[0] for choice in AvatarCharacter.NATION_CHOICES}

        if not name:
            return JsonResponse({
                "status": "error",
                "message": _("Name fehlt.")
            }, status=400)

        if nation not in valid_nations:
            return JsonResponse({
                "status": "error",
                "message": _("Ungültige Nation.")
            }, status=400)

        if not image:
            return JsonResponse({
                "status": "error",
                "message": _("Bild fehlt.")
            }, status=400)

        try:
            max_order = AvatarCharacter.objects.filter(user=user).aggregate(Max("order"))["order__max"]
            character = AvatarCharacter.objects.create(
                user=user,
                name=name,
                nation=nation,
                link=link,
                description=description,
                image=image,
                order=(max_order + 1) if max_order is not None else 0,
            )
        except (OperationalError, ProgrammingError):
            return JsonResponse({
                "status": "error",
                "message": _("Datenbanktabelle fehlt. Bitte Migration ausführen: python manage.py migrate")
            }, status=500)

        return JsonResponse({
            "status": "ok",
            "character": serialize_avatar_character(character),
        }, status=201)

    return JsonResponse({
        "status": "error",
        "message": _("Methode nicht erlaubt.")
    }, status=405)


def avatar_character_detail_api(request, character_id):
    character = get_object_or_404(AvatarCharacter, id=character_id, user=request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        nation = request.POST.get("nation", "").strip()
        link = request.POST.get("link", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.FILES.get("image")
        valid_nations = {choice[0] for choice in AvatarCharacter.NATION_CHOICES}

        if not name:
            return JsonResponse({
                "status": "error",
                "message": _("Name fehlt.")
            }, status=400)

        if nation not in valid_nations:
            return JsonResponse({
                "status": "error",
                "message": _("Ungültige Nation.")
            }, status=400)

        character.name = name
        character.nation = nation
        character.link = link
        character.description = description

        if image:
            if character.image:
                character.image.delete(save=False)
            character.image = image

        character.save()

        return JsonResponse({
            "status": "ok",
            "character": serialize_avatar_character(character),
        })

    if request.method != "DELETE":
        return JsonResponse({
            "status": "error",
            "message": _("Methode nicht erlaubt.")
        }, status=405)

    character.delete()

    return JsonResponse({
        "status": "ok",
    })


def genius_search_api(request):
    query = request.GET.get("q", "").strip()
    page = request.GET.get("page", "1")
    per_page = request.GET.get("per_page", "8")

    if not query:
        return JsonResponse({
            "status": "error",
            "message": _("Suchbegriff fehlt.")
        }, status=400)

    api_key = get_env_value("GENIUS_API_KEY")

    if not api_key:
        return api_error_response(missing_env_message("GENIUS_API_KEY"), status=500)

    try:
        page = max(1, int(page))
        per_page = min(20, max(1, int(per_page)))
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": _("Pagination-Parameter sind ungültig.")
        }, status=400)

    try:
        response = requests.get(
            "https://api.genius.com/search",
            params={
                "q": query,
                "page": page,
                "per_page": per_page,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            timeout=10,
        )
        data = response.json()

        if not isinstance(data, dict):
            return JsonResponse({
                "status": "error",
                "message": _("Ungültige Antwort der Genius API.")
            }, status=502)

        if response.status_code != 200:
            return JsonResponse({
                "status": "error",
                "message": data.get("meta", {}).get("message", _("Genius API Fehler."))
            }, status=response.status_code)

        results = []
        for hit in data.get("response", {}).get("hits", []):
            song = hit.get("result", {})
            artist = song.get("primary_artist") or {}

            results.append({
                "title": song.get("title", ""),
                "artist": artist.get("name", ""),
                "url": song.get("url", ""),
                "image": song.get("song_art_image_thumbnail_url", ""),
            })

        return JsonResponse({
            "status": "ok",
            "results": results,
        })
    except requests.RequestException:
        return JsonResponse({
            "status": "error",
            "message": _("Genius API konnte nicht erreicht werden.")
        }, status=502)
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": _("Ungültige Antwort der Genius API.")
        }, status=502)


def tankstellen_api(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if not lat or not lon:
        return JsonResponse({
            "status": "error",
            "message": _("Latitude und Longitude fehlen.")
        }, status=400)

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": _("Latitude und Longitude müssen Zahlen sein.")
        }, status=400)

    api_key = get_env_value("TANKERKOENIG_API_KEY")

    if not api_key:
        return api_error_response(missing_env_message("TANKERKOENIG_API_KEY"), status=500)

    url = "https://creativecommons.tankerkoenig.de/json/list.php"

    params = {
        "lat": lat,
        "lng": lon,
        "rad": 10,
        "sort": "dist",
        "type": "all",
        "apikey": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if not isinstance(data, dict):
            return api_error_response(_("Ungültige Antwort der Tankerkönig API."), status=502)

        if response.status_code != 200:
            return api_error_response(
                data.get("message", _("Tankerkönig API Fehler.")),
                status=response.status_code
            )

        return JsonResponse(data, status=response.status_code)
    except requests.RequestException:
        return JsonResponse({
            "status": "error",
            "message": _("Tankerkönig API konnte nicht erreicht werden.")
        }, status=502)
    except ValueError:
        return JsonResponse({
            "status": "error",
            "message": _("Ungültige Antwort der Tankerkönig API.")
        }, status=502)


def notes_view(request):
    query = request.GET.get("q", "").strip()
    show_archived = request.GET.get("archived") == "1"

    notes = Note.objects.filter(user=request.user, is_archived=show_archived)

    if query:
        notes = notes.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__icontains=query)
        )

    pinned_notes = notes.filter(is_pinned=True)
    normal_notes = notes.filter(is_pinned=False)

    context = {
        "pinned_notes": pinned_notes,
        "normal_notes": normal_notes,
        "query": query,
        "show_archived": show_archived,
        "note_count": notes.count(),
    }

    return render(request, "app/notes.html", context)


def note_create_view(request):
    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, _("Notiz wurde erstellt."))
            return redirect("notes")
    else:
        form = NoteForm()

    return render(request, "app/note_form.html", {
        "form": form,
        "form_title": _("Neue Notiz"),
        "submit_text": _("Notiz speichern"),
    })


def note_edit_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)

        if form.is_valid():
            form.save()
            messages.success(request, _("Notiz wurde aktualisiert."))
            return redirect("notes")
    else:
        form = NoteForm(instance=note)

    return render(request, "app/note_form.html", {
        "form": form,
        "note": note,
        "form_title": _("Notiz bearbeiten"),
        "submit_text": _("Änderungen speichern"),
    })


@require_POST
def note_delete_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.delete()

    messages.success(request, _("Notiz wurde gelöscht."))
    return redirect("notes")


@require_POST
def note_toggle_pin_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save()

    return redirect("notes")


@require_POST
def note_toggle_archive_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.is_archived = not note.is_archived
    note.save()

    if note.is_archived:
        messages.success(request, _("Notiz wurde archiviert."))
    else:
        messages.success(request, _("Notiz wurde wiederhergestellt."))

    return redirect("notes")


def unit_converter_view(request):
    converter_labels = {
        "storage": {
            "kb": _("Kilobyte (KB)"),
            "mb": _("Megabyte (MB)"),
            "gb": _("Gigabyte (GB)"),
            "tb": _("Terabyte (TB)"),
        },
        "time": {
            "seconds": _("Sekunden"),
            "minutes": _("Minuten"),
            "hours": _("Stunden"),
            "days": _("Tage"),
        },
        "distance": {
            "mm": _("Millimeter"),
            "cm": _("Zentimeter"),
            "m": _("Meter"),
            "km": _("Kilometer"),
            "mi": _("Meilen"),
        },
        "money": {
            "daily": _("Euro pro Tag"),
            "weekly": _("Euro pro Woche"),
            "monthly": _("Euro pro Monat"),
            "yearly": _("Euro pro Jahr"),
        },
        "messages": {
            "empty": _("Gib einen Wert ein, um die Umrechnung zu starten."),
        },
    }

    return render(request, "app/unit_converter.html", {
        "converter_labels": converter_labels,
    })


def drift_circuit(request):
    return render(request, "app/drift_circuit.html")


def stream_deck(request):
    return render(request, "app/stream_deck.html", {
        "spotify_client_id": get_env_value("SPOTIFY_CLIENT_ID") or "",
        "spotify_redirect_uri": get_env_value("SPOTIFY_REDIRECT_URI") or request.build_absolute_uri(request.path),
    })
