import json
import math

import requests
from PIL import Image, UnidentifiedImageError
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone as django_timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from app.models import (
    AvatarCharacter,
    CookieClickerHighScore,
    CookieCosmosV2Save,
    Game2048HighScore,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    NebulaForgeTycoonSave,
    SnakeHighScore,
)

from ..image_optimization import WIKI_IMAGE_MAX_SIZE, optimize_uploaded_image
from ..presence_utils import clear_active_game, mark_active_game
from . import core as core_views


MAX_AVATAR_WIKI_UPLOAD_SIZE = 10 * 1024 * 1024


def get_env_value(name):
    return core_views.get_env_value(name)


def missing_env_message(name):
    return core_views.missing_env_message(name)


def api_error_response(message, status=400):
    return core_views.api_error_response(message, status=status)


def send_voicemod_action(*args, **kwargs):
    return core_views.send_voicemod_action(*args, **kwargs)


VoicemodError = core_views.VoicemodError
parse_voicemod_ports = core_views.parse_voicemod_ports


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
        ).order_by("-created_at", "-id")[:10]

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
    mark_active_game(request.user, "human_benchmark")
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
    mark_active_game(request.user, "human_benchmark")
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

        if image.size > MAX_AVATAR_WIKI_UPLOAD_SIZE:
            return JsonResponse({
                "status": "error",
                "message": _("Das Bild darf maximal 10 MB groß sein."),
            }, status=413)

        try:
            optimized_image = optimize_uploaded_image(
                image,
                prefix=f"avatar_wiki_{user.id}",
                max_size=WIKI_IMAGE_MAX_SIZE,
            )
        except Image.DecompressionBombError:
            return JsonResponse({
                "status": "error",
                "message": _("Die Bildabmessungen sind zu gross."),
            }, status=413)
        except (UnidentifiedImageError, OSError, ValueError):
            return JsonResponse({
                "status": "error",
                "message": _("Das Bild konnte nicht verarbeitet werden."),
            }, status=400)

        try:
            max_order = AvatarCharacter.objects.filter(user=user).aggregate(Max("order"))["order__max"]
            character = AvatarCharacter(
                user=user,
                name=name,
                nation=nation,
                link=link,
                description=description,
                order=(max_order + 1) if max_order is not None else 0,
            )
            character.image.save(
                optimized_image.filename,
                optimized_image.file,
                save=False,
            )
            character.save()
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
            if image.size > MAX_AVATAR_WIKI_UPLOAD_SIZE:
                return JsonResponse({
                    "status": "error",
                    "message": _("Das Bild darf maximal 10 MB groß sein."),
                }, status=413)
            try:
                optimized_image = optimize_uploaded_image(
                    image,
                    prefix=f"avatar_wiki_{request.user.id}",
                    max_size=WIKI_IMAGE_MAX_SIZE,
                )
            except Image.DecompressionBombError:
                return JsonResponse({
                    "status": "error",
                    "message": _("Die Bildabmessungen sind zu gross."),
                }, status=413)
            except (UnidentifiedImageError, OSError, ValueError):
                return JsonResponse({
                    "status": "error",
                    "message": _("Das Bild konnte nicht verarbeitet werden."),
                }, status=400)
            if character.image:
                character.image.delete(save=False)
            character.image.save(
                optimized_image.filename,
                optimized_image.file,
                save=False,
            )

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


def calculator_view(request):
    return render(request, "app/calculator.html")


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


def _drift_frontend_i18n():
    return {
        "modeTimeTrial": _("Time Trial · 3 Runden"),
        "modeCheckpointRush": _("Checkpoint Rush · 90 Sekunden"),
        "modeZen": _("Zen Drive · Freies Fahren"),
        "layoutCityFlow": _("City Flow"),
        "layoutSnakeRally": _("Snake Rally"),
        "layoutHairpinMountain": _("Hairpin Mountain"),
        "startFinish": _("Start/Ziel"),
        "checkpoint": _("Checkpoint {number}"),
        "go": _("GO!"),
        "lap": _("Runde {current} / {total}"),
        "timeExpired": _("Zeit abgelaufen"),
        "checkpointRushFinished": _("Checkpoint Rush beendet:"),
        "raceFinished": _("Rennen beendet"),
        "yourTime": _("Deine Zeit:"),
        "checkpoints": _("{count} Checkpoints"),
        "statMap": _("Map"),
        "statLayout": _("Layout"),
        "statScore": _("Score"),
        "statDriftPoints": _("Driftpunkte"),
        "statCheckpoints": _("Checkpoints"),
        "checkpointGate": _("CHECKPOINT"),
        "free": _("Frei"),
        "checkpointAbbr": _("CP"),
        "drift": _("Drift"),
    }


def drift_circuit(request):
    mark_active_game(request.user, "drift_circuit")
    return render(request, "app/drift_circuit.html", {
        "drift_i18n": _drift_frontend_i18n(),
    })


SNAKE_SPEED_KEYS = {"relaxed", "normal", "fast", "turbo"}
SNAKE_SPAWN_KEYS = {"slow", "normal", "high", "instant"}
SNAKE_WALL_KEYS = {"wrap", "wall"}


def _snake_int(value, default=0, minimum=0, maximum=999999999):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def normalize_snake_settings(raw_settings):
    raw_settings = raw_settings if isinstance(raw_settings, dict) else {}
    board_size = _snake_int(raw_settings.get("boardSize"), 19, 11, 31)
    fruit_limit = _snake_int(raw_settings.get("fruitLimit"), 1, 1, 7)
    speed_key = str(raw_settings.get("speedKey") or "normal")
    spawn_key = str(raw_settings.get("spawnKey") or "normal")
    wall_mode = str(raw_settings.get("wallMode") or "wrap")

    return {
        "boardSize": board_size,
        "speedKey": speed_key if speed_key in SNAKE_SPEED_KEYS else "normal",
        "fruitLimit": fruit_limit,
        "spawnKey": spawn_key if spawn_key in SNAKE_SPAWN_KEYS else "normal",
        "wallMode": wall_mode if wall_mode in SNAKE_WALL_KEYS else "wrap",
    }


def snake_settings_key(settings):
    return "|".join([
        str(settings["boardSize"]),
        settings["speedKey"],
        str(settings["fruitLimit"]),
        settings["spawnKey"],
        settings["wallMode"],
    ])


def serialize_snake_highscore(highscore):
    if not highscore:
        return None

    return {
        "key": highscore.settings_key,
        "settings": highscore.settings or {},
        "score": highscore.score,
        "length": highscore.length,
        "fruits": highscore.fruits,
        "moves": highscore.moves,
        "durationSeconds": highscore.duration_seconds,
        "runs": highscore.runs,
        "achievedAt": highscore.achieved_at.isoformat(),
        "achievedAtLabel": date_format(highscore.achieved_at, "d.m.Y H:i"),
    }


@ensure_csrf_cookie
def snake_powerups(request):
    mark_active_game(request.user, "snake_powerups")
    snake_text = {
        "readyKicker": _("Bereit"),
        "readyText": _("Starte ein schlichtes Snake ohne Effekte. Die Lüfter sollten dabei deutlich ruhiger bleiben."),
        "pausedKicker": _("Pausiert"),
        "pausedTitle": _("Pause"),
        "pausedText": _("Drücke Fortsetzen oder die Leertaste."),
        "resume": _("Fortsetzen"),
        "start": _("Start"),
        "pause": _("Pausieren"),
        "settingsLocked": _("Einstellungen sind während des Runs gesperrt."),
        "settingsHint": _("Änderungen gelten ab dem nächsten Start."),
        "hitWall": _("Die Snake ist gegen die Wand gelaufen."),
        "hitSnake": _("Die Snake hat sich selbst erwischt."),
        "boardFull": _("Das Spielfeld ist voll. Stark gespielt!"),
        "newHighscore": _("Neuer Highscore!"),
        "gameOverKicker": _("Game Over"),
        "gameOverTitle": _("Game Over"),
        "scoreSaved": _("Dein Score wurde gespeichert."),
        "fruitSingle": _("Frucht"),
        "fruitPlural": _("Früchte"),
        "lengthShort": _("Länge"),
        "noHighscore": _("Noch kein Highscore"),
        "emptyHighscores": _("Noch keine Highscores gespielt."),
        "speedLabels": {
            "relaxed": _("Entspannt"),
            "normal": _("Normal"),
            "fast": _("Schnell"),
            "turbo": _("Turbo"),
        },
        "spawnLabels": {
            "slow": _("Ruhig"),
            "normal": _("Standard"),
            "high": _("Hoch"),
            "instant": _("Sofort"),
        },
        "wallLabels": {
            "wrap": _("Durchlaufen"),
            "wall": _("Wände"),
        },
    }
    snake_highscores = []
    if request.user.is_authenticated:
        snake_highscores = [
            serialize_snake_highscore(highscore)
            for highscore in SnakeHighScore.objects.filter(user=request.user).order_by("-score", "-length", "-achieved_at")[:60]
        ]

    return render(request, "app/snake_powerups.html", {
        "snake_text": snake_text,
        "snake_highscores": snake_highscores,
    })


@login_required
@require_POST
def snake_score_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungueltige Anfrage."), status=400)

    settings = normalize_snake_settings(payload.get("settings"))
    settings_key = snake_settings_key(settings)

    score = _snake_int(payload.get("score"), 0, 0, 999999999)
    length = _snake_int(payload.get("length"), 3, 1, 999999)
    fruits = _snake_int(payload.get("fruits"), 0, 0, 999999)
    moves = _snake_int(payload.get("moves"), 0, 0, 999999)
    duration_seconds = _snake_int(payload.get("durationSeconds"), 0, 0, 86400)
    runs = _snake_int(payload.get("runs"), 1, 1, 999999)

    if score <= 0:
        return api_error_response(_("Ungueltiger Snake-Score."), status=400)

    highscore, created = SnakeHighScore.objects.get_or_create(
        user=request.user,
        settings_key=settings_key,
        defaults={
            "settings": settings,
            "score": score,
            "length": length,
            "fruits": fruits,
            "moves": moves,
            "duration_seconds": duration_seconds,
            "runs": runs,
        },
    )

    is_new_highscore = created or score > highscore.score or (score == highscore.score and length > highscore.length)
    if not created:
        if is_new_highscore:
            highscore.settings = settings
            highscore.score = score
            highscore.length = length
            highscore.fruits = fruits
            highscore.moves = moves
            highscore.duration_seconds = duration_seconds
            highscore.runs = max(highscore.runs or 1, runs)
            highscore.save()
        else:
            update_fields = []
            merged_runs = max(highscore.runs or 1, runs)
            if merged_runs != highscore.runs:
                highscore.runs = merged_runs
                update_fields.append("runs")
            if highscore.settings != settings:
                highscore.settings = settings
                update_fields.append("settings")
            if update_fields:
                highscore.save(update_fields=update_fields)

    mark_active_game(request.user, "snake_powerups")

    return JsonResponse({
        "status": "ok",
        "new_highscore": is_new_highscore,
        "highscore": serialize_snake_highscore(highscore),
    })


NEBULA_FORGE_SAVE_COOLDOWN_SECONDS = 60
NEBULA_FORGE_MAX_SAVE_BYTES = 300_000


def serialize_nebula_forge_save(save):
    if not save:
        return None

    return {
        "flux": save.flux,
        "lifetime_flux": save.lifetime_flux,
        "total_lifetime_flux": save.total_lifetime_flux,
        "cps": save.cps,
        "manual_power": save.manual_power,
        "prestige_level": save.prestige_level,
        "shards": save.shards,
        "achievements_count": save.achievements_count,
        "upgrades_count": save.upgrades_count,
        "buildings_count": save.buildings_count,
        "updated_at": save.updated_at.isoformat() if save.updated_at else None,
        "last_manual_save": save.last_manual_save.isoformat() if save.last_manual_save else None,
    }


def nebula_forge_save_countdown(save):
    if not save or not save.last_manual_save:
        return 0

    elapsed = django_timezone.now() - save.last_manual_save
    remaining = NEBULA_FORGE_SAVE_COOLDOWN_SECONDS - int(elapsed.total_seconds())
    return max(0, remaining)


@ensure_csrf_cookie
def nebula_forge_tycoon(request):
    mark_active_game(request.user, "nebula_forge_tycoon")
    return render(request, "app/nebula_forge_tycoon.html")


@login_required
@require_POST
def nebula_forge_tycoon_activity_api(request):
    action = request.POST.get("action", "mark")

    if action == "clear":
        clear_active_game(request.user, "nebula_forge_tycoon")
    else:
        mark_active_game(request.user, "nebula_forge_tycoon")

    return JsonResponse({"status": "ok"})


@login_required
def nebula_forge_tycoon_load_api(request):
    mark_active_game(request.user, "nebula_forge_tycoon")
    save = NebulaForgeTycoonSave.objects.filter(user=request.user).first()

    return JsonResponse({
        "status": "ok",
        "save": serialize_nebula_forge_save(save),
        "save_data": save.save_data if save else None,
        "next_save_in_seconds": nebula_forge_save_countdown(save),
    })


@login_required
@require_POST
def nebula_forge_tycoon_save_api(request):
    mark_active_game(request.user, "nebula_forge_tycoon")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungültige Anfrage."), status=400)

    save_data = payload.get("save_data")
    if not isinstance(save_data, dict):
        return api_error_response(_("Ungültiger Nebula-Forge-Spielstand."), status=400)

    try:
        serialized_size = len(json.dumps(save_data, separators=(",", ":")))
    except (TypeError, ValueError):
        return api_error_response(_("Ungültiger Nebula-Forge-Spielstand."), status=400)

    if serialized_size > NEBULA_FORGE_MAX_SAVE_BYTES:
        return api_error_response(_("Der Nebula-Forge-Spielstand ist zu groß."), status=400)

    try:
        flux = float(payload.get("flux") or 0)
        lifetime_flux = float(payload.get("lifetime_flux") or 0)
        total_lifetime_flux = float(payload.get("total_lifetime_flux") or 0)
        cps = float(payload.get("cps") or 0)
        manual_power = float(payload.get("manual_power") or 1)
        prestige_level = int(payload.get("prestige_level") or 1)
        shards = int(payload.get("shards") or 0)
        achievements_count = int(payload.get("achievements_count") or 0)
        upgrades_count = int(payload.get("upgrades_count") or 0)
        buildings_count = int(payload.get("buildings_count") or 0)
    except (TypeError, ValueError):
        return api_error_response(_("Ungültige Nebula-Forge-Werte."), status=400)

    numeric_values = (flux, lifetime_flux, total_lifetime_flux, cps, manual_power)
    if not all(math.isfinite(value) for value in numeric_values):
        return api_error_response(_("Ungültige Nebula-Forge-Werte."), status=400)

    if flux < 0 or lifetime_flux < 0 or total_lifetime_flux < 0 or cps < 0 or manual_power < 0 or prestige_level < 1:
        return api_error_response(_("Ungültige Nebula-Forge-Werte."), status=400)

    save = NebulaForgeTycoonSave.objects.filter(user=request.user).first()
    remaining = nebula_forge_save_countdown(save)
    if remaining > 0:
        return JsonResponse({
            "status": "error",
            "message": _("Du kannst Nebula Forge Tycoon nur einmal pro Minute in der Datenbank speichern."),
            "next_save_in_seconds": remaining,
            "save": serialize_nebula_forge_save(save),
        }, status=429)

    manual_saved_at = django_timezone.now()
    save_data["databaseSavedAt"] = int(manual_saved_at.timestamp() * 1000)

    defaults = {
        "save_data": save_data,
        "flux": max(0, flux),
        "lifetime_flux": max(0, lifetime_flux),
        "total_lifetime_flux": max(0, total_lifetime_flux),
        "cps": max(0, cps),
        "manual_power": max(0, manual_power),
        "prestige_level": max(1, prestige_level),
        "shards": max(0, shards),
        "achievements_count": max(0, min(achievements_count, 500)),
        "upgrades_count": max(0, min(upgrades_count, 500)),
        "buildings_count": max(0, buildings_count),
        "last_manual_save": manual_saved_at,
    }

    save, _created = NebulaForgeTycoonSave.objects.update_or_create(
        user=request.user,
        defaults=defaults,
    )

    return JsonResponse({
        "status": "ok",
        "save": serialize_nebula_forge_save(save),
        "save_data": save.save_data,
        "next_save_in_seconds": NEBULA_FORGE_SAVE_COOLDOWN_SECONDS,
    })


def serialize_2048_highscore(highscore):
    if not highscore:
        return None

    return {
        "score": highscore.score,
        "display_score": highscore.display_score,
        "best_tile": highscore.best_tile,
        "moves": highscore.moves,
        "duration_seconds": highscore.duration_seconds,
        "duration_label": highscore.duration_label,
        "won": highscore.won,
        "games_played": highscore.games_played,
        "achieved_at": date_format(highscore.achieved_at, "d.m.Y H:i"),
    }


@ensure_csrf_cookie
def game_2048(request):
    mark_active_game(request.user, "2048")
    return render(request, "app/game_2048.html", {
        "highscore": serialize_2048_highscore(
            Game2048HighScore.objects.filter(user=request.user).first() if request.user.is_authenticated else None
        ),
    })


def _touch_2048_activity(user):
    mark_active_game(user, "2048")


@login_required
@require_POST
def game_2048_activity_api(request):
    _touch_2048_activity(request.user)
    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def game_2048_score_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungueltige Anfrage."), status=400)

    try:
        score = int(payload.get("score") or 0)
        best_tile = int(payload.get("best_tile") or 2)
        moves = int(payload.get("moves") or 0)
        duration_seconds = int(payload.get("duration_seconds") or 0)
    except (TypeError, ValueError):
        return api_error_response(_("Ungueltiger 2048-Score."), status=400)

    won = bool(payload.get("won"))
    if score < 0 or best_tile < 2 or moves < 0 or duration_seconds < 0:
        return api_error_response(_("Ungueltiger 2048-Score."), status=400)

    best_tile = min(best_tile, 131072)
    score = min(score, 999999999)
    moves = min(moves, 999999)
    duration_seconds = min(duration_seconds, 86400)
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}

    highscore, created = Game2048HighScore.objects.get_or_create(
        user=request.user,
        defaults={
            "score": score,
            "best_tile": best_tile,
            "moves": moves,
            "duration_seconds": duration_seconds,
            "won": won,
            "games_played": 1,
            "details": details,
        },
    )

    is_new_highscore = created or score > highscore.score or (score == highscore.score and best_tile > highscore.best_tile)
    if not created:
        highscore.games_played += 1
        if is_new_highscore:
            highscore.score = score
            highscore.best_tile = best_tile
            highscore.moves = moves
            highscore.duration_seconds = duration_seconds
            highscore.details = details
        highscore.won = highscore.won or won
        highscore.save()

    _touch_2048_activity(request.user)

    return JsonResponse({
        "status": "ok",
        "new_highscore": is_new_highscore,
        "highscore": serialize_2048_highscore(highscore),
    })


def format_cookie_score(value):
    value = max(0, float(value or 0))
    suffixes = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]

    if value < 1000:
        return str(int(value))

    tier = 0
    while value >= 1000 and tier < len(suffixes) - 1:
        value /= 1000
        tier += 1

    digits = 0 if value >= 100 else 1 if value >= 10 else 2
    return f"{value:.{digits}f}{suffixes[tier]}"


def serialize_cookie_clicker_highscore(highscore):
    if not highscore:
        return None

    return {
        "score": highscore.score,
        "display_score": highscore.display_score,
        "cps": highscore.cps,
        "click_power": highscore.click_power,
        "stardust": highscore.stardust,
        "ascensions": highscore.ascensions,
        "achievements_count": highscore.achievements_count,
        "upgrades_count": highscore.upgrades_count,
        "buildings_count": highscore.buildings_count,
        "achieved_at": date_format(highscore.achieved_at, "d.m.Y H:i"),
    }


@ensure_csrf_cookie
def cookie_clicker(request):
    mark_active_game(request.user, "cookie_cosmos")
    return render(request, "app/cookie_clicker.html")


COOKIE_COSMOS_V2_SAVE_COOLDOWN_SECONDS = 60
COOKIE_COSMOS_V2_MAX_SAVE_BYTES = 300_000


def serialize_cookie_cosmos_v2_save(save):
    if not save:
        return None

    return {
        "cookies": save.cookies,
        "lifetime_cookies": save.lifetime_cookies,
        "cps": save.cps,
        "click_power": save.click_power,
        "prestige_level": save.prestige_level,
        "prestige_crumbs": save.prestige_crumbs,
        "achievements_count": save.achievements_count,
        "upgrades_count": save.upgrades_count,
        "buildings_count": save.buildings_count,
        "updated_at": save.updated_at.isoformat() if save.updated_at else None,
        "last_manual_save": save.last_manual_save.isoformat() if save.last_manual_save else None,
    }


def cookie_cosmos_v2_save_countdown(save):
    if not save or not save.last_manual_save:
        return 0

    elapsed = django_timezone.now() - save.last_manual_save
    remaining = COOKIE_COSMOS_V2_SAVE_COOLDOWN_SECONDS - int(elapsed.total_seconds())
    return max(0, remaining)


@ensure_csrf_cookie
def cookie_cosmos_v2(request):
    mark_active_game(request.user, "cookie_cosmos_v2")
    return render(request, "app/cookie_cosmos_v2.html")


@login_required
def cookie_cosmos_v2_load_api(request):
    mark_active_game(request.user, "cookie_cosmos_v2")
    save = CookieCosmosV2Save.objects.filter(user=request.user).first()

    return JsonResponse({
        "status": "ok",
        "save": serialize_cookie_cosmos_v2_save(save),
        "save_data": save.save_data if save else None,
        "next_save_in_seconds": cookie_cosmos_v2_save_countdown(save),
    })


@login_required
@require_POST
def cookie_cosmos_v2_save_api(request):
    mark_active_game(request.user, "cookie_cosmos_v2")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungültige Anfrage."), status=400)

    save_data = payload.get("save_data")
    if not isinstance(save_data, dict):
        return api_error_response(_("Ungültiger Cookie-Cosmos-V2-Spielstand."), status=400)

    try:
        serialized_size = len(json.dumps(save_data, separators=(",", ":")))
    except (TypeError, ValueError):
        return api_error_response(_("Ungültiger Cookie-Cosmos-V2-Spielstand."), status=400)

    if serialized_size > COOKIE_COSMOS_V2_MAX_SAVE_BYTES:
        return api_error_response(_("Der Cookie-Cosmos-V2-Spielstand ist zu groß."), status=400)

    try:
        cookies = float(payload.get("cookies") or 0)
        lifetime_cookies = float(payload.get("lifetime_cookies") or 0)
        cps = float(payload.get("cps") or 0)
        click_power = float(payload.get("click_power") or 1)
        prestige_level = int(payload.get("prestige_level") or 1)
        prestige_crumbs = int(payload.get("prestige_crumbs") or 0)
        achievements_count = int(payload.get("achievements_count") or 0)
        upgrades_count = int(payload.get("upgrades_count") or 0)
        buildings_count = int(payload.get("buildings_count") or 0)
    except (TypeError, ValueError):
        return api_error_response(_("Ungültige Cookie-Cosmos-V2-Werte."), status=400)

    numeric_values = (cookies, lifetime_cookies, cps, click_power)
    if not all(math.isfinite(value) for value in numeric_values):
        return api_error_response(_("Ungültige Cookie-Cosmos-V2-Werte."), status=400)

    if cookies < 0 or lifetime_cookies < 0 or cps < 0 or click_power < 0 or prestige_level < 1:
        return api_error_response(_("Ungültige Cookie-Cosmos-V2-Werte."), status=400)

    save = CookieCosmosV2Save.objects.filter(user=request.user).first()
    remaining = cookie_cosmos_v2_save_countdown(save)
    if remaining > 0:
        return JsonResponse({
            "status": "error",
            "message": _("Du kannst Cookie Cosmos V2 nur einmal pro Minute in der Datenbank speichern."),
            "next_save_in_seconds": remaining,
            "save": serialize_cookie_cosmos_v2_save(save),
        }, status=429)

    now = django_timezone.now()
    defaults = {
        "save_data": save_data,
        "cookies": max(0, cookies),
        "lifetime_cookies": max(0, lifetime_cookies),
        "cps": max(0, cps),
        "click_power": max(0, click_power),
        "prestige_level": max(1, prestige_level),
        "prestige_crumbs": max(0, prestige_crumbs),
        "achievements_count": max(0, min(achievements_count, 500)),
        "upgrades_count": max(0, min(upgrades_count, 500)),
        "buildings_count": max(0, buildings_count),
        "last_manual_save": now,
    }

    save, _created = CookieCosmosV2Save.objects.update_or_create(
        user=request.user,
        defaults=defaults,
    )

    return JsonResponse({
        "status": "ok",
        "save": serialize_cookie_cosmos_v2_save(save),
        "next_save_in_seconds": COOKIE_COSMOS_V2_SAVE_COOLDOWN_SECONDS,
    })


@login_required
@require_POST
def cookie_clicker_score_api(request):
    mark_active_game(request.user, "cookie_cosmos")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error_response(_("Ungueltige Anfrage."), status=400)

    try:
        score = float(payload.get("score") or 0)
        cps = float(payload.get("cps") or 0)
        click_power = float(payload.get("click_power") or 0)
        stardust = int(payload.get("stardust") or 0)
        ascensions = int(payload.get("ascensions") or 0)
        achievements_count = int(payload.get("achievements_count") or 0)
        upgrades_count = int(payload.get("upgrades_count") or 0)
        buildings_count = int(payload.get("buildings_count") or 0)
    except (TypeError, ValueError):
        return api_error_response(_("Ung\u00fcltiger Cookie-Cosmos-Score."), status=400)

    if not all(math.isfinite(value) for value in (score, cps, click_power)) or score < 0 or cps < 0 or click_power < 0:
        return api_error_response(_("Ung\u00fcltiger Cookie-Cosmos-Score."), status=400)

    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    try:
        current_cookies = float(payload.get("current_cookies", details.get("current_cookies", score)) or 0)
    except (TypeError, ValueError):
        current_cookies = score

    if not math.isfinite(current_cookies) or current_cookies < 0:
        current_cookies = 0

    details = {
        **details,
        "current_cookies": current_cookies,
        "record_cookies": score,
    }
    display_score = str(payload.get("display_score") or format_cookie_score(score))[:80]

    highscore, created = CookieClickerHighScore.objects.get_or_create(
        user=request.user,
        defaults={
            "score": score,
            "display_score": display_score,
            "cps": cps,
            "click_power": click_power,
            "stardust": max(0, stardust),
            "ascensions": max(0, ascensions),
            "achievements_count": max(0, min(achievements_count, 500)),
            "upgrades_count": max(0, min(upgrades_count, 500)),
            "buildings_count": max(0, buildings_count),
            "details": details,
        },
    )

    is_new_highscore = created or score > highscore.score

    if not created:
        update_fields = [
            "cps",
            "click_power",
            "stardust",
            "ascensions",
            "achievements_count",
            "upgrades_count",
            "buildings_count",
            "details",
        ]

        if is_new_highscore:
            highscore.score = score
            highscore.display_score = display_score
            update_fields.extend(["score", "display_score", "achieved_at"])

        highscore.cps = cps
        highscore.click_power = click_power
        highscore.stardust = max(0, stardust)
        highscore.ascensions = max(0, ascensions)
        highscore.achievements_count = max(0, min(achievements_count, 500))
        highscore.upgrades_count = max(0, min(upgrades_count, 500))
        highscore.buildings_count = max(0, buildings_count)
        saved_details = highscore.details if isinstance(highscore.details, dict) else {}
        highscore.details = {**saved_details, **details}
        highscore.save(update_fields=update_fields)

    return JsonResponse({
        "status": "ok",
        "new_highscore": is_new_highscore,
        "highscore": serialize_cookie_clicker_highscore(highscore),
    })


VOICEMOD_ALLOWED_ACTIONS = {
    "getVoices",
    "getCurrentVoice",
    "getVoiceChangerStatus",
    "toggleVoiceChanger",
    "toggleHearMyVoice",
    "toggleMuteMic",
    "selectRandomVoice",
    "loadVoice",
}

VOICEMOD_RANDOM_MODES = {"FreeVoices", "AllVoices", "FavoriteVoices"}


@ensure_csrf_cookie
def stream_deck(request):
    return render(request, "app/stream_deck.html", {
        "spotify_client_id": get_env_value("SPOTIFY_CLIENT_ID") or "",
        "spotify_redirect_uri": get_env_value("SPOTIFY_REDIRECT_URI") or request.build_absolute_uri(request.path),
    })


@login_required
@require_POST
def stream_deck_voicemod_action(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return api_error_response(_("Ungueltige Anfrage."), status=400)

    action = str(payload.get("action") or "").strip()

    if action not in VOICEMOD_ALLOWED_ACTIONS:
        return api_error_response(_("Unbekannte Voicemod Aktion."), status=400)

    action_payload = _voicemod_action_payload(action, payload.get("payload") if isinstance(payload.get("payload"), dict) else {})

    if action_payload is None:
        return api_error_response(_("Voicemod Aktion unvollstaendig."), status=400)

    request_api_key = str(payload.get("apiKey") or "").strip()
    api_key = request_api_key[:512]

    if not api_key:
        return api_error_response(_("Kein Voicemod API-Key verbunden."), status=400)

    host = (get_env_value("VOICEMOD_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    ports = parse_voicemod_ports(get_env_value("VOICEMOD_PORTS"))

    try:
        response = send_voicemod_action(api_key, action, action_payload, host=host, ports=ports)
    except VoicemodError as exc:
        return api_error_response(str(exc), status=exc.status_code)

    return JsonResponse({
        "status": "ok",
        "action": action,
        "response": response,
    })


def _voicemod_action_payload(action, payload):
    if action == "loadVoice":
        voice_id = str(payload.get("voiceID") or "").strip()

        if not voice_id:
            return None

        return {"voiceID": voice_id[:120]}

    if action == "selectRandomVoice":
        mode = str(payload.get("mode") or "FreeVoices").strip()

        if mode not in VOICEMOD_RANDOM_MODES:
            mode = "FreeVoices"

        return {"mode": mode}

    return {}


@login_required
def color_palette_tool_view(request):
    return render(request, "app/color_palette_tool.html")


def randomizer_tools_view(request):
    return render(request, "app/randomizer_tools.html")
