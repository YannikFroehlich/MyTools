import os
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
import requests
from django.utils import translation
from django.utils.formats import date_format
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.models import Shortcut, ShortcutSection

import json

from django.db.models import Max
from django.http import JsonResponse

load_dotenv()

api_key = os.getenv("OPENWEATHER_API_KEY")


def home(request):
    default_section, created = ShortcutSection.objects.get_or_create(
        name="Verknüpfungen",
        defaults={
            "color": "blue",
            "order": 0
        }
    )

    Shortcut.objects.filter(section__isnull=True).update(section=default_section)

    if request.method == "POST":
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"success": False, "error": "Ungültiges JSON"}, status=400)

            action = data.get("action")

            if action == "update_shortcut_order":
                shortcuts = data.get("shortcuts", [])

                for item in shortcuts:
                    shortcut_id = item.get("id")
                    section_id = item.get("section_id")
                    order = item.get("order", 0)

                    Shortcut.objects.filter(id=shortcut_id).update(
                        section_id=section_id,
                        order=order
                    )

                return JsonResponse({"success": True})

            if action == "update_section_order":
                sections = data.get("sections", [])

                for item in sections:
                    section_id = item.get("id")
                    order = item.get("order", 0)

                    ShortcutSection.objects.filter(id=section_id).update(order=order)

                return JsonResponse({"success": True})

            return JsonResponse({"success": False, "error": "Unbekannte Aktion"}, status=400)

        action = request.POST.get("action")

        if action == "add_section":
            section_name = request.POST.get("section_name", "").strip()
            section_color = request.POST.get("section_color", "blue").strip()

            if section_name:
                max_order = ShortcutSection.objects.aggregate(Max("order"))["order__max"] or 0

                ShortcutSection.objects.create(
                    name=section_name,
                    color=section_color,
                    order=max_order + 1
                )

            return redirect("home")

        if action == "delete_section":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(ShortcutSection, id=section_id)

            if section.name != "Verknüpfungen":
                section.delete()

            return redirect("home")

        if action == "toggle_section_collapse":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(ShortcutSection, id=section_id)

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

            section = get_object_or_404(ShortcutSection, id=section_id)

            if custom_icon:
                icon = custom_icon

            if name and url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                max_order = Shortcut.objects.filter(section=section).aggregate(Max("order"))["order__max"] or 0

                Shortcut.objects.create(
                    section=section,
                    name=name,
                    url=url,
                    icon=icon or "fa-solid fa-link",
                    image=image,
                    order=max_order + 1
                )

            return redirect("home")

        if action == "delete_shortcut":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id)
            shortcut.delete()

            return redirect("home")

        if action == "toggle_favorite":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id)

            shortcut.is_favorite = not shortcut.is_favorite
            shortcut.save()

            return redirect("home")

    sections = ShortcutSection.objects.prefetch_related("shortcuts").all().order_by("order", "created_at")

    return render(request, "app/home.html", {
        "sections": sections
    })

def about(request):
    template_name = 'app/about.html'
    return render(request, template_name)

def weather(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    city = request.GET.get("city", "Berlin")
    current_lang = translation.get_language()

    params = f"&appid={api_key}&units=metric&lang={current_lang}"
    location_query = f"lat={lat}&lon={lon}" if lat and lon else f"q={city}"

    try:
        curr_url = f"http://api.openweathermap.org/data/2.5/weather?{location_query}{params}"
        curr_response = requests.get(curr_url)
        curr_data = curr_response.json()

        if curr_response.status_code == 200:
            fore_url = f"http://api.openweathermap.org/data/2.5/forecast?{location_query}{params}"
            fore_response = requests.get(fore_url)
            fore_data = fore_response.json()

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

            # ───── Vollständiger Context (kein Duplikat mehr) ─────

            context = {
                'city': curr_data['name'],
                'country': curr_data['sys']['country'],
                'temperature': round(curr_data['main']['temp'], 1),
                'description': curr_data['weather'][0]['description'],
                'icon': curr_data['weather'][0]['icon'],
                'wind_speed': curr_data['wind']['speed'],
                'humidity': curr_data['main']['humidity'],
                'pressure': curr_data['main']['pressure'],
                'forecast': forecast_list,
                'hourly_forecast': hourly_forecast,
                'sunrise': sunrise,
                'sunset': sunset,
                'current_lang': current_lang,
            }
        else:
            context = {'error': "Standort nicht gefunden."}

    except Exception as e:
        context = {'error': f"Verbindungsfehler: {str(e)}"}

    return render(request, 'app/weather.html', context)