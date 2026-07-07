import calendar
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from ..models import VacationHoliday, VacationPeriod, VacationYearSetting
from ..vacation_utils import FULL_DAY, HALF_DAY, ZERO_DAY, clip_range_to_year, dates_between, vacation_day_stats


HOLIDAY_DATE_FORMATS = (
    ("%Y-%m-%d", True),
    ("%d.%m.%Y", True),
    ("%d.%m.%y", True),
    ("%d.%m.", False),
    ("%d.%m", False),
)


def _selected_year(request):
    raw_year = request.POST.get("year") or request.GET.get("year") or timezone.localdate().year
    try:
        year = int(raw_year)
    except (TypeError, ValueError):
        return timezone.localdate().year
    return max(1900, min(year, 2200))


def _selected_month(request, selected_year):
    raw_month = request.POST.get("month") or request.GET.get("month")
    try:
        month = int(raw_month)
    except (TypeError, ValueError):
        today = timezone.localdate()
        return today.month if selected_year == today.year else 1
    return max(1, min(month, 12))


def _month_shift(year, month, offset):
    month_index = month - 1 + offset
    shifted_year = year + month_index // 12
    shifted_month = month_index % 12 + 1
    return shifted_year, shifted_month


def _planner_url(year, month=None, anchor=""):
    query = f"?year={year}"
    if month:
        query += f"&month={month}"
    return f"{reverse('vacation_planner')}{query}{anchor}"


def _planner_redirect(year, month=None, anchor=""):
    return redirect(_planner_url(year, month, anchor))


def parse_holiday_date(value, default_year=None):
    value = str(value or "").strip()
    if not value:
        raise ValueError("empty")

    for date_format, includes_year in HOLIDAY_DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, date_format).date()
        except ValueError:
            continue

        if includes_year:
            return parsed

        if default_year is None:
            raise ValueError("missing-year")

        return parsed.replace(year=int(default_year))

    raise ValueError("invalid")


def parse_holiday_line(line, default_year):
    cleaned = " ".join(str(line or "").strip().split())
    if not cleaned:
        return None

    date_token, _, raw_name = cleaned.partition(" ")
    date_token = date_token.strip(" ,;:")
    date_value = parse_holiday_date(date_token, default_year=default_year)
    name = raw_name.strip(" -:") or _("Feiertag")
    return date_value, str(name)[:100]


def calculate_vacation_days(start_date, end_date, holiday_dates):
    return vacation_day_stats(start_date, end_date, holiday_dates)


def clip_period_to_year(start_date, end_date, year):
    return clip_range_to_year(start_date, end_date, year)


def vacation_status_for_period(period, today):
    if period.start_date > today:
        return "planned", _("Geplant")
    if period.end_date < today:
        return "taken", _("Genommen")
    return "current", _("Aktuell")


def build_vacation_period_rows(periods, selected_year, holiday_dates, today):
    rows = []
    total_days = ZERO_DAY
    taken_days = ZERO_DAY
    planned_days = ZERO_DAY

    for period in periods:
        clipped = clip_period_to_year(period.start_date, period.end_date, selected_year)
        if clipped is None:
            continue

        clipped_start, clipped_end = clipped
        stats = calculate_vacation_days(clipped_start, clipped_end, holiday_dates)
        period_days = stats["vacation_days"]
        period_taken_days = ZERO_DAY

        if clipped_start <= today:
            taken_end = min(clipped_end, today)
            period_taken_days = calculate_vacation_days(clipped_start, taken_end, holiday_dates)["vacation_days"]

        period_planned_days = max(ZERO_DAY, period_days - period_taken_days)
        status_key, status_label = vacation_status_for_period(period, today)

        rows.append({
            "period": period,
            "clipped_start": clipped_start,
            "clipped_end": clipped_end,
            "vacation_days": period_days,
            "taken_days": period_taken_days,
            "planned_days": period_planned_days,
            "status_key": status_key,
            "status_label": status_label,
            "badge_label": period.note or status_label,
        })

        total_days += period_days
        taken_days += period_taken_days
        planned_days += period_planned_days

    return rows, {
        "total_days": total_days,
        "taken_days": taken_days,
        "planned_days": planned_days,
        "period_count": len(rows),
    }


def _year_bounds(year):
    return date(year, 1, 1), date(year, 12, 31)


def _vacation_periods_for_year(user, year):
    year_start, year_end = _year_bounds(year)
    return (
        VacationPeriod.objects
        .filter(user=user, start_date__lte=year_end, end_date__gte=year_start)
        .order_by("start_date", "created_at")
    )


def _saved_year_options(user, selected_year):
    today = timezone.localdate()
    years = {today.year - 1, today.year, today.year + 1, selected_year}
    years.update(VacationYearSetting.objects.filter(user=user).values_list("year", flat=True))
    years.update(VacationHoliday.objects.filter(user=user).values_list("year", flat=True))

    for start_date, end_date in VacationPeriod.objects.filter(user=user).values_list("start_date", "end_date"):
        years.update(range(start_date.year, end_date.year + 1))

    return sorted(years)


def _parse_total_days(value):
    try:
        total_days = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid")

    if total_days < 0 or total_days > 366:
        raise ValueError("out-of-range")
    return total_days


def _holiday_deduction_for(holiday):
    return HALF_DAY if holiday.is_half_day else FULL_DAY


def _holiday_label(holiday):
    if holiday.is_half_day:
        return _("%(name)s (halber Feiertag)") % {"name": holiday.name}
    return holiday.name


def _vacation_payload(request, selected_year):
    title = (request.POST.get("vacation_title") or "").strip() or "Urlaub"
    note = (request.POST.get("vacation_note") or "").strip()[:500]

    try:
        start_date = parse_holiday_date(request.POST.get("vacation_start"), default_year=selected_year)
        end_date = parse_holiday_date(request.POST.get("vacation_end"), default_year=selected_year)
    except ValueError as exc:
        raise ValueError("invalid-date") from exc

    if end_date < start_date:
        raise ValueError("end-before-start")

    return title[:100], start_date, end_date, note


def _warn_about_overlap(request, start_date, end_date, excluded_id=None):
    overlaps = VacationPeriod.objects.filter(
        user=request.user,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if excluded_id:
        overlaps = overlaps.exclude(id=excluded_id)

    if overlaps.exists():
        messages.warning(request, _("Hinweis: Dieser Urlaub überschneidet sich mit einem vorhandenen Eintrag."))


def _build_month_calendar(year, month, vacation_rows, holidays_by_date, today):
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    grid_start = first_day
    while grid_start.weekday() != 0:
        grid_start = grid_start - timedelta(days=1)

    grid_end = last_day
    while grid_end.weekday() != 6:
        grid_end = grid_end + timedelta(days=1)

    weeks = []
    current_week = []
    vacation_periods = [row["period"] for row in vacation_rows]

    for current in dates_between(grid_start, grid_end):
        holiday_names = holidays_by_date.get(current, [])
        vacation_titles = [
            period.title
            for period in vacation_periods
            if period.start_date <= current <= period.end_date
        ]
        is_weekend = current.weekday() >= 5
        is_counted_vacation = bool(vacation_titles) and not is_weekend and not holiday_names
        labels = [current.strftime("%d.%m.%Y")]
        if vacation_titles:
            labels.append(_("Urlaub: %(titles)s") % {"titles": ", ".join(vacation_titles)})
        if holiday_names:
            labels.append(_("Feiertag: %(names)s") % {"names": ", ".join(holiday_names)})

        current_week.append({
            "date": current,
            "day": current.day,
            "is_current_month": current.month == month,
            "is_today": current == today,
            "is_weekend": is_weekend,
            "is_vacation": bool(vacation_titles),
            "is_counted_vacation": is_counted_vacation,
            "is_holiday": bool(holiday_names),
            "holiday_names": holiday_names,
            "vacation_titles": vacation_titles,
            "aria_label": " · ".join(labels),
        })

        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []

    return weeks


@login_required
def vacation_planner_view(request):
    selected_year = _selected_year(request)
    selected_month = _selected_month(request, selected_year)

    year_setting, _created = VacationYearSetting.objects.get_or_create(
        user=request.user,
        year=selected_year,
        defaults={"total_days": 30},
    )

    if request.method == "POST":
        action = request.POST.get("action")
        redirect_month = selected_month if request.POST.get("month") or request.GET.get("month") else None

        def post_redirect(year, anchor=""):
            return _planner_redirect(year, redirect_month, anchor if redirect_month else "")

        if action == "save_year_setting":
            try:
                year_setting.total_days = _parse_total_days(request.POST.get("total_days"))
            except ValueError:
                messages.error(request, _("Bitte gib Urlaubstage zwischen 0 und 366 ein."))
                return post_redirect(selected_year)

            year_setting.save(update_fields=["total_days", "updated_at"])
            messages.success(request, _("Urlaubstage für das Jahr wurden gespeichert."))
            return post_redirect(selected_year)

        if action == "add_holiday":
            holiday_name = (request.POST.get("holiday_name") or "").strip()[:100]
            is_half_day = request.POST.get("holiday_is_half_day") == "1"
            if not holiday_name:
                messages.error(request, _("Bitte gib einen Namen für den Feiertag ein."))
                return post_redirect(selected_year, "#vacation-holidays")

            try:
                holiday_date = parse_holiday_date(request.POST.get("holiday_date"), default_year=selected_year)
            except ValueError:
                messages.error(request, _("Bitte gib ein gültiges Feiertagsdatum ein."))
                return post_redirect(selected_year, "#vacation-holidays")

            VacationHoliday.objects.update_or_create(
                user=request.user,
                year=holiday_date.year,
                date=holiday_date,
                defaults={"name": holiday_name, "is_half_day": is_half_day},
            )
            messages.success(request, _("Feiertag wurde gespeichert."))
            return post_redirect(holiday_date.year, "#vacation-holidays")

        if action == "update_holiday":
            holiday = get_object_or_404(VacationHoliday, id=request.POST.get("holiday_id"), user=request.user)
            holiday_name = (request.POST.get("holiday_name") or "").strip()[:100]
            is_half_day = request.POST.get("holiday_is_half_day") == "1"
            if not holiday_name:
                messages.error(request, _("Bitte gib einen Namen für den Feiertag ein."))
                return post_redirect(selected_year, "#vacation-holidays")

            try:
                holiday_date = parse_holiday_date(request.POST.get("holiday_date"), default_year=selected_year)
            except ValueError:
                messages.error(request, _("Bitte gib ein gültiges Feiertagsdatum ein."))
                return post_redirect(selected_year, "#vacation-holidays")

            duplicate = VacationHoliday.objects.filter(
                user=request.user,
                year=holiday_date.year,
                date=holiday_date,
            ).exclude(id=holiday.id).exists()
            if duplicate:
                messages.error(request, _("Für dieses Datum existiert bereits ein Feiertag."))
                return post_redirect(selected_year, "#vacation-holidays")

            holiday.name = holiday_name
            holiday.date = holiday_date
            holiday.is_half_day = is_half_day
            holiday.save()
            messages.success(request, _("Feiertag wurde aktualisiert."))
            return post_redirect(holiday_date.year, "#vacation-holidays")

        if action == "bulk_add_holidays":
            raw_lines = (request.POST.get("bulk_holidays") or "").splitlines()
            saved_count = 0
            errors = []
            for line_number, line in enumerate(raw_lines, start=1):
                if not line.strip():
                    continue
                try:
                    parsed = parse_holiday_line(line, selected_year)
                except ValueError:
                    errors.append(line_number)
                    continue
                if parsed is None:
                    continue
                holiday_date, holiday_name = parsed
                VacationHoliday.objects.update_or_create(
                    user=request.user,
                    year=holiday_date.year,
                    date=holiday_date,
                    defaults={"name": holiday_name, "is_half_day": False},
                )
                saved_count += 1

            if saved_count:
                messages.success(request, _("%(count)s Feiertage wurden gespeichert.") % {"count": saved_count})
            if errors:
                messages.warning(request, _("Einige Zeilen konnten nicht gelesen werden: %(lines)s.") % {
                    "lines": ", ".join(str(line) for line in errors[:5]),
                })
            if not saved_count and not errors:
                messages.info(request, _("Keine Feiertage zum Speichern gefunden."))
            return post_redirect(selected_year, "#vacation-holidays")

        if action == "delete_holiday":
            holiday = get_object_or_404(VacationHoliday, id=request.POST.get("holiday_id"), user=request.user)
            holiday_year = holiday.year
            holiday.delete()
            messages.success(request, _("Feiertag wurde gelöscht."))
            return post_redirect(holiday_year, "#vacation-holidays")

        if action == "add_vacation":
            try:
                vacation_title, start_date, end_date, vacation_note = _vacation_payload(request, selected_year)
            except ValueError as exc:
                error_messages = {
                    "missing-title": _("Bitte gib eine Bezeichnung für den Urlaub ein."),
                    "invalid-date": _("Bitte gib einen gültigen Urlaubszeitraum ein."),
                    "end-before-start": _("Das Enddatum darf nicht vor dem Startdatum liegen."),
                }
                messages.error(request, error_messages.get(str(exc), _("Bitte prüfe deine Eingaben.")))
                return post_redirect(selected_year, "#vacation-add")

            period = VacationPeriod.objects.create(
                user=request.user,
                title=vacation_title,
                start_date=start_date,
                end_date=end_date,
                note=vacation_note,
            )
            _warn_about_overlap(request, start_date, end_date, excluded_id=period.id)
            messages.success(request, _("Urlaub wurde gespeichert."))
            return post_redirect(start_date.year, "#vacation-list")

        if action == "update_vacation":
            period = get_object_or_404(VacationPeriod, id=request.POST.get("vacation_id"), user=request.user)
            try:
                vacation_title, start_date, end_date, vacation_note = _vacation_payload(request, selected_year)
            except ValueError as exc:
                error_messages = {
                    "missing-title": _("Bitte gib eine Bezeichnung für den Urlaub ein."),
                    "invalid-date": _("Bitte gib einen gültigen Urlaubszeitraum ein."),
                    "end-before-start": _("Das Enddatum darf nicht vor dem Startdatum liegen."),
                }
                messages.error(request, error_messages.get(str(exc), _("Bitte prüfe deine Eingaben.")))
                return post_redirect(selected_year, "#vacation-list")

            period.title = vacation_title
            period.start_date = start_date
            period.end_date = end_date
            period.note = vacation_note
            period.save()
            _warn_about_overlap(request, start_date, end_date, excluded_id=period.id)
            messages.success(request, _("Urlaub wurde aktualisiert."))
            return post_redirect(start_date.year, "#vacation-list")

        if action == "delete_vacation":
            period = get_object_or_404(VacationPeriod, id=request.POST.get("vacation_id"), user=request.user)
            period_year = selected_year if clip_period_to_year(period.start_date, period.end_date, selected_year) else period.year
            period.delete()
            messages.success(request, _("Urlaub wurde gelöscht."))
            return post_redirect(period_year, "#vacation-list")

    today = timezone.localdate()
    holidays = list(VacationHoliday.objects.filter(user=request.user, year=selected_year).order_by("date", "name"))
    holidays_by_date = {}
    holiday_deductions = {}
    for holiday in holidays:
        holidays_by_date.setdefault(holiday.date, []).append(_holiday_label(holiday))
        holiday_deductions[holiday.date] = _holiday_deduction_for(holiday)

    vacation_periods = list(_vacation_periods_for_year(request.user, selected_year))
    vacation_rows, entry_summary = build_vacation_period_rows(
        vacation_periods,
        selected_year,
        holiday_deductions,
        today,
    )

    planned_days = entry_summary["total_days"]
    remaining_days = year_setting.total_days - planned_days
    if year_setting.total_days:
        used_percent = min(100, max(0, round(planned_days / year_setting.total_days * 100)))
    else:
        used_percent = 100 if planned_days else 0

    previous_year, previous_month = _month_shift(selected_year, selected_month, -1)
    next_year, next_month = _month_shift(selected_year, selected_month, 1)
    month_anchor = "#vacation-calendar"
    month_weeks = _build_month_calendar(selected_year, selected_month, vacation_rows, holidays_by_date, today)
    month_start = date(selected_year, selected_month, 1)

    year_options = _saved_year_options(request.user, selected_year)
    all_user_holidays = VacationHoliday.objects.filter(user=request.user).order_by("date", "name")

    context = {
        "selected_year": selected_year,
        "selected_month": selected_month,
        "year_options": year_options,
        "year_setting": year_setting,
        "holidays": holidays,
        "holiday_count": len(holidays),
        "vacation_period_rows": vacation_rows,
        "entry_summary": entry_summary,
        "total_days": year_setting.total_days,
        "planned_days": planned_days,
        "remaining_days": remaining_days,
        "used_percent": used_percent,
        "remaining_percent": max(0, 100 - used_percent),
        "is_overplanned": remaining_days < 0,
        "month_label": date_format(month_start, "F Y"),
        "month_weeks": month_weeks,
        "weekday_labels": [_("Mo"), _("Di"), _("Mi"), _("Do"), _("Fr"), _("Sa"), _("So")],
        "previous_month_url": _planner_url(previous_year, previous_month, month_anchor),
        "next_month_url": _planner_url(next_year, next_month, month_anchor),
        "today_month_url": _planner_url(today.year, today.month, month_anchor),
        "today": today.isoformat(),
        "all_holidays": [
            {
                "date": holiday.date.isoformat(),
                "name": holiday.name,
                "year": holiday.year,
                "is_half_day": holiday.is_half_day,
                "deduction": 0.5 if holiday.is_half_day else 1,
            }
            for holiday in all_user_holidays
        ],
        "planner_labels": {
            "missingDates": _("Bitte Start- und Enddatum ausfüllen."),
            "invalidRange": _("Das Enddatum darf nicht vor dem Startdatum liegen."),
            "vacationDays": _("Urlaubstage"),
            "calendarDays": _("Kalendertage"),
            "weekends": _("Wochenenden"),
            "holidays": _("Feiertage"),
            "ready": _("Zeitraum auswählen, um die Urlaubstage zu prüfen."),
            "deleteVacation": _("Urlaub wirklich löschen?"),
            "deleteHoliday": _("Feiertag wirklich löschen?"),
            "overlap": _("Überschneidung mit einem gespeicherten Urlaub möglich."),
        },
    }
    return render(request, "app/vacation_planner.html", context)

