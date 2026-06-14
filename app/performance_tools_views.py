from pathlib import Path
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import get_valid_filename
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import (
    ConnectFourGame,
    CookieClickerHighScore,
    FileShare,
    Friendship,
    HangmanLobby,
    HangmanPlayer,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    SkribbleStats,
    StadtLandFlussPlayer,
    TicTacToeGame,
    UserProfile,
)

MAX_SHARE_RECIPIENTS = 20
FILE_SHARE_EXPIRY_DAYS = {"1": 1, "7": 7, "30": 30}


def _display_name(user):
    return user.get_full_name() or user.username


def _human_size(size):
    size = float(size or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def _parse_download_limit(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return max(1, min(parsed, 1000))


def _parse_share_expiry(value):
    days = FILE_SHARE_EXPIRY_DAYS.get(str(value or "").strip())
    if not days:
        return None
    return timezone.now() + timedelta(days=days)


def _file_share_limit(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return {
        "size": profile.file_share_max_size,
        "label": profile.file_share_limit_label,
        "is_unlimited": profile.file_share_max_size is None,
    }


def _build_win_rows(model, cases, title, icon, limit=10):
    totals = {}
    for case in cases:
        winner_relation = case["winner"][:-3] if case["winner"].endswith("_id") else case["winner"]
        qs = (
            model.objects
            .filter(status=case["finished"], **{case["win_field"]: case["win_value"]})
            .filter(**{f"{winner_relation}__profile__privacy_show_highscores": True})
            .exclude(**{case["winner"]: None})
            .values(case["winner"])
            .annotate(total=Count("id"))
        )
        for row in qs:
            user_id = row[case["winner"]]
            totals[user_id] = totals.get(user_id, 0) + row["total"]

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    users = User.objects.in_bulk([user_id for user_id, _score in ranked])
    rows = []
    for index, (user_id, score) in enumerate(ranked, start=1):
        user = users.get(user_id)
        if not user:
            continue
        rows.append({"rank": index, "name": _display_name(user), "score": score, "detail": _("Siege")})
    return {"title": title, "icon": icon, "rows": rows}


def _decorate_leaderboards(boards):
    decorated = []
    for index, board in enumerate(boards):
        rows = board.get("rows") or []
        decorated.append({
            **board,
            "accent": f"leaderboard-accent-{(index % 4) + 1}",
            "top_row": rows[0] if rows else None,
            "row_count": len(rows),
        })
    return decorated


def _human_benchmark_rows(game, title, lower_is_better=False, limit=10):
    order = "score" if lower_is_better else "-score"
    qs = (
        HumanBenchmarkHighScore.objects.filter(game=game, user__profile__privacy_show_highscores=True)
        .select_related("user")
        .order_by(order, "achieved_at")[:limit]
    )
    rows = []
    for index, item in enumerate(qs, start=1):
        rows.append({
            "rank": index,
            "name": _display_name(item.user),
            "score": item.display_score,
            "detail": item.achieved_at.strftime("%d.%m.%Y"),
        })
    return {"title": title, "icon": "fa-solid fa-stopwatch", "rows": rows}


@login_required
def leaderboard_view(request):
    human_total = HumanBenchmarkScore.objects.count()
    multiplayer_games = (
        TicTacToeGame.objects.filter(status=TicTacToeGame.STATUS_FINISHED).count()
        + ConnectFourGame.objects.filter(status=ConnectFourGame.STATUS_FINISHED).count()
        + HangmanLobby.objects.filter(status=HangmanLobby.STATUS_FINISHED).count()
    )

    boards = [
        _human_benchmark_rows(HumanBenchmarkScore.GAME_REACTION, _("Reaktion"), lower_is_better=True),
        _human_benchmark_rows(HumanBenchmarkScore.GAME_AIM, _("Aim Trainer")),
        _human_benchmark_rows(HumanBenchmarkScore.GAME_TYPING, _("Typing Test")),
        _human_benchmark_rows(HumanBenchmarkScore.GAME_VISUAL, _("Visual Memory")),
    ]

    skribble_rows = []
    for index, stats in enumerate(
        SkribbleStats.objects.select_related("user")
        .filter(user__profile__privacy_show_highscores=True)
        .order_by("-games_won", "-total_score")[:10],
        start=1,
    ):
        skribble_rows.append({
            "rank": index,
            "name": _display_name(stats.user),
            "score": stats.games_won,
            "detail": _("Siege · %(score)s Punkte") % {"score": stats.total_score},
        })
    boards.append({"title": _("Skribble"), "icon": "fa-solid fa-pencil", "rows": skribble_rows})

    cookie_rows = []
    cookie_qs = (
        CookieClickerHighScore.objects
        .select_related("user")
        .filter(user__profile__privacy_show_highscores=True)
        .order_by("-score", "achieved_at")[:10]
    )
    for index, item in enumerate(cookie_qs, start=1):
        cookie_rows.append({
            "rank": index,
            "name": _display_name(item.user),
            "score": item.display_score,
            "detail": _("Cookie Cosmos Â· %(upgrades)s Upgrades") % {"upgrades": item.upgrades_count},
        })
    boards.append({"title": _("Cookie Cosmos"), "icon": "fa-solid fa-cookie-bite", "rows": cookie_rows})

    stadt_rows = []
    stadt_qs = (
        StadtLandFlussPlayer.objects.filter(user__profile__privacy_show_highscores=True)
        .values("user", "user__username", "user__first_name", "user__last_name")
        .annotate(total=Coalesce(Sum("score"), Value(0)), last_played=Max("last_seen"))
        .order_by("-total", "-last_played")[:10]
    )
    for index, row in enumerate(stadt_qs, start=1):
        name = f"{row['user__first_name']} {row['user__last_name']}".strip() or row["user__username"]
        stadt_rows.append({"rank": index, "name": name, "score": row["total"], "detail": _("Gesamtpunkte")})
    boards.append({"title": _("Stadt Land Fluss"), "icon": "fa-solid fa-font", "rows": stadt_rows})

    hangman_rows = []
    hangman_qs = (
        HangmanPlayer.objects.filter(user__profile__privacy_show_highscores=True)
        .values("user", "user__username", "user__first_name", "user__last_name")
        .annotate(total=Coalesce(Sum("score"), Value(0)), games=Count("id"))
        .order_by("-total", "-games")[:10]
    )
    for index, row in enumerate(hangman_qs, start=1):
        name = f"{row['user__first_name']} {row['user__last_name']}".strip() or row["user__username"]
        hangman_rows.append({"rank": index, "name": name, "score": row["total"], "detail": _("Punkte aus %(games)s Runden") % {"games": row["games"]}})
    boards.append({"title": _("Hangman"), "icon": "fa-solid fa-user-secret", "rows": hangman_rows})

    boards.append(_build_win_rows(TicTacToeGame, [
        {"winner": "player_x_id", "loser": "player_o_id", "finished": TicTacToeGame.STATUS_FINISHED, "win_field": "winner_symbol", "win_value": TicTacToeGame.SYMBOL_X},
        {"winner": "player_o_id", "loser": "player_x_id", "finished": TicTacToeGame.STATUS_FINISHED, "win_field": "winner_symbol", "win_value": TicTacToeGame.SYMBOL_O},
    ], _("Tic Tac Toe"), "fa-solid fa-xmark"))

    boards.append(_build_win_rows(ConnectFourGame, [
        {"winner": "player_red_id", "loser": "player_yellow_id", "finished": ConnectFourGame.STATUS_FINISHED, "win_field": "winner_disc", "win_value": ConnectFourGame.DISC_RED},
        {"winner": "player_yellow_id", "loser": "player_red_id", "finished": ConnectFourGame.STATUS_FINISHED, "win_field": "winner_disc", "win_value": ConnectFourGame.DISC_YELLOW},
    ], _("Vier gewinnt"), "fa-solid fa-circle-dot"))

    context = {
        "boards": _decorate_leaderboards(boards),
        "boards_total": len(boards),
        "human_total": human_total,
        "multiplayer_games": multiplayer_games,
        "players_total": User.objects.filter(is_active=True).count(),
        "visible_scores_total": sum(len(board.get("rows", [])) for board in boards),
    }
    return render(request, "app/leaderboard.html", context)


@login_required
def image_tools_view(request):
    return render(request, "app/image_tools.html")


def _friends_queryset(user):
    friend_ids = Friendship.friend_ids_for_user(user)
    return User.objects.filter(id__in=friend_ids, is_active=True).order_by("username")


@login_required
def file_share_view(request):
    share_limit = _file_share_limit(request.user)
    friends = _friends_queryset(request.user)
    own_shares = (
        FileShare.objects.filter(owner=request.user)
        .prefetch_related("recipients")
        .order_by("-created_at")
    )
    received_shares = (
        FileShare.objects.filter(recipients=request.user)
        .exclude(owner=request.user)
        .select_related("owner")
        .distinct()
        .order_by("-created_at")
    )

    return render(request, "app/file_share.html", {
        "friends": friends,
        "own_shares": Paginator(own_shares, 12).get_page(request.GET.get("own_page")),
        "received_shares": Paginator(received_shares, 12).get_page(request.GET.get("received_page")),
        "max_share_mb": share_limit["label"],
        "max_share_bytes": share_limit["size"] or "",
        "max_share_unlimited": share_limit["is_unlimited"],
    })


@login_required
@require_POST
def file_share_upload_view(request):
    share_limit = _file_share_limit(request.user)
    uploads = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not uploads:
        messages.error(request, _("Bitte wähle eine Datei aus."))
        return redirect("file_share")

    oversized = [
        upload
        for upload in uploads
        if share_limit["size"] is not None and upload.size > share_limit["size"]
    ]
    if oversized:
        messages.error(request, _("Die Datei ist zu groß. Maximal erlaubt sind %(size)s.") % {"size": share_limit["label"]})
        return redirect("file_share")

    selected_ids = request.POST.getlist("recipients")[:MAX_SHARE_RECIPIENTS]
    recipients = list(_friends_queryset(request.user).filter(id__in=selected_ids))
    is_public = request.POST.get("is_public_link") == "on"
    if not recipients and not is_public:
        messages.error(request, _("Wähle mindestens einen Freund oder aktiviere den privaten Link."))
        return redirect("file_share")

    password = str(request.POST.get("share_password") or "").strip()
    expires_at = _parse_share_expiry(request.POST.get("expires_in"))
    max_downloads = _parse_download_limit(request.POST.get("max_downloads"))

    created_count = 0
    for upload in uploads:
        safe_name = get_valid_filename(Path(upload.name).name)[:180] or "datei"
        share = FileShare.objects.create(
            owner=request.user,
            file=upload,
            original_name=safe_name,
            size=upload.size,
            content_type=getattr(upload, "content_type", "")[:120],
            token=get_random_string(40),
            is_public_link=is_public,
            password_hash=make_password(password) if password else "",
            expires_at=expires_at,
            max_downloads=max_downloads,
        )
        if recipients:
            share.recipients.set(recipients)
        created_count += 1

    if created_count == 1:
        messages.success(request, _("Datei wurde geteilt."))
    else:
        messages.success(request, _("%(count)s Dateien wurden geteilt.") % {"count": created_count})

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "redirect_url": reverse("file_share"), "count": created_count})
    return redirect("file_share")


def _has_direct_share_access(user, share):
    if not getattr(user, "is_authenticated", False):
        return False
    if share.owner_id == user.id:
        return True
    return share.recipients.filter(id=user.id).exists()


def _can_access_share(user, share):
    if _has_direct_share_access(user, share):
        return True
    return share.is_public_link


def file_share_download_view(request, token):
    share = get_object_or_404(FileShare.objects.select_related("owner"), token=token)
    if not _can_access_share(request.user, share):
        raise PermissionDenied
    if share.is_expired:
        return render(request, "app/file_share_access.html", {"share": share, "state": "expired"}, status=410)
    if share.download_limit_reached:
        return render(request, "app/file_share_access.html", {"share": share, "state": "limit"}, status=410)
    direct_access = _has_direct_share_access(request.user, share)
    session_key = f"file_share_access_{share.token}"
    if share.password_hash and not direct_access and not request.session.get(session_key):
        if request.method == "POST":
            password = str(request.POST.get("password") or "")
            if check_password(password, share.password_hash):
                request.session[session_key] = True
                return redirect(request.get_full_path())
            messages.error(request, _("Das Passwort ist nicht korrekt."))
        return render(request, "app/file_share_access.html", {"share": share, "state": "password"})
    if not share.file:
        raise Http404
    preview = request.GET.get("preview") == "1" and (share.is_image or share.is_pdf)
    if not preview:
        share.download_count = F("download_count") + 1
        share.last_downloaded_at = timezone.now()
        share.save(update_fields=["download_count", "last_downloaded_at"])
    response = FileResponse(share.file.open("rb"), as_attachment=not preview, filename=share.original_name)
    if share.content_type:
        response["Content-Type"] = share.content_type
    return response


@login_required
@require_POST
def file_share_delete_view(request, share_id):
    share = get_object_or_404(FileShare, id=share_id, owner=request.user)
    if share.file:
        share.file.delete(save=False)
    share.delete()
    messages.success(request, _("Datei wurde gelöscht."))
    return redirect("file_share")
