from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import VacationHoliday, VacationPeriod


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
    if end_date < start_date:
        raise ValueError("end-before-start")

    holiday_dates = set(holiday_dates)
    total_days = (end_date - start_date).days + 1
    weekend_days = 0
    holiday_weekdays = 0
    vacation_days = 0

    for offset in range(total_days):
        current = start_date + timedelta(days=offset)
        if current.weekday() >= 5:
            weekend_days += 1
        elif current in holiday_dates:
            holiday_weekdays += 1
        else:
            vacation_days += 1

    return {
        "total_days": total_days,
        "weekend_days": weekend_days,
        "holiday_weekdays": holiday_weekdays,
        "vacation_days": vacation_days,
    }


def clip_period_to_year(start_date, end_date, year):
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    clipped_start = max(start_date, year_start)
    clipped_end = min(end_date, year_end)

    if clipped_end < clipped_start:
        return None

    return clipped_start, clipped_end


def vacation_status_for_period(period, today):
    if period.start_date > today:
        return "planned", _("Geplant")
    if period.end_date < today:
        return "taken", _("Genommen")
    return "current", _("Aktuell")


def build_vacation_period_rows(periods, selected_year, holiday_dates, today):
    rows = []
    total_days = 0
    taken_days = 0
    planned_days = 0

    for period in periods:
        clipped = clip_period_to_year(period.start_date, period.end_date, selected_year)
        if clipped is None:
            continue

        clipped_start, clipped_end = clipped
        stats = calculate_vacation_days(clipped_start, clipped_end, holiday_dates)
        period_days = stats["vacation_days"]
        period_taken_days = 0

        if clipped_start <= today:
            taken_end = min(clipped_end, today)
            period_taken_days = calculate_vacation_days(clipped_start, taken_end, holiday_dates)["vacation_days"]

        period_planned_days = max(0, period_days - period_taken_days)
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


def _planner_redirect(year):
    return redirect(f"{reverse('vacation_planner')}?year={year}")


@login_required
def vacation_planner_view(request):
    selected_year = _selected_year(request)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_holiday":
            holiday_name = (request.POST.get("holiday_name") or "").strip()[:100] or _("Feiertag")
            try:
                holiday_date = parse_holiday_date(request.POST.get("holiday_date"), default_year=selected_year)
            except ValueError:
                messages.error(request, _("Bitte gib ein gueltiges Feiertagsdatum ein."))
                return _planner_redirect(selected_year)

            VacationHoliday.objects.update_or_create(
                user=request.user,
                date=holiday_date,
                defaults={"name": holiday_name},
            )
            messages.success(request, _("Feiertag wurde gespeichert."))
            return _planner_redirect(holiday_date.year)

        if action == "add_vacation":
            vacation_title = (request.POST.get("vacation_title") or "").strip()[:100] or _("Urlaub")
            vacation_note = (request.POST.get("vacation_note") or "").strip()[:500]

            try:
                start_date = parse_holiday_date(request.POST.get("vacation_start"), default_year=selected_year)
                end_date = parse_holiday_date(request.POST.get("vacation_end"), default_year=selected_year)
            except ValueError:
                messages.error(request, _("Bitte gib einen gueltigen Urlaubszeitraum ein."))
                return _planner_redirect(selected_year)

            if end_date < start_date:
                messages.error(request, _("Das Enddatum muss nach dem Startdatum liegen."))
                return _planner_redirect(selected_year)

            VacationPeriod.objects.create(
                user=request.user,
                title=vacation_title,
                start_date=start_date,
                end_date=end_date,
                note=vacation_note,
            )
            messages.success(request, _("Urlaub wurde gespeichert."))
            return _planner_redirect(start_date.year)

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
                    date=holiday_date,
                    defaults={"name": holiday_name},
                )
                saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    _("%(count)s Feiertag wurde gespeichert.") % {"count": saved_count}
                    if saved_count == 1
                    else _("%(count)s Feiertage wurden gespeichert.") % {"count": saved_count},
                )

            if errors:
                messages.warning(
                    request,
                    _("Einige Zeilen konnten nicht gelesen werden: %(lines)s.") % {
                        "lines": ", ".join(str(line) for line in errors[:5])
                    },
                )

            if not saved_count and not errors:
                messages.info(request, _("Keine Feiertage zum Speichern gefunden."))

            return _planner_redirect(selected_year)

        if action == "delete_holiday":
            holiday = get_object_or_404(VacationHoliday, id=request.POST.get("holiday_id"), user=request.user)
            holiday_year = holiday.date.year
            holiday.delete()
            messages.success(request, _("Feiertag wurde geloescht."))
            return _planner_redirect(holiday_year)

        if action == "delete_vacation":
            period = get_object_or_404(VacationPeriod, id=request.POST.get("vacation_id"), user=request.user)
            period_year = selected_year if clip_period_to_year(period.start_date, period.end_date, selected_year) else period.start_date.year
            period.delete()
            messages.success(request, _("Urlaub wurde geloescht."))
            return _planner_redirect(period_year)

        if action == "clear_year":
            deleted_count, _details = VacationHoliday.objects.filter(user=request.user, date__year=selected_year).delete()
            if deleted_count:
                messages.success(request, _("Feiertage fuer dieses Jahr wurden geloescht."))
            else:
                messages.info(request, _("Fuer dieses Jahr waren keine Feiertage gespeichert."))
            return _planner_redirect(selected_year)

    all_holidays = list(VacationHoliday.objects.filter(user=request.user).order_by("date", "name"))
    all_periods = list(VacationPeriod.objects.filter(user=request.user).order_by("-start_date", "-created_at"))
    current_year = timezone.localdate().year
    today = timezone.localdate()
    saved_years = {holiday.date.year for holiday in all_holidays}
    for period in all_periods:
        saved_years.update(range(period.start_date.year, period.end_date.year + 1))

    year_options = sorted(saved_years | {selected_year, current_year - 1, current_year, current_year + 1, current_year + 2})
    holidays_for_year = [holiday for holiday in all_holidays if holiday.date.year == selected_year]
    holiday_dates = {holiday.date for holiday in all_holidays}
    vacation_period_rows, vacation_summary = build_vacation_period_rows(
        all_periods,
        selected_year,
        holiday_dates,
        today,
    )

    context = {
        "selected_year": selected_year,
        "year_options": year_options,
        "holidays": holidays_for_year,
        "holiday_count": len(holidays_for_year),
        "vacation_period_rows": vacation_period_rows,
        "vacation_summary": vacation_summary,
        "all_holidays": [
            {
                "date": holiday.date.isoformat(),
                "name": holiday.name,
                "year": holiday.date.year,
            }
            for holiday in all_holidays
        ],
        "today": today.isoformat(),
        "planner_labels": {
            "missingDates": _("Bitte Start- und Enddatum ausfuellen."),
            "invalidRange": _("Das Enddatum muss nach dem Startdatum liegen."),
            "ready": _("Gib Start und Ende ein, um deine Urlaubstage zu berechnen."),
            "vacationDays": _("benoetigte Urlaubstage"),
            "calendarDays": _("Kalendertage"),
            "weekends": _("Wochenendtage"),
            "holidays": _("Feiertage auf Werktagen"),
            "noHolidays": _("Keine gespeicherten Feiertage im Zeitraum."),
            "savedHoliday": _("Gespeicherter Feiertag"),
            "weekend": _("Wochenende"),
            "vacation": _("Urlaubstag"),
            "missingYearPrefix": _("Noch keine Feiertage gespeichert fuer"),
            "clearConfirm": _("Alle Feiertage fuer dieses Jahr loeschen?"),
        },
    }
    return render(request, "app/vacation_planner.html", context)
