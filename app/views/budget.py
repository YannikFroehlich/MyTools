import calendar
import csv
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import BudgetCategory, BudgetEntry, BudgetMonth


MONEY_ZERO = Decimal("0.00")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ICON_RE = re.compile(r"^[a-zA-Z0-9\-\s]+$")

DEFAULT_BUDGET_CATEGORIES = [
    {"name": "Gehalt", "kind": BudgetCategory.KIND_INCOME, "icon": "fa-solid fa-briefcase", "color": "#16a34a"},
    {"name": "Nebenjob", "kind": BudgetCategory.KIND_INCOME, "icon": "fa-solid fa-hand-holding-dollar", "color": "#0f766e"},
    {"name": "Sonstiges", "kind": BudgetCategory.KIND_INCOME, "icon": "fa-solid fa-circle-plus", "color": "#0891b2"},
    {"name": "Essen", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-utensils", "color": "#f97316"},
    {"name": "Einkaufen", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-cart-shopping", "color": "#db2777"},
    {"name": "Freizeit", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-gamepad", "color": "#7c3aed"},
    {"name": "Auto", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-car", "color": "#ea580c"},
    {"name": "Schule", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-graduation-cap", "color": "#2563eb"},
    {"name": "Abos", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-repeat", "color": "#475569"},
    {"name": "Fixkosten", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-file-invoice-dollar", "color": "#dc2626"},
    {"name": "Sonstiges", "kind": BudgetCategory.KIND_EXPENSE, "icon": "fa-solid fa-wallet", "color": "#64748b"},
]


def _money(value, default=MONEY_ZERO):
    raw = str(value or "").strip().replace(".", "").replace(",", ".") if "," in str(value or "") else str(value or "").strip()
    if not raw:
        return default
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return default
    return max(amount, MONEY_ZERO)


def _parse_month(raw_month):
    today = timezone.localdate()
    if raw_month:
        try:
            parsed = date.fromisoformat(f"{raw_month}-01")
            return parsed.year, parsed.month
        except ValueError:
            pass
    return today.year, today.month


def _month_start(year, month):
    return date(year, month, 1)


def _add_months(base_date, offset):
    month_index = base_date.month - 1 + offset
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_bounds(year, month):
    start = _month_start(year, month)
    return start, _add_months(start, 1)


def _safe_day_in_month(year, month, day):
    return min(day, calendar.monthrange(year, month)[1])


def _month_query_value(year, month):
    return f"{year:04d}-{month:02d}"


def _redirect_to_budget(year, month):
    return f"{reverse('budget_tracker')}?month={_month_query_value(year, month)}"


def _ensure_default_budget_categories(user):
    for category in DEFAULT_BUDGET_CATEGORIES:
        BudgetCategory.objects.get_or_create(
            user=user,
            kind=category["kind"],
            name=category["name"],
            defaults={
                "icon": category["icon"],
                "color": category["color"],
                "is_default": True,
            },
        )


def _get_category_for_entry(user, category_id, entry_type):
    if not category_id:
        return BudgetCategory.objects.filter(user=user, kind=entry_type, name="Sonstiges").first()
    return BudgetCategory.objects.filter(user=user, kind=entry_type, id=category_id).first()


def _sum_amount(queryset):
    return queryset.aggregate(total=Sum("amount", default=MONEY_ZERO))["total"] or MONEY_ZERO


def _safe_percent(value, goal):
    if not goal or goal <= MONEY_ZERO:
        return 0
    return int(min(100, max(0, (value / goal) * Decimal("100"))))


@login_required
def budget_tracker_view(request):
    _ensure_default_budget_categories(request.user)

    year, month = _parse_month(request.GET.get("month"))
    month_start, next_month_start = _month_bounds(year, month)
    month_value = _month_query_value(year, month)

    budget_month, _created = BudgetMonth.objects.get_or_create(
        user=request.user,
        year=year,
        month=month,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "save_plan":
            budget_month.planned_income = _money(request.POST.get("planned_income"))
            budget_month.expense_limit = _money(request.POST.get("expense_limit"))
            budget_month.savings_goal = _money(request.POST.get("savings_goal"))
            budget_month.notes = (request.POST.get("notes") or "").strip()[:2000]
            budget_month.save()
            messages.success(request, _("Monatsbudget wurde gespeichert."))
            return redirect(_redirect_to_budget(year, month))

        if action == "add_entry":
            entry_type = request.POST.get("entry_type")
            if entry_type not in {BudgetEntry.TYPE_INCOME, BudgetEntry.TYPE_EXPENSE}:
                entry_type = BudgetEntry.TYPE_EXPENSE

            title = (request.POST.get("title") or "").strip()
            amount = _money(request.POST.get("amount"))
            try:
                entry_date = date.fromisoformat(request.POST.get("date") or month_start.isoformat())
            except ValueError:
                entry_date = month_start

            if not (month_start <= entry_date < next_month_start):
                entry_date = month_start

            category = _get_category_for_entry(request.user, request.POST.get("category"), entry_type)

            if not title:
                messages.error(request, _("Bitte gib einen Titel für die Buchung ein."))
                return redirect(_redirect_to_budget(year, month))

            if amount <= MONEY_ZERO:
                messages.error(request, _("Bitte gib einen Betrag größer als 0 ein."))
                return redirect(_redirect_to_budget(year, month))

            recurrence = BudgetEntry.RECURRENCE_MONTHLY if request.POST.get("recurrence") == BudgetEntry.RECURRENCE_MONTHLY else BudgetEntry.RECURRENCE_NONE

            BudgetEntry.objects.create(
                user=request.user,
                category=category,
                title=title[:120],
                amount=amount,
                entry_type=entry_type,
                date=entry_date,
                note=(request.POST.get("note") or "").strip()[:2000],
                is_fixed=bool(request.POST.get("is_fixed")),
                recurrence=recurrence,
            )
            messages.success(request, _("Buchung wurde hinzugefügt."))
            return redirect(_redirect_to_budget(year, month))

        if action == "delete_entry":
            entry = get_object_or_404(BudgetEntry, id=request.POST.get("entry_id"), user=request.user)
            entry.delete()
            messages.success(request, _("Buchung wurde gelöscht."))
            return redirect(_redirect_to_budget(year, month))

        if action == "add_category":
            kind = request.POST.get("kind")
            if kind not in {BudgetCategory.KIND_INCOME, BudgetCategory.KIND_EXPENSE}:
                kind = BudgetCategory.KIND_EXPENSE

            name = (request.POST.get("name") or "").strip()[:80]
            color = (request.POST.get("color") or "#2563eb").strip()
            icon = (request.POST.get("icon") or "fa-solid fa-wallet").strip()[:80]

            if not COLOR_RE.match(color):
                color = "#2563eb"
            if not ICON_RE.match(icon):
                icon = "fa-solid fa-wallet"

            if not name:
                messages.error(request, _("Bitte gib einen Kategorienamen ein."))
                return redirect(_redirect_to_budget(year, month))

            category, created = BudgetCategory.objects.get_or_create(
                user=request.user,
                kind=kind,
                name=name,
                defaults={"color": color, "icon": icon},
            )
            if created:
                messages.success(request, _("Kategorie wurde angelegt."))
            else:
                category.color = color
                category.icon = icon
                category.save(update_fields=["color", "icon"])
                messages.success(request, _("Kategorie wurde aktualisiert."))
            return redirect(_redirect_to_budget(year, month))

        if action == "delete_category":
            category = get_object_or_404(BudgetCategory, id=request.POST.get("category_id"), user=request.user)
            category.delete()
            messages.success(request, _("Kategorie wurde gelöscht. Vorhandene Buchungen bleiben erhalten."))
            return redirect(_redirect_to_budget(year, month))

        if action == "import_recurring":
            previous_start = _add_months(month_start, -1)
            previous_next = month_start
            recurring_entries = BudgetEntry.objects.filter(
                user=request.user,
                date__gte=previous_start,
                date__lt=previous_next,
            ).filter(Q(is_fixed=True) | Q(recurrence=BudgetEntry.RECURRENCE_MONTHLY))

            created_count = 0
            for old_entry in recurring_entries:
                new_date = date(year, month, _safe_day_in_month(year, month, old_entry.date.day))
                duplicate_exists = BudgetEntry.objects.filter(
                    user=request.user,
                    title=old_entry.title,
                    amount=old_entry.amount,
                    entry_type=old_entry.entry_type,
                    date=new_date,
                ).exists()
                if duplicate_exists:
                    continue
                BudgetEntry.objects.create(
                    user=request.user,
                    category=old_entry.category if old_entry.category and old_entry.category.user_id == request.user.id else None,
                    title=old_entry.title,
                    amount=old_entry.amount,
                    entry_type=old_entry.entry_type,
                    date=new_date,
                    note=old_entry.note,
                    is_fixed=old_entry.is_fixed,
                    recurrence=old_entry.recurrence,
                )
                created_count += 1

            if created_count:
                messages.success(request, _("%(count)s wiederkehrende Buchung(en) wurden übernommen.") % {"count": created_count})
            else:
                messages.info(request, _("Es wurden keine neuen wiederkehrenden Buchungen gefunden."))
            return redirect(_redirect_to_budget(year, month))

    categories = list(BudgetCategory.objects.filter(user=request.user))
    income_categories = [category for category in categories if category.kind == BudgetCategory.KIND_INCOME]
    expense_categories = [category for category in categories if category.kind == BudgetCategory.KIND_EXPENSE]

    entries = BudgetEntry.objects.filter(user=request.user, date__gte=month_start, date__lt=next_month_start).select_related("category")

    filter_type = request.GET.get("type", "all")
    filter_category = request.GET.get("category", "")
    if filter_category and not str(filter_category).isdigit():
        filter_category = ""
    search_query = (request.GET.get("q") or "").strip()

    filtered_entries = entries
    if filter_type in {BudgetEntry.TYPE_INCOME, BudgetEntry.TYPE_EXPENSE}:
        filtered_entries = filtered_entries.filter(entry_type=filter_type)
    if filter_category:
        filtered_entries = filtered_entries.filter(category_id=int(filter_category))
    if search_query:
        filtered_entries = filtered_entries.filter(Q(title__icontains=search_query) | Q(note__icontains=search_query))

    income_entries = entries.filter(entry_type=BudgetEntry.TYPE_INCOME)
    expense_entries = entries.filter(entry_type=BudgetEntry.TYPE_EXPENSE)
    fixed_expense_entries = expense_entries.filter(Q(is_fixed=True) | Q(recurrence=BudgetEntry.RECURRENCE_MONTHLY))

    total_income = _sum_amount(income_entries)
    total_expenses = _sum_amount(expense_entries)
    total_fixed_expenses = _sum_amount(fixed_expense_entries)
    balance = total_income - total_expenses
    planned_income = budget_month.planned_income or MONEY_ZERO
    expense_limit = budget_month.expense_limit or MONEY_ZERO
    savings_goal = budget_month.savings_goal or MONEY_ZERO
    limit_remaining = expense_limit - total_expenses if expense_limit > MONEY_ZERO else MONEY_ZERO

    category_totals = list(
        expense_entries.values(
            "category_id",
            "category__name",
            "category__color",
            "category__icon",
        )
        .annotate(total=Sum("amount", default=MONEY_ZERO))
        .order_by("-total")
    )

    for item in category_totals:
        item["name"] = item["category__name"] or _("Ohne Kategorie")
        item["color"] = item["category__color"] or "#64748b"
        item["icon"] = item["category__icon"] or "fa-solid fa-wallet"
        item["percent"] = _safe_percent(item["total"], total_expenses)

    today = timezone.localdate()
    default_entry_date = today if today.year == year and today.month == month else month_start
    days_in_month = calendar.monthrange(year, month)[1]
    if today.year == year and today.month == month:
        days_remaining = max(1, days_in_month - today.day + 1)
    else:
        days_remaining = days_in_month
    daily_remaining = (max(balance, MONEY_ZERO) / Decimal(days_remaining)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    trend_labels = []
    trend_income = []
    trend_expenses = []
    trend_balance = []
    for offset in range(-5, 1):
        trend_start = _add_months(month_start, offset)
        trend_next = _add_months(trend_start, 1)
        month_entries = BudgetEntry.objects.filter(user=request.user, date__gte=trend_start, date__lt=trend_next)
        month_income = _sum_amount(month_entries.filter(entry_type=BudgetEntry.TYPE_INCOME))
        month_expenses = _sum_amount(month_entries.filter(entry_type=BudgetEntry.TYPE_EXPENSE))
        trend_labels.append(trend_start.strftime("%m/%y"))
        trend_income.append(float(month_income))
        trend_expenses.append(float(month_expenses))
        trend_balance.append(float(month_income - month_expenses))

    context = {
        "budget_month": budget_month,
        "month_value": month_value,
        "month_label": date_format(month_start, "F Y"),
        "previous_month_value": _month_query_value(_add_months(month_start, -1).year, _add_months(month_start, -1).month),
        "next_month_value": _month_query_value(_add_months(month_start, 1).year, _add_months(month_start, 1).month),
        "income_categories": income_categories,
        "expense_categories": expense_categories,
        "all_categories": categories,
        "entries": filtered_entries,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_fixed_expenses": total_fixed_expenses,
        "balance": balance,
        "limit_remaining": limit_remaining,
        "daily_remaining": daily_remaining,
        "category_totals": category_totals,
        "expense_usage_percent": _safe_percent(total_expenses, expense_limit),
        "income_progress_percent": _safe_percent(total_income, planned_income),
        "savings_progress_percent": _safe_percent(max(balance, MONEY_ZERO), savings_goal),
        "filter_type": filter_type,
        "filter_category": filter_category,
        "search_query": search_query,
        "default_entry_date_iso": default_entry_date.isoformat(),
        "month_start_iso": month_start.isoformat(),
        "month_end_iso": date(year, month, days_in_month).isoformat(),
        "planned_income_value": f"{budget_month.planned_income:.2f}",
        "expense_limit_value": f"{budget_month.expense_limit:.2f}",
        "savings_goal_value": f"{budget_month.savings_goal:.2f}",
        "trend_json": json.dumps({
            "labels": trend_labels,
            "income": trend_income,
            "expenses": trend_expenses,
            "balance": trend_balance,
        }),
    }
    return render(request, "app/budget_tracker.html", context)


@login_required
def budget_tracker_export_csv(request):
    year, month = _parse_month(request.GET.get("month"))
    month_start, next_month_start = _month_bounds(year, month)
    entries = BudgetEntry.objects.filter(user=request.user, date__gte=month_start, date__lt=next_month_start).select_related("category")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="budget-{year:04d}-{month:02d}.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Datum", "Typ", "Titel", "Kategorie", "Betrag", "Fixkosten", "Wiederholung", "Notiz"])
    for entry in entries:
        writer.writerow([
            entry.date.isoformat(),
            entry.get_entry_type_display(),
            entry.title,
            entry.category.name if entry.category else "",
            str(entry.amount).replace(".", ","),
            "Ja" if entry.is_fixed else "Nein",
            entry.get_recurrence_display(),
            entry.note,
        ])
    return response
