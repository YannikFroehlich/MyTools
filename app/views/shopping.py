import calendar
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..models import ShoppingItem, ShoppingList
from ..open_food_facts import ProductLookupUnavailable, lookup_product, normalize_barcode


DECIMAL_STEP = Decimal("0.01")
MAX_QUANTITY = Decimal("999999.99")
MAX_PRICE = Decimal("99999999.99")
ALLOWED_IMAGE_HOSTS = {"images.openfoodfacts.org", "static.openfoodfacts.org"}


def _default_list(user):
    shopping_list, _created = ShoppingList.objects.get_or_create(
        owner=user,
        is_default=True,
        defaults={"name": _("Mein Einkaufszettel")},
    )
    return shopping_list


def _parse_decimal(raw_value, *, required, maximum):
    raw = str(raw_value or "").strip().replace(" ", "")
    if not raw:
        if required:
            raise ValueError
        return None

    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")

    try:
        value = Decimal(raw).quantize(DECIMAL_STEP, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError from None
    if value <= 0 or value > maximum:
        raise ValueError
    return value


def _parse_optional_price(raw_value):
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    try:
        return _parse_decimal(raw, required=True, maximum=MAX_PRICE)
    except ValueError:
        if raw in {"0", "0,0", "0,00", "0.0", "0.00"}:
            return Decimal("0.00")
        raise


def _safe_product_image(raw_url):
    value = str(raw_url or "").strip()[:500]
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_IMAGE_HOSTS:
        return ""
    return value


def _next_recurrence_date(recurrence, base_date):
    if recurrence == ShoppingItem.RECURRENCE_WEEKLY:
        return base_date + timedelta(days=7)
    if recurrence == ShoppingItem.RECURRENCE_BIWEEKLY:
        return base_date + timedelta(days=14)
    if recurrence == ShoppingItem.RECURRENCE_MONTHLY:
        if base_date.month == 12:
            year, month = base_date.year + 1, 1
        else:
            year, month = base_date.year, base_date.month + 1
        day = min(base_date.day, calendar.monthrange(year, month)[1])
        return base_date.replace(year=year, month=month, day=day)
    return None


def _item_data(request):
    name = (request.POST.get("name") or "").strip()[:160]
    if not name:
        return None, _("Bitte gib einen Artikelnamen ein.")

    try:
        quantity = _parse_decimal(request.POST.get("quantity"), required=True, maximum=MAX_QUANTITY)
    except ValueError:
        return None, _("Die Menge muss größer als 0 sein.")

    try:
        unit_price = _parse_optional_price(request.POST.get("unit_price"))
    except ValueError:
        return None, _("Bitte gib einen gültigen Preis ein.")

    valid_units = {value for value, _label in ShoppingItem.UNIT_CHOICES}
    unit = request.POST.get("unit")
    if unit not in valid_units:
        unit = ShoppingItem.UNIT_PIECE

    valid_categories = {value for value, _label in ShoppingItem.CATEGORY_CHOICES}
    category = request.POST.get("category")
    if category not in valid_categories:
        category = ShoppingItem.CATEGORY_OTHER

    valid_recurrences = {value for value, _label in ShoppingItem.RECURRENCE_CHOICES}
    recurrence = request.POST.get("recurrence")
    if recurrence not in valid_recurrences:
        recurrence = ShoppingItem.RECURRENCE_NONE

    raw_barcode = request.POST.get("barcode") or ""
    barcode = normalize_barcode(raw_barcode) if raw_barcode.strip() else ""
    if raw_barcode.strip() and not barcode:
        return None, _("Der Barcode muss aus 8 bis 14 Ziffern bestehen.")

    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "category": category,
        "note": (request.POST.get("note") or "").strip()[:1000],
        "barcode": barcode,
        "brand": (request.POST.get("brand") or "").strip()[:120],
        "product_quantity": (request.POST.get("product_quantity") or "").strip()[:80],
        "image_url": _safe_product_image(request.POST.get("image_url")),
        "recurrence": recurrence,
    }, None


def _redirect_to_list():
    return redirect(reverse("shopping_list"))


@login_required
def shopping_list_view(request):
    shopping_list = _default_list(request.user)

    if request.method == "POST":
        data, error = _item_data(request)
        if error:
            messages.error(request, error)
            return _redirect_to_list()

        last_position = shopping_list.items.aggregate(max_position=Max("position"))["max_position"] or 0
        ShoppingItem.objects.create(
            shopping_list=shopping_list,
            position=last_position + 1,
            **data,
        )
        messages.success(request, _("Artikel wurde hinzugefügt."))
        return _redirect_to_list()

    today = timezone.localdate()
    shopping_list.items.filter(
        is_completed=False,
        next_due_date__lte=today,
    ).update(next_due_date=None)

    items = list(shopping_list.items.all())
    active_items = [
        item for item in items
        if not item.is_completed and item.next_due_date is None
    ]
    planned_items = sorted(
        (
            item for item in items
            if not item.is_completed and item.next_due_date is not None
        ),
        key=lambda item: (item.next_due_date, item.position, item.created_at),
    )
    completed_items = [item for item in items if item.is_completed]
    estimated_total = sum(
        (item.line_total for item in active_items if item.line_total is not None),
        Decimal("0.00"),
    )
    priced_items_count = sum(item.unit_price is not None for item in active_items)

    return render(request, "app/shopping_list.html", {
        "shopping_list": shopping_list,
        "active_items": active_items,
        "planned_items": planned_items,
        "completed_items": completed_items,
        "active_count": len(active_items),
        "planned_count": len(planned_items),
        "completed_count": len(completed_items),
        "estimated_total": estimated_total,
        "priced_items_count": priced_items_count,
        "unit_choices": ShoppingItem.UNIT_CHOICES,
        "category_choices": ShoppingItem.CATEGORY_CHOICES,
        "recurrence_choices": ShoppingItem.RECURRENCE_CHOICES,
    })


@login_required
@require_POST
def shopping_item_update_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    data, error = _item_data(request)
    if error:
        messages.error(request, error)
        return _redirect_to_list()

    for field, value in data.items():
        setattr(item, field, value)
    update_fields = [*data.keys(), "updated_at"]
    if item.recurrence == ShoppingItem.RECURRENCE_NONE and item.next_due_date is not None:
        item.next_due_date = None
        update_fields.append("next_due_date")
    item.save(update_fields=update_fields)
    messages.success(request, _("Artikel wurde aktualisiert."))
    return _redirect_to_list()


@login_required
@require_POST
def shopping_item_toggle_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    if (
        not item.is_completed
        and item.recurrence != ShoppingItem.RECURRENCE_NONE
    ):
        if item.next_due_date and item.next_due_date > timezone.localdate():
            messages.info(request, _("Der Artikel ist bereits für später eingeplant."))
            return _redirect_to_list()

        next_due_date = _next_recurrence_date(item.recurrence, timezone.localdate())
        item.next_due_date = next_due_date
        item.completed_at = None
        item.save(update_fields=["next_due_date", "completed_at", "updated_at"])
        messages.success(
            request,
            _("Artikel ist bis %(date)s eingeplant.") % {
                "date": date_format(next_due_date, "DATE_FORMAT"),
            },
        )
        return _redirect_to_list()

    item.is_completed = not item.is_completed
    item.completed_at = timezone.now() if item.is_completed else None
    if not item.is_completed:
        item.next_due_date = None
    item.save(update_fields=["is_completed", "completed_at", "next_due_date", "updated_at"])
    return _redirect_to_list()


@login_required
@require_POST
def shopping_item_activate_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    item.next_due_date = None
    item.is_completed = False
    item.completed_at = None
    item.save(update_fields=["next_due_date", "is_completed", "completed_at", "updated_at"])
    messages.success(request, _("Artikel wurde auf die aktuelle Liste gesetzt."))
    return _redirect_to_list()


@login_required
@require_POST
def shopping_item_delete_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    item.delete()
    messages.success(request, _("Artikel wurde gelöscht."))
    return _redirect_to_list()


@login_required
@require_POST
def shopping_clear_completed_view(request):
    shopping_list = _default_list(request.user)
    deleted_count, _details = shopping_list.items.filter(is_completed=True).delete()
    if deleted_count:
        messages.success(request, _("Erledigte Artikel wurden entfernt."))
    else:
        messages.info(request, _("Es gibt keine erledigten Artikel."))
    return _redirect_to_list()


@login_required
@require_GET
def shopping_product_api(request, barcode):
    normalized = normalize_barcode(barcode)
    if not normalized:
        return JsonResponse({
            "ok": False,
            "error": _("Der Barcode muss aus 8 bis 14 Ziffern bestehen."),
        }, status=400)

    try:
        product = lookup_product(normalized)
    except ProductLookupUnavailable:
        return JsonResponse({
            "ok": False,
            "error": _("Open Food Facts ist gerade nicht erreichbar. Du kannst den Artikel manuell eintragen."),
        }, status=503)

    if product is None:
        return JsonResponse({
            "ok": False,
            "error": _("Zu diesem Barcode wurde kein Produkt gefunden."),
        }, status=404)

    return JsonResponse({"ok": True, "product": product})
