import os
import hashlib
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode
from io import BytesIO
import re

from django.shortcuts import render, redirect, get_object_or_404
import requests
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.core.cache import cache
from django.utils import translation
from django.utils.formats import date_format
from datetime import datetime, timezone, timedelta
from django.utils.translation import gettext as _
from django.utils import timezone as django_timezone

from dotenv import dotenv_values, load_dotenv

from app.models import (
    BudgetEntry,
    BudgetMonth,
    ChatMessage,
    ChatRoom,
    ChatRoomMember,
    ClockSettings,
    ClockTimerPreset,
    ClockWorldCity,
    DrawingGameInvite,
    DrawingGameLobby,
    DrawingGamePlayer,
    FeatureIdea,
    FeatureVote,
    FileShare,
    Friendship,
    HomeLayoutPreference,
    HomeWidget,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    InboxItem,
    KniffelGame,
    KniffelInvite,
    KniffelPlayer,
    Shortcut,
    ShortcutSection,
    StadtLandFlussInvite,
    StadtLandFlussLobby,
    StadtLandFlussPlayer,
    TicTacToeGame,
    ToolFavorite,
    UnoGame,
    UnoInvite,
    UnoPlayer,
    UserProfile,
    WeatherLocation,
)

import json

from django.db import transaction
from django.db.models import Count, Max, Prefetch, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse
from django.views.decorators.http import require_GET

from ..models import Note, SiteAccessSettings
from ..forms import SignUpForm
from ..image_optimization import SHORTCUT_ICON_MAX_SIZE, optimize_uploaded_image
from ..chat_permissions import accessible_chat_rooms_for_user
from .auth import GoogleOAuthCaptchaForm
from ..platform_utils import resolve_tools
from ..voicemod import VoicemodError, parse_voicemod_ports, send_voicemod_action
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


OPENWEATHER_CURRENT_CACHE_SECONDS = 300
OPENWEATHER_FORECAST_CACHE_SECONDS = 900


OPENWEATHER_ICON_CACHE_SECONDS = 60 * 60 * 24 * 30
OPENWEATHER_ICON_RE = re.compile(r"^[0-9]{2}[dn]$")
OPENWEATHER_ICON_SIZES = {"2x", "4x"}


def weather_icon_url(icon_code, size="2x"):
    icon_code = str(icon_code or "").strip()
    size = str(size or "2x").strip().lower()

    if not OPENWEATHER_ICON_RE.match(icon_code) or size not in OPENWEATHER_ICON_SIZES:
        return ""

    return reverse("weather_icon", args=[icon_code, size])


def weather_icon_view(request, icon_code, size="2x"):
    icon_code = str(icon_code or "").strip()
    size = str(size or "2x").strip().lower()

    if not OPENWEATHER_ICON_RE.match(icon_code) or size not in OPENWEATHER_ICON_SIZES:
        return HttpResponse(status=404)

    cache_key = f"openweather-icon:webp:{icon_code}:{size}:v1"
    cached = cache.get(cache_key)

    if cached is None:
        try:
            response = requests.get(
                f"https://openweathermap.org/img/wn/{icon_code}@{size}.png",
                timeout=5,
            )
            response.raise_for_status()

            with Image.open(BytesIO(response.content)) as image:
                output = BytesIO()
                image.convert("RGBA").save(output, format="WEBP", quality=82, method=6)
                cached = output.getvalue()

            cache.set(cache_key, cached, OPENWEATHER_ICON_CACHE_SECONDS)
        except (requests.RequestException, UnidentifiedImageError, OSError, ValueError):
            return HttpResponse(status=404)

    response = HttpResponse(cached, content_type="image/webp")
    response["Cache-Control"] = "public, max-age=2592000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _openweather_cache_key(endpoint, params):
    safe_params = {key: value for key, value in params.items() if key != "appid"}
    raw = json.dumps({"endpoint": endpoint, "params": safe_params}, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"openweather:{endpoint}:{digest}"


def cached_openweather_json(endpoint, params, *, timeout=10, cache_seconds=OPENWEATHER_CURRENT_CACHE_SECONDS):
    """Return OpenWeather JSON with a short Redis/Django cache.

    This keeps dashboard/weather page reloads from hitting the external API every
    time, but still refreshes quickly enough for normal weather usage.
    """
    cache_key = _openweather_cache_key(endpoint, params)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["status_code"], cached["data"]

    response = requests.get(
        f"https://api.openweathermap.org/data/2.5/{endpoint}",
        params=params,
        timeout=timeout,
    )
    data = response.json()
    if response.status_code == 200 and isinstance(data, dict):
        cache.set(cache_key, {"status_code": response.status_code, "data": data}, cache_seconds)
    return response.status_code, data


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
    timezone_choices = [(timezone, _(label)) for timezone, label in CLOCK_TIMEZONE_CHOICES]
    ringtone_choices = [(value, _(label)) for value, label in ClockSettings.RINGTONE_CHOICES]
    valid_timezones = {timezone for timezone, label in CLOCK_TIMEZONE_CHOICES}
    valid_ringtones = {choice[0] for choice in ClockSettings.RINGTONE_CHOICES}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_world_city":
            label = request.POST.get("label", "").strip()
            timezone_name = request.POST.get("timezone", "").strip()

            if not label and timezone_name in valid_timezones:
                label = dict(timezone_choices).get(timezone_name, timezone_name)

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
        "custom_sound_url": reverse("clock_custom_sound") if settings_obj.custom_sound else "",
        "timezone_choices": timezone_choices,
        "ringtone_choices": ringtone_choices,
    }
    return render(request, "app/clock.html", context)


@login_required
@require_GET
def clock_custom_sound_view(request):
    settings_obj, _created = ClockSettings.objects.get_or_create(user=request.user)
    if not settings_obj.custom_sound:
        raise Http404

    response = FileResponse(
        settings_obj.custom_sound.open("rb"),
        as_attachment=False,
        filename=settings_obj.custom_sound.name.rsplit("/", 1)[-1],
    )
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    if settings.OIDC_ONLY:
        return redirect("login")

    access_settings = SiteAccessSettings.get_solo()
    if access_settings.login_registration_locked:
        if request.method == "POST":
            messages.error(request, _("Registrierungen sind aktuell gesperrt."))
        return render(request, "registration/signup.html", {
            "form": SignUpForm(),
            "google_captcha_form": GoogleOAuthCaptchaForm(),
            "access_settings": access_settings,
            "access_locked": True,
        }, status=403 if request.method == "POST" else 200)

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, _("Dein Account wurde erstellt."))
            return redirect("home")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {
        "form": form,
        "google_captcha_form": GoogleOAuthCaptchaForm(),
        "access_settings": access_settings,
        "access_locked": False,
    })



def get_home_weather_data(request, user, widget):
    api_key = get_env_value("OPENWEATHER_API_KEY")
    units = request.GET.get("units", "metric")
    if units not in {"metric", "imperial"}:
        units = "metric"

    default_location = (
        WeatherLocation.objects.filter(user=user, is_default=True).first()
        or WeatherLocation.objects.filter(user=user).first()
    )
    location = widget.weather_location or default_location
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
        status_code, data = cached_openweather_json(
            "weather",
            params,
            timeout=6,
            cache_seconds=OPENWEATHER_CURRENT_CACHE_SECONDS,
        )

        if status_code != 200:
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
            "icon_url": weather_icon_url(weather_info.get("icon"), "2x"),
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


def build_home_chat_widget_data(user):
    accessible_room_ids = list(
        accessible_chat_rooms_for_user(user).values_list("id", flat=True)
    )
    memberships = list(
        ChatRoomMember.objects
        .filter(user=user, room_id__in=accessible_room_ids)
        .select_related("room")
        .order_by("-room__updated_at")
    )
    room_ids = [membership.room_id for membership in memberships]
    rooms = list(
        accessible_chat_rooms_for_user(user)
        .filter(id__in=room_ids)
        .prefetch_related("members", "members__profile")
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-last_message_at", "-updated_at")
        .distinct()[:4]
    )
    memberships_by_room = {membership.room_id: membership for membership in memberships}

    unread_total = 0
    recent_rooms = []
    for room in rooms:
        membership = memberships_by_room.get(room.id)
        unread_qs = ChatMessage.objects.filter(room=room).exclude(sender=user)
        if membership and membership.last_read_at:
            unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)
        unread_count = unread_qs.count()
        unread_total += unread_count

        recent_rooms.append({
            "id": room.id,
            "title": room.title_for(user),
            "type": room.room_type,
            "last_message": room.messages.select_related("sender").order_by("-created_at").first(),
            "unread_count": unread_count,
        })

    if len(rooms) < len(room_ids):
        for membership in memberships:
            if membership.room_id in {room.id for room in rooms}:
                continue
            unread_qs = ChatMessage.objects.filter(room=membership.room).exclude(sender=user)
            if membership.last_read_at:
                unread_qs = unread_qs.filter(created_at__gt=membership.last_read_at)
            unread_total += unread_qs.count()

    return {
        "room_count": len(room_ids),
        "unread_total": unread_total,
        "recent_rooms": recent_rooms,
    }


def build_home_friends_widget_data(user):
    accepted_friendships = list(Friendship.accepted_for_user(user)[:5])
    friend_users = []

    for friendship in accepted_friendships:
        other_user = friendship.other_user(user)
        if other_user:
            try:
                profile = other_user.profile
            except UserProfile.DoesNotExist:
                profile, _created = UserProfile.objects.get_or_create(user=other_user)
            friend_users.append({
                "user": other_user,
                "profile": profile,
                "since": friendship.updated_at,
            })

    return {
        "friend_count": Friendship.accepted_for_user(user).count(),
        "incoming_count": Friendship.objects.filter(to_user=user, status=Friendship.STATUS_PENDING).count(),
        "outgoing_count": Friendship.objects.filter(from_user=user, status=Friendship.STATUS_PENDING).count(),
        "recent_friends": friend_users[:3],
    }


def build_home_skribble_widget_data(user):
    pending_invites = (
        DrawingGameInvite.objects
        .filter(to_user=user, status=DrawingGameInvite.STATUS_PENDING)
        .select_related("lobby", "from_user")[:3]
    )
    active_lobbies = (
        DrawingGameLobby.objects
        .filter(players__user=user, status__in=[DrawingGameLobby.STATUS_WAITING, DrawingGameLobby.STATUS_PLAYING])
        .distinct()
        .order_by("-updated_at")[:3]
    )

    return {
        "pending_invites_count": DrawingGameInvite.objects.filter(to_user=user, status=DrawingGameInvite.STATUS_PENDING).count(),
        "owned_waiting_count": DrawingGameLobby.objects.filter(owner=user, status=DrawingGameLobby.STATUS_WAITING).count(),
        "active_lobbies_count": DrawingGamePlayer.objects.filter(
            user=user,
            lobby__status__in=[DrawingGameLobby.STATUS_WAITING, DrawingGameLobby.STATUS_PLAYING],
        ).count(),
        "pending_invites": pending_invites,
        "active_lobbies": active_lobbies,
    }


def build_home_tictactoe_widget_data(user):
    active_games = (
        TicTacToeGame.objects
        .filter(
            Q(owner=user) | Q(player_x=user) | Q(player_o=user),
            status__in=[TicTacToeGame.STATUS_WAITING, TicTacToeGame.STATUS_PLAYING],
        )
        .distinct()
        .select_related("player_x", "player_o")
        .order_by("-updated_at")[:3]
    )

    return {
        "active_count": (
            TicTacToeGame.objects
            .filter(
                Q(owner=user) | Q(player_x=user) | Q(player_o=user),
                status__in=[TicTacToeGame.STATUS_WAITING, TicTacToeGame.STATUS_PLAYING],
            )
            .distinct()
            .count()
        ),
        "active_games": active_games,
    }


def build_home_stadtlandfluss_widget_data(user):
    active_lobbies = (
        StadtLandFlussLobby.objects
        .filter(
            Q(owner=user) | Q(players__user=user),
            status__in=[
                StadtLandFlussLobby.STATUS_WAITING,
                StadtLandFlussLobby.STATUS_PLAYING,
                StadtLandFlussLobby.STATUS_ROUND_SUMMARY,
            ],
        )
        .distinct()
        .order_by("-updated_at")[:3]
    )

    return {
        "pending_invites_count": StadtLandFlussInvite.objects.filter(
            to_user=user,
            status=StadtLandFlussInvite.STATUS_PENDING,
        ).count(),
        "active_count": StadtLandFlussPlayer.objects.filter(
            user=user,
            lobby__status__in=[
                StadtLandFlussLobby.STATUS_WAITING,
                StadtLandFlussLobby.STATUS_PLAYING,
                StadtLandFlussLobby.STATUS_ROUND_SUMMARY,
            ],
        ).count(),
        "pending_invites": (
            StadtLandFlussInvite.objects
            .filter(to_user=user, status=StadtLandFlussInvite.STATUS_PENDING)
            .select_related("lobby", "from_user")[:3]
        ),
        "active_lobbies": active_lobbies,
    }


def build_home_uno_widget_data(user):
    active_games = (
        UnoGame.objects
        .filter(
            Q(owner=user) | Q(players__user=user),
            status__in=[UnoGame.STATUS_WAITING, UnoGame.STATUS_PLAYING],
        )
        .distinct()
        .order_by("-updated_at")[:3]
    )

    return {
        "pending_invites_count": UnoInvite.objects.filter(
            to_user=user,
            status=UnoInvite.STATUS_PENDING,
        ).count(),
        "active_count": UnoPlayer.objects.filter(
            user=user,
            game__status__in=[UnoGame.STATUS_WAITING, UnoGame.STATUS_PLAYING],
        ).count(),
        "pending_invites": (
            UnoInvite.objects
            .filter(to_user=user, status=UnoInvite.STATUS_PENDING)
            .select_related("game", "from_user")[:3]
        ),
        "active_games": active_games,
    }


def build_home_kniffel_widget_data(user):
    active_games = (
        KniffelGame.objects
        .filter(
            Q(owner=user) | Q(players__user=user),
            status__in=[KniffelGame.STATUS_WAITING, KniffelGame.STATUS_PLAYING],
        )
        .distinct()
        .order_by("-updated_at")[:3]
    )

    return {
        "pending_invites_count": KniffelInvite.objects.filter(
            to_user=user,
            status=KniffelInvite.STATUS_PENDING,
        ).count(),
        "active_count": KniffelPlayer.objects.filter(
            user=user,
            game__status__in=[KniffelGame.STATUS_WAITING, KniffelGame.STATUS_PLAYING],
        ).count(),
        "pending_invites": (
            KniffelInvite.objects
            .filter(to_user=user, status=KniffelInvite.STATUS_PENDING)
            .select_related("game", "from_user")[:3]
        ),
        "active_games": active_games,
    }


def format_home_money(value):
    try:
        amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.00")

    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


def build_home_file_share_widget_data(user):
    own_shares = FileShare.objects.filter(owner=user)
    received_shares = (
        FileShare.objects
        .filter(recipients=user)
        .exclude(owner=user)
        .select_related("owner")
        .distinct()
    )
    own_size = own_shares.aggregate(total=Sum("size"))["total"] or 0

    return {
        "own_count": own_shares.count(),
        "received_count": received_shares.count(),
        "public_link_count": own_shares.filter(is_public_link=True).count(),
        "own_size_label": FileShare(size=own_size).human_size,
        "recent_received": received_shares.order_by("-created_at")[:3],
        "recent_own": own_shares.order_by("-created_at")[:3],
    }


def build_home_budget_widget_data(user):
    today = django_timezone.localdate()
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)

    budget_month = BudgetMonth.objects.filter(
        user=user,
        year=month_start.year,
        month=month_start.month,
    ).first()
    entries = BudgetEntry.objects.filter(user=user, date__gte=month_start, date__lt=next_month_start)
    total_income = entries.filter(entry_type=BudgetEntry.TYPE_INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_expenses = entries.filter(entry_type=BudgetEntry.TYPE_EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    balance = total_income - total_expenses
    expense_limit = budget_month.expense_limit if budget_month else Decimal("0.00")
    savings_goal = budget_month.savings_goal if budget_month else Decimal("0.00")

    if expense_limit and expense_limit > 0:
        expense_usage_percent = int(min(100, max(0, (total_expenses / expense_limit) * Decimal("100"))))
        limit_remaining = expense_limit - total_expenses
    else:
        expense_usage_percent = 0
        limit_remaining = Decimal("0.00")

    return {
        "month_label": date_format(month_start, "F Y"),
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "total_income_label": format_home_money(total_income),
        "total_expenses_label": format_home_money(total_expenses),
        "balance_label": format_home_money(balance),
        "expense_limit_label": format_home_money(expense_limit),
        "limit_remaining_label": format_home_money(limit_remaining),
        "savings_goal_label": format_home_money(savings_goal),
        "expense_usage_percent": expense_usage_percent,
        "has_plan": bool(budget_month and (budget_month.planned_income or budget_month.expense_limit or budget_month.savings_goal)),
        "recent_entries": entries.select_related("category").order_by("-date", "-created_at")[:3],
    }


def build_home_favorites_widget_data(request, user):
    favorite_keys = list(ToolFavorite.objects.filter(user=user).values_list("tool_key", flat=True))
    favorite_key_set = set(favorite_keys)
    tools_by_key = {
        tool["key"]: tool
        for tool in resolve_tools(request, favorite_key_set)
        if tool.get("is_favorite")
    }
    favorite_tools = [tools_by_key[key] for key in favorite_keys if key in tools_by_key]
    categories = sorted({str(tool["category"]) for tool in favorite_tools})

    return {
        "favorite_count": len(favorite_tools),
        "category_count": len(categories),
        "favorite_tools": favorite_tools[:4],
    }


def build_home_roadmap_widget_data(user):
    open_statuses = [
        FeatureIdea.STATUS_SUGGESTED,
        FeatureIdea.STATUS_PLANNED,
        FeatureIdea.STATUS_IN_PROGRESS,
    ]
    popular_ideas = (
        FeatureIdea.objects
        .select_related("author")
        .annotate(vote_total=Count("votes"))
        .order_by("-vote_total", "-updated_at", "-created_at")[:3]
    )

    return {
        "total_ideas": FeatureIdea.objects.count(),
        "open_count": FeatureIdea.objects.filter(status__in=open_statuses).count(),
        "in_progress_count": FeatureIdea.objects.filter(status=FeatureIdea.STATUS_IN_PROGRESS).count(),
        "done_count": FeatureIdea.objects.filter(status=FeatureIdea.STATUS_DONE).count(),
        "user_votes": FeatureVote.objects.filter(user=user).count(),
        "popular_ideas": popular_ideas,
    }


def build_home_inbox_widget_data(user):
    inbox_items = InboxItem.objects.filter(user=user)

    return {
        "unread_count": inbox_items.filter(is_read=False).count(),
        "total_count": inbox_items.count(),
        "recent_items": inbox_items.order_by("-created_at")[:3],
    }


def build_home_changelog_widget_data():
    from .community import get_changelog_entries

    entries = get_changelog_entries()
    latest_entry = entries[0] if entries else None

    return {
        "latest_entry": latest_entry,
        "release_count": len(entries),
        "change_count": sum(len(entry.get("items", [])) for entry in entries),
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

        elif widget.widget_type == HomeWidget.WIDGET_CHAT:
            data = build_home_chat_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_FRIENDS:
            data = build_home_friends_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_SKRIBBLE:
            data = build_home_skribble_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_TICTACTOE:
            data = build_home_tictactoe_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_STADTLANDFLUSS:
            data = build_home_stadtlandfluss_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_UNO:
            data = build_home_uno_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_KNIFFEL:
            data = build_home_kniffel_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_FILE_SHARE:
            data = build_home_file_share_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_BUDGET:
            data = build_home_budget_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_FAVORITES:
            data = build_home_favorites_widget_data(request, user)

        elif widget.widget_type == HomeWidget.WIDGET_ROADMAP:
            data = build_home_roadmap_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_INBOX:
            data = build_home_inbox_widget_data(user)

        elif widget.widget_type == HomeWidget.WIDGET_CHANGELOG:
            data = build_home_changelog_widget_data()

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


def home_onboarding_templates():
    return {
        "everyday": {
            "widgets": [
                {"title": _("Uhr"), "widget_type": HomeWidget.WIDGET_CLOCK, "color": "theme"},
                {"title": _("Wetter"), "widget_type": HomeWidget.WIDGET_WEATHER, "color": "theme"},
                {"title": _("Notizen"), "widget_type": HomeWidget.WIDGET_NOTES, "color": "theme"},
                {"title": _("Schnellstatistiken"), "widget_type": HomeWidget.WIDGET_STATS, "color": "theme"},
            ],
            "shortcuts": [
                {"name": "Gmail", "url": "https://mail.google.com", "icon": "fa-solid fa-envelope"},
                {"name": _("Kalender"), "url": "https://calendar.google.com", "icon": "fa-solid fa-calendar-days"},
                {"name": "YouTube", "url": "https://www.youtube.com", "icon": "fa-brands fa-youtube"},
            ],
        },
        "gaming": {
            "widgets": [
                {"title": _("Chats"), "widget_type": HomeWidget.WIDGET_CHAT, "color": "theme"},
                {"title": _("Freunde"), "widget_type": HomeWidget.WIDGET_FRIENDS, "color": "theme"},
                {"title": _("Tic Tac Toe"), "widget_type": HomeWidget.WIDGET_TICTACTOE, "color": "theme"},
                {"title": _("Human Benchmark"), "widget_type": HomeWidget.WIDGET_BENCHMARK, "color": "theme"},
            ],
            "shortcuts": [
                {"name": "Steam", "url": "https://store.steampowered.com", "icon": "fa-brands fa-steam"},
                {"name": "Twitch", "url": "https://www.twitch.tv", "icon": "fa-brands fa-twitch"},
                {"name": "Discord", "url": "https://discord.com/app", "icon": "fa-brands fa-discord"},
            ],
        },
        "homelab": {
            "widgets": [
                {"title": _("Schnellstatistiken"), "widget_type": HomeWidget.WIDGET_STATS, "color": "theme"},
                {"title": _("Notizen"), "widget_type": HomeWidget.WIDGET_NOTES, "color": "theme"},
                {"title": _("Uhr"), "widget_type": HomeWidget.WIDGET_CLOCK, "color": "theme"},
            ],
            "shortcuts": [
                {"name": "CasaOS", "url": "http://casaos.local", "icon": "fa-solid fa-server"},
                {"name": "Home Assistant", "url": "http://homeassistant.local:8123", "icon": "fa-solid fa-house-signal"},
                {"name": "Nextcloud", "url": "http://nextcloud.local", "icon": "fa-solid fa-cloud"},
            ],
        },
    }


def apply_home_onboarding_template(user, template_key):
    templates = home_onboarding_templates()
    if template_key not in {*templates, "blank"}:
        return False

    with transaction.atomic():
        layout_preference, _ = (
            HomeLayoutPreference.objects
            .select_for_update()
            .get_or_create(user=user)
        )

        if layout_preference.onboarding_completed:
            return False

        template = templates.get(template_key)
        if template:
            if not HomeWidget.objects.filter(user=user).exists():
                HomeWidget.objects.bulk_create([
                    HomeWidget(user=user, order=order, **widget)
                    for order, widget in enumerate(template["widgets"], start=1)
                ])

            if not Shortcut.objects.filter(user=user).exists():
                default_section, _ = ShortcutSection.objects.get_or_create(
                    user=user,
                    name="Verknüpfungen",
                    defaults={"color": "theme", "order": 0},
                )
                Shortcut.objects.bulk_create([
                    Shortcut(user=user, section=default_section, order=order, **shortcut)
                    for order, shortcut in enumerate(template["shortcuts"], start=1)
                ])

        layout_preference.onboarding_completed = True
        layout_preference.save(update_fields=["onboarding_completed", "updated_at"])

    return True


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
        "currentImage": _("Aktuelles Bild vorhanden"),
        "newWidget": _("Neues Widget"),
        "editWidget": _("Widget bearbeiten"),
        "addWidget": _("Widget hinzufügen"),
        "saveWidget": _("Widget speichern"),
        "widgetDeleted": _("Widget gelöscht"),
        "sectionDeleted": _("Bereich gelöscht"),
        "shortcutDeleted": _("Verknüpfung gelöscht"),
        "deletePending": _("Wird in wenigen Sekunden endgültig gelöscht."),
        "undoDelete": _("Rückgängig"),
        "deleteFailed": _("Löschen fehlgeschlagen"),
        "deleteFailedHint": _("Bitte versuche es noch einmal."),
    }

    default_section, created = ShortcutSection.objects.get_or_create(
        user=user,
        name="Verknüpfungen",
        defaults={
            "color": "theme",
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

        if action == "complete_onboarding":
            template_key = request.POST.get("onboarding_template", "everyday").strip()
            apply_home_onboarding_template(user, template_key)
            return redirect("home")

        if action == "add_widget":
            title = request.POST.get("widget_title", "").strip()
            widget_type = request.POST.get("widget_type", HomeWidget.WIDGET_WEATHER).strip()
            widget_color = request.POST.get("widget_color", "theme").strip()
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
                widget_color = "theme"

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
            widget_color = request.POST.get("widget_color", "theme").strip()
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
                widget_color = "theme"

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
            widget.move_to_trash()

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True, "deleted": "widget"})
            return redirect("home")

        if action == "add_section":
            section_name = request.POST.get("section_name", "").strip()
            section_color = request.POST.get("section_color", "theme").strip()
            valid_section_colors = {choice[0] for choice in ShortcutSection.COLOR_CHOICES}

            if section_color not in valid_section_colors:
                section_color = "theme"

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
            section_color = request.POST.get("section_color", "theme").strip()
            valid_section_colors = {choice[0] for choice in ShortcutSection.COLOR_CHOICES}

            if section_color not in valid_section_colors:
                section_color = "theme"

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
            deleted = False

            if section.name != "Verknüpfungen":
                default_section, _created = ShortcutSection.objects.get_or_create(
                    user=user,
                    name="Verknüpfungen",
                    defaults={"color": "theme", "order": 0},
                )
                Shortcut.all_objects.filter(section=section, deleted_at__isnull=True).update(
                    deleted_at=django_timezone.now(),
                )
                Shortcut.all_objects.filter(section=section).update(section=default_section)
                section.delete()
                deleted = True

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": deleted, "deleted": "section"})
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
            remove_image = request.POST.get("remove_image") == "1"
            color = request.POST.get("shortcut_color", "theme").strip()
            valid_shortcut_colors = {choice[0] for choice in ShortcutSection.COLOR_CHOICES}

            if color not in valid_shortcut_colors:
                color = "theme"

            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if custom_icon:
                icon = custom_icon

            if name and url:
                optimized_image = None
                if image:
                    try:
                        optimized_image = optimize_uploaded_image(
                            image,
                            prefix=f"shortcut_{user.id}",
                            max_size=SHORTCUT_ICON_MAX_SIZE,
                        )
                    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
                        messages.error(request, _("Das Shortcut-Bild konnte nicht verarbeitet werden."))
                        return redirect("home")

                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                max_order = Shortcut.objects.filter(user=user, section=section).aggregate(Max("order"))[
                                "order__max"] or 0

                shortcut = Shortcut(
                    user=user,
                    section=section,
                    name=name,
                    url=url,
                    icon=icon or "fa-solid fa-link",
                    color=color,
                    order=max_order + 1
                )
                if optimized_image:
                    shortcut.image.save(
                        optimized_image.filename,
                        optimized_image.file,
                        save=False,
                    )
                shortcut.save()

            return redirect("home")

        if action == "edit_shortcut":
            shortcut_id = request.POST.get("shortcut_id")
            section_id = request.POST.get("section_id")
            name = request.POST.get("name", "").strip()
            url = request.POST.get("url", "").strip()
            icon = request.POST.get("icon", "").strip()
            custom_icon = request.POST.get("custom_icon", "").strip()
            image = request.FILES.get("image")
            remove_image = request.POST.get("remove_image") == "1"
            color = request.POST.get("shortcut_color", "theme").strip()
            valid_shortcut_colors = {choice[0] for choice in ShortcutSection.COLOR_CHOICES}

            if color not in valid_shortcut_colors:
                color = "theme"

            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)
            section = get_object_or_404(ShortcutSection, id=section_id, user=user)

            if custom_icon:
                icon = custom_icon

            if name and url:
                optimized_image = None
                if image:
                    try:
                        optimized_image = optimize_uploaded_image(
                            image,
                            prefix=f"shortcut_{user.id}",
                            max_size=SHORTCUT_ICON_MAX_SIZE,
                        )
                    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
                        messages.error(request, _("Das Shortcut-Bild konnte nicht verarbeitet werden."))
                        return redirect("home")

                if not url.startswith(("http://", "https://")):
                    url = "https://" + url

                shortcut.section = section
                shortcut.name = name
                shortcut.url = url
                shortcut.icon = icon or "fa-solid fa-link"
                shortcut.color = color

                if remove_image and shortcut.image:
                    shortcut.image.delete(save=False)
                    shortcut.image = None

                if optimized_image:
                    if shortcut.image:
                        shortcut.image.delete(save=False)
                    shortcut.image.save(
                        optimized_image.filename,
                        optimized_image.file,
                        save=False,
                    )

                shortcut.save()

            return redirect("home")

        if action == "toggle_favorite":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)
            shortcut.is_favorite = not shortcut.is_favorite
            shortcut.save(update_fields=["is_favorite"])

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": True,
                    "is_favorite": shortcut.is_favorite,
                })
            return redirect("home")

        if action == "delete_shortcut":
            shortcut_id = request.POST.get("shortcut_id")
            shortcut = get_object_or_404(Shortcut, id=shortcut_id, user=user)
            shortcut.move_to_trash()

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True, "deleted": "shortcut"})
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
    show_onboarding = (
        not layout_preference.onboarding_completed
        and not custom_sections
        and not Shortcut.objects.filter(user=user).exists()
        and not HomeWidget.objects.filter(user=user).exists()
    )

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
        "shortcut_colors": [(value, _(label)) for value, label in ShortcutSection.COLOR_CHOICES],
        "clock_designs": [(value, _(label)) for value, label in HomeWidget.CLOCK_DESIGN_CHOICES],
        "clock_styles": [(value, _(label)) for value, label in HomeWidget.CLOCK_STYLE_CHOICES],
        "home_labels": home_labels,
        "show_onboarding": show_onboarding,
    })


def about(request):
    template_name = 'app/about.html'
    return render(request, template_name)


def weather(request):
    user = request.user
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    units = request.GET.get("units") or request.POST.get("units") or "metric"
    if units not in {"metric", "imperial"}:
        units = "metric"

    saved_locations = (
        WeatherLocation.objects.filter(user=user)
        if user.is_authenticated
        else WeatherLocation.objects.none()
    )
    default_location = saved_locations.filter(is_default=True).first() or saved_locations.first()
    city = (request.GET.get("city") or "").strip()
    if not city and not (lat and lon):
        city = default_location.name if default_location else "Berlin"
    city = city or "Berlin"

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
            "default_location": default_location,
            "units": units,
            "temperature_unit": temperature_unit,
            "wind_unit": wind_unit,
        }
        context.update(extra)
        return context

    # ───── Gespeicherte Wetter-Orte: Hinzufügen / Löschen ─────
    if request.method == "POST":
        if not user.is_authenticated:
            return redirect(request.path)

        action = request.POST.get("action")

        if action == "add_weather_location":
            location_name = request.POST.get("location_name", "").strip()

            if location_name:
                has_locations = saved_locations.exists()
                max_order = WeatherLocation.objects.filter(user=user).aggregate(Max("order"))["order__max"] or 0

                WeatherLocation.objects.get_or_create(
                    user=user,
                    name=location_name,
                    defaults={
                        "is_default": not has_locations,
                        "order": max_order + 1
                    }
                )

                return redirect(weather_redirect_url(city=location_name))

            return redirect(request.path)

        if action == "set_default_weather_location":
            location_id = request.POST.get("location_id")
            current_city = request.POST.get("current_city", city).strip() or "Berlin"
            location = WeatherLocation.objects.filter(id=location_id, user=user).first()

            if location:
                WeatherLocation.objects.filter(user=user, is_default=True).exclude(id=location.id).update(is_default=False)
                if not location.is_default:
                    location.is_default = True
                    location.save(update_fields=["is_default"])
                return redirect(weather_redirect_url(city=location.name))

            return redirect(weather_redirect_url(city=current_city))

        if action == "delete_weather_location":
            location_id = request.POST.get("location_id")
            current_city = request.POST.get("current_city", city).strip() or "Berlin"

            if location_id:
                location = WeatherLocation.objects.filter(id=location_id, user=user).first()
                if location:
                    deleted_name = location.name
                    was_default = location.is_default
                    location.delete()

                    remaining_locations = WeatherLocation.objects.filter(user=user)
                    replacement_location = (
                        remaining_locations.filter(is_default=True).first()
                        or remaining_locations.first()
                    )

                    if was_default and replacement_location and not replacement_location.is_default:
                        replacement_location.is_default = True
                        replacement_location.save(update_fields=["is_default"])

                    if current_city == deleted_name:
                        current_city = replacement_location.name if replacement_location else "Berlin"

            return redirect(weather_redirect_url(city=current_city))

        return redirect(request.path)

    if not api_key:
        return render(request, 'app/weather.html', weather_context(
            saved_locations=saved_locations,
            error=missing_env_message("OPENWEATHER_API_KEY"),
        ))

    params = {
        "appid": api_key,
        "units": units,
        "lang": current_lang,
    }
    if lat and lon:
        params.update({"lat": lat, "lon": lon})
    else:
        params["q"] = city

    try:
        curr_status_code, curr_data = cached_openweather_json(
            "weather",
            params,
            timeout=10,
            cache_seconds=OPENWEATHER_CURRENT_CACHE_SECONDS,
        )

        if not isinstance(curr_data, dict):
            context = {
                'city': city,
                'saved_locations': saved_locations,
                'error': _("Ungültige Antwort der OpenWeather API.")
            }
            context.update(weather_context())
            return render(request, 'app/weather.html', context)

        if curr_status_code == 200:
            fore_status_code, fore_data = cached_openweather_json(
                "forecast",
                params,
                timeout=10,
                cache_seconds=OPENWEATHER_FORECAST_CACHE_SECONDS,
            )

            if not isinstance(fore_data, dict):
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("Ungültige Antwort der OpenWeather API.")
                }
                context.update(weather_context())
                return render(request, 'app/weather.html', context)

            if fore_status_code != 200:
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
                    'rain': round(midday_item.get('pop', 0) * 100),
                    'icon_url': weather_icon_url(midday_item['weather'][0]['icon'], '2x'),
                })

            # ───── Stündliche Vorhersage ─────

            hourly_forecast = []

            for item in fore_data['list'][:8]:
                dt_obj = datetime.fromtimestamp(item['dt'])

                hourly_forecast.append({
                    'time': dt_obj.strftime("%H:%M"),
                    'temp': round(item['main']['temp']),
                    'icon': item['weather'][0]['icon'],
                    'rain': round(item.get('pop', 0) * 100),
                    'icon_url': weather_icon_url(item['weather'][0]['icon'], '2x'),
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
                'icon_url': weather_icon_url(curr_data['weather'][0]['icon'], '4x'),
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

            if curr_status_code == 401:
                context = {
                    'city': city,
                    'saved_locations': saved_locations,
                    'error': _("OpenWeather API-Key ist ungültig.")
                }
            elif curr_status_code == 404:
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
