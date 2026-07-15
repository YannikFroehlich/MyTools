import calendar
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..models import ShoppingItem, ShoppingList
from ..open_food_facts import ProductLookupUnavailable, lookup_product, normalize_barcode


DECIMAL_STEP = Decimal("0.01")
MAX_QUANTITY = Decimal("999999.99")
MAX_PRICE = Decimal("99999999.99")
ALLOWED_IMAGE_HOSTS = {"images.openfoodfacts.org", "static.openfoodfacts.org"}
SHOPPING_UNDO_WINDOW_SECONDS = 30
SHOPPING_UNDO_SALT = "shopping-item-undo"
CATEGORY_ICONS = {
    ShoppingItem.CATEGORY_FRUIT_VEG: "fa-solid fa-carrot",
    ShoppingItem.CATEGORY_BAKERY: "fa-solid fa-bread-slice",
    ShoppingItem.CATEGORY_CHILLED: "fa-solid fa-snowflake",
    ShoppingItem.CATEGORY_PANTRY: "fa-solid fa-box-open",
    ShoppingItem.CATEGORY_DRINKS: "fa-solid fa-bottle-water",
    ShoppingItem.CATEGORY_FROZEN: "fa-solid fa-icicles",
    ShoppingItem.CATEGORY_HOUSEHOLD: "fa-solid fa-house",
    ShoppingItem.CATEGORY_OTHER: "fa-solid fa-basket-shopping",
}


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


def _wants_json(request):
    return (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _decimal_input(value):
    if value is None:
        return ""
    return format(value.normalize(), "f")


def _item_json(item):
    line_total = item.line_total
    return {
        "id": item.id,
        "name": item.name,
        "quantity": _decimal_input(item.quantity),
        "unit": item.unit,
        "unit_label": str(item.get_unit_display()),
        "unit_price": _decimal_input(item.unit_price),
        "line_total": format(line_total.quantize(DECIMAL_STEP, rounding=ROUND_HALF_UP), ".2f") if line_total is not None else None,
        "category": item.category,
        "category_label": str(item.get_category_display()),
        "barcode": item.barcode,
        "position": item.position,
        "is_completed": item.is_completed,
        "is_planned": item.next_due_date is not None,
    }


def _suggestion_payload(item, usage_count=1):
    return {
        "name": item.name,
        "quantity": _decimal_input(item.quantity),
        "unit": item.unit,
        "unit_price": _decimal_input(item.unit_price),
        "category": item.category,
        "recurrence": item.recurrence,
        "barcode": item.barcode,
        "brand": item.brand,
        "product_quantity": item.product_quantity,
        "image_url": item.image_url,
        "usage_count": usage_count,
        "kind": "frequent" if usage_count > 1 else "recent",
    }


def _shopping_suggestions(completed_items, active_items, limit=8):
    active_names = {item.name.strip().casefold() for item in active_items}
    grouped = {}
    for item in sorted(completed_items, key=lambda value: value.updated_at, reverse=True):
        key = item.name.strip().casefold()
        if not key or key in active_names:
            continue
        entry = grouped.setdefault(key, {"item": item, "count": 0})
        entry["count"] += 1

    ranked = sorted(
        grouped.values(),
        key=lambda entry: (-entry["count"], -entry["item"].updated_at.timestamp()),
    )
    return [
        _suggestion_payload(entry["item"], entry["count"])
        for entry in ranked[:limit]
    ]


def _starter_suggestions():
    defaults = (
        (_("Milch"), ShoppingItem.CATEGORY_CHILLED, ShoppingItem.UNIT_PIECE),
        (_("Brot"), ShoppingItem.CATEGORY_BAKERY, ShoppingItem.UNIT_PIECE),
        (_("Bananen"), ShoppingItem.CATEGORY_FRUIT_VEG, ShoppingItem.UNIT_PIECE),
        (_("Wasser"), ShoppingItem.CATEGORY_DRINKS, ShoppingItem.UNIT_PACK),
        (_("Nudeln"), ShoppingItem.CATEGORY_PANTRY, ShoppingItem.UNIT_PACK),
        (_("Spülmittel"), ShoppingItem.CATEGORY_HOUSEHOLD, ShoppingItem.UNIT_PIECE),
    )
    return [
        {
            "name": str(name),
            "quantity": "1",
            "unit": unit,
            "unit_price": "",
            "category": category,
            "recurrence": ShoppingItem.RECURRENCE_NONE,
            "barcode": "",
            "brand": "",
            "product_quantity": "",
            "image_url": "",
            "usage_count": 0,
            "kind": "starter",
        }
        for name, category, unit in defaults
    ]


def _normalized_category_order(shopping_list, proposed_order=None):
    valid_order = [value for value, _label in ShoppingItem.CATEGORY_CHOICES]
    raw_order = proposed_order if proposed_order is not None else shopping_list.category_order
    if not isinstance(raw_order, list):
        raw_order = []

    normalized = []
    for value in raw_order:
        if value in valid_order and value not in normalized:
            normalized.append(value)
    normalized.extend(value for value in valid_order if value not in normalized)
    return normalized


def _shopping_context(shopping_list, *, include_suggestions=False):
    today = timezone.localdate()
    shopping_list.items.filter(
        is_completed=False,
        next_due_date__lte=today,
    ).update(next_due_date=None)

    category_order = _normalized_category_order(shopping_list)
    category_rank = {category: index for index, category in enumerate(category_order)}
    items = list(shopping_list.items.all())
    active_items = sorted(
        (
            item for item in items
            if not item.is_completed and item.next_due_date is None
        ),
        key=lambda item: (
            category_rank.get(item.category, len(category_rank)),
            item.position,
            item.created_at,
        ),
    )
    planned_items = sorted(
        (
            item for item in items
            if not item.is_completed and item.next_due_date is not None
        ),
        key=lambda item: (item.next_due_date, item.position, item.created_at),
    )
    completed_items = [item for item in items if item.is_completed]
    choices_by_category = dict(ShoppingItem.CATEGORY_CHOICES)
    active_groups = []
    for category in category_order:
        category_items = [item for item in active_items if item.category == category]
        if category_items:
            active_groups.append({
                "category": category,
                "label": choices_by_category[category],
                "icon": CATEGORY_ICONS.get(category, CATEGORY_ICONS[ShoppingItem.CATEGORY_OTHER]),
                "items": category_items,
                "order_index": category_rank[category],
            })

    estimated_total = sum(
        (item.line_total for item in active_items if item.line_total is not None),
        Decimal("0.00"),
    )
    context = {
        "shopping_list": shopping_list,
        "active_items": active_items,
        "active_groups": active_groups,
        "planned_items": planned_items,
        "completed_items": completed_items,
        "active_count": len(active_items),
        "planned_count": len(planned_items),
        "completed_count": len(completed_items),
        "estimated_total": estimated_total,
        "priced_items_count": sum(item.unit_price is not None for item in active_items),
        "category_order": category_order,
        "unit_choices": ShoppingItem.UNIT_CHOICES,
        "category_choices": ShoppingItem.CATEGORY_CHOICES,
        "recurrence_choices": ShoppingItem.RECURRENCE_CHOICES,
    }
    if include_suggestions:
        historical_suggestions = _shopping_suggestions(completed_items, active_items)
        context.update({
            "shopping_suggestions": historical_suggestions or _starter_suggestions(),
            "has_historical_suggestions": bool(historical_suggestions),
            "existing_items": [_item_json(item) for item in active_items],
        })
    return context


def _shopping_state_payload(request, shopping_list, *, context=None):
    context = context or _shopping_context(shopping_list, include_suggestions=True)
    estimated_total = context["estimated_total"].quantize(DECIMAL_STEP, rounding=ROUND_HALF_UP)
    return {
        "summary": {
            "active": context["active_count"],
            "planned": context["planned_count"],
            "completed": context["completed_count"],
            "estimated_total": format(estimated_total, ".2f"),
            "priced_items_count": context["priced_items_count"],
        },
        "category_order": context["category_order"],
        "existing_items": [_item_json(item) for item in context["active_items"]],
        "list_html": render_to_string(
            "app/includes/shopping_list_content.html",
            context,
            request=request,
        ),
    }


def _json_with_shopping_state(request, shopping_list, payload=None, *, status=200):
    response_payload = {"ok": True}
    if payload:
        response_payload.update(payload)
    response_payload.update(_shopping_state_payload(request, shopping_list))
    return JsonResponse(response_payload, status=status)


def _duplicate_item(shopping_list, data):
    duplicate_query = Q(name__iexact=data["name"])
    if data["barcode"]:
        duplicate_query |= Q(barcode=data["barcode"])
    return shopping_list.items.filter(
        is_completed=False,
        next_due_date__isnull=True,
    ).filter(duplicate_query).first()


def _delete_snapshot(item):
    return {
        "owner_id": item.shopping_list.owner_id,
        "shopping_list_id": item.shopping_list_id,
        "item": {
            "name": item.name,
            "quantity": str(item.quantity),
            "unit": item.unit,
            "unit_price": str(item.unit_price) if item.unit_price is not None else None,
            "category": item.category,
            "note": item.note,
            "barcode": item.barcode,
            "brand": item.brand,
            "product_quantity": item.product_quantity,
            "image_url": item.image_url,
            "recurrence": item.recurrence,
            "next_due_date": item.next_due_date.isoformat() if item.next_due_date else None,
            "is_completed": item.is_completed,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "position": item.position,
        },
    }


@login_required
def shopping_list_view(request):
    shopping_list = _default_list(request.user)

    if request.method == "POST":
        data, error = _item_data(request)
        if error:
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
            return _redirect_to_list()

        duplicate = _duplicate_item(shopping_list, data)
        duplicate_action = request.POST.get("duplicate_action") or ""
        if duplicate and duplicate_action == "merge":
            duplicate.quantity = min(MAX_QUANTITY, duplicate.quantity + data["quantity"])
            duplicate.save(update_fields=["quantity", "updated_at"])
            message = _("Die Menge von %(name)s wurde erhöht.") % {"name": duplicate.name}
            if _wants_json(request):
                return _json_with_shopping_state(
                    request,
                    shopping_list,
                    {"message": message, "merged": True, "item": _item_json(duplicate)},
                )
            messages.success(request, message)
            return _redirect_to_list()

        if duplicate and _wants_json(request) and request.POST.get("allow_duplicate") != "1":
            return JsonResponse({
                "ok": False,
                "duplicate": True,
                "error": _("%(name)s steht bereits auf deiner Liste.") % {"name": duplicate.name},
                "item": _item_json(duplicate),
            }, status=409)

        last_position = shopping_list.items.aggregate(max_position=Max("position"))["max_position"] or 0
        item = ShoppingItem.objects.create(
            shopping_list=shopping_list,
            position=last_position + 1,
            **data,
        )
        if _wants_json(request):
            return _json_with_shopping_state(
                request,
                shopping_list,
                {
                    "message": _("Artikel wurde hinzugefügt."),
                    "item": _item_json(item),
                },
                status=201,
            )
        messages.success(request, _("Artikel wurde hinzugefügt."))
        return _redirect_to_list()

    context = _shopping_context(shopping_list, include_suggestions=True)
    return render(request, "app/shopping_list.html", context)


@login_required
@require_POST
def shopping_item_update_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    if request.POST.get("inline") == "1":
        try:
            quantity = _parse_decimal(request.POST.get("quantity"), required=True, maximum=MAX_QUANTITY)
        except ValueError:
            error = _("Die Menge muss größer als 0 sein.")
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
            return _redirect_to_list()

        try:
            unit_price = _parse_optional_price(request.POST.get("unit_price"))
        except ValueError:
            error = _("Bitte gib einen gültigen Preis ein.")
            if _wants_json(request):
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
            return _redirect_to_list()

        item.quantity = quantity
        item.unit_price = unit_price
        item.save(update_fields=["quantity", "unit_price", "updated_at"])
        message = _("Menge und Preis wurden gespeichert.")
        if _wants_json(request):
            return _json_with_shopping_state(
                request,
                item.shopping_list,
                {"message": message, "item": _item_json(item)},
            )
        messages.success(request, message)
        return _redirect_to_list()

    data, error = _item_data(request)
    if error:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return _redirect_to_list()

    for field, value in data.items():
        setattr(item, field, value)
    update_fields = [*data.keys(), "updated_at"]
    if item.recurrence == ShoppingItem.RECURRENCE_NONE and item.next_due_date is not None:
        item.next_due_date = None
        update_fields.append("next_due_date")
    item.save(update_fields=update_fields)
    if _wants_json(request):
        return _json_with_shopping_state(
            request,
            item.shopping_list,
            {
                "message": _("Artikel wurde aktualisiert."),
                "item": _item_json(item),
            },
        )
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
            message = _("Der Artikel ist bereits für später eingeplant.")
            if _wants_json(request):
                return _json_with_shopping_state(
                    request,
                    item.shopping_list,
                    {"message": message},
                    status=409,
                )
            messages.info(request, message)
            return _redirect_to_list()

        next_due_date = _next_recurrence_date(item.recurrence, timezone.localdate())
        item.next_due_date = next_due_date
        item.completed_at = None
        item.save(update_fields=["next_due_date", "completed_at", "updated_at"])
        message = _("Artikel ist bis %(date)s eingeplant.") % {
            "date": date_format(next_due_date, "DATE_FORMAT"),
        }
        if _wants_json(request):
            return _json_with_shopping_state(
                request,
                item.shopping_list,
                {"message": message, "item": _item_json(item)},
            )
        messages.success(request, message)
        return _redirect_to_list()

    item.is_completed = not item.is_completed
    item.completed_at = timezone.now() if item.is_completed else None
    if not item.is_completed:
        item.next_due_date = None
    item.save(update_fields=["is_completed", "completed_at", "next_due_date", "updated_at"])
    if _wants_json(request):
        message = _("Artikel wurde erledigt.") if item.is_completed else _("Artikel ist wieder offen.")
        return _json_with_shopping_state(
            request,
            item.shopping_list,
            {"message": message, "item": _item_json(item)},
        )
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
    message = _("Artikel wurde auf die aktuelle Liste gesetzt.")
    if _wants_json(request):
        return _json_with_shopping_state(
            request,
            item.shopping_list,
            {"message": message, "item": _item_json(item)},
        )
    messages.success(request, message)
    return _redirect_to_list()


@login_required
@require_POST
def shopping_item_delete_view(request, item_id):
    item = get_object_or_404(
        ShoppingItem,
        id=item_id,
        shopping_list__owner=request.user,
    )
    restore_token = signing.dumps(
        _delete_snapshot(item),
        salt=SHOPPING_UNDO_SALT,
        compress=True,
    )
    item.delete()
    if _wants_json(request):
        return _json_with_shopping_state(
            request,
            item.shopping_list,
            {
                "message": _("Artikel wurde gelöscht."),
                "restore_url": reverse("shopping_item_restore"),
                "restore_token": restore_token,
            },
        )
    messages.success(request, _("Artikel wurde gelöscht."))
    return _redirect_to_list()


@login_required
@require_POST
def shopping_item_restore_view(request):
    expired_message = _("Dieser Artikel kann nicht mehr wiederhergestellt werden.")
    restore_token = request.POST.get("token") or ""
    try:
        snapshot = signing.loads(
            restore_token,
            salt=SHOPPING_UNDO_SALT,
            max_age=SHOPPING_UNDO_WINDOW_SECONDS,
        )
    except (signing.BadSignature, signing.SignatureExpired):
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": expired_message}, status=410)
        messages.error(request, expired_message)
        return _redirect_to_list()

    try:
        if int(snapshot["owner_id"]) != request.user.pk:
            raise ValueError

        shopping_list = get_object_or_404(
            ShoppingList,
            id=int(snapshot["shopping_list_id"]),
            owner=request.user,
        )
        stored = snapshot["item"]
        item = ShoppingItem.objects.create(
            shopping_list=shopping_list,
            name=stored["name"],
            quantity=Decimal(stored["quantity"]),
            unit=stored["unit"],
            unit_price=Decimal(stored["unit_price"]) if stored["unit_price"] is not None else None,
            category=stored["category"],
            note=stored["note"],
            barcode=stored["barcode"],
            brand=stored["brand"],
            product_quantity=stored["product_quantity"],
            image_url=stored["image_url"],
            recurrence=stored["recurrence"],
            next_due_date=parse_date(stored["next_due_date"]) if stored["next_due_date"] else None,
            is_completed=bool(stored["is_completed"]),
            completed_at=parse_datetime(stored["completed_at"]) if stored["completed_at"] else None,
            position=int(stored["position"]),
        )
    except (InvalidOperation, KeyError, TypeError, ValueError):
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": expired_message}, status=410)
        messages.error(request, expired_message)
        return _redirect_to_list()

    message = _("Artikel wurde wiederhergestellt.")
    if _wants_json(request):
        return _json_with_shopping_state(
            request,
            shopping_list,
            {"message": message, "item": _item_json(item)},
        )
    messages.success(request, message)
    return _redirect_to_list()


@login_required
@require_POST
def shopping_clear_completed_view(request):
    shopping_list = _default_list(request.user)
    deleted_count, _details = shopping_list.items.filter(is_completed=True).delete()
    message = _("Erledigte Artikel wurden entfernt.") if deleted_count else _("Es gibt keine erledigten Artikel.")
    if _wants_json(request):
        return _json_with_shopping_state(request, shopping_list, {"message": message})
    if deleted_count:
        messages.success(request, message)
    else:
        messages.info(request, message)
    return _redirect_to_list()


@login_required
@require_GET
def shopping_state_api(request):
    shopping_list = _default_list(request.user)
    return _json_with_shopping_state(request, shopping_list)


@login_required
@require_POST
def shopping_reorder_view(request):
    shopping_list = _default_list(request.user)
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = json.loads(request.POST.get("payload") or "")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": _("Die Sortierung ist ungültig.")}, status=400)

    category_order = payload.get("categories")
    item_entries = payload.get("items")
    if not isinstance(category_order, list) or not isinstance(item_entries, list):
        return JsonResponse({"ok": False, "error": _("Die Sortierung ist unvollständig.")}, status=400)

    valid_categories = {value for value, _label in ShoppingItem.CATEGORY_CHOICES}
    normalized_entries = []
    seen_ids = set()
    try:
        for raw_entry in item_entries:
            if isinstance(raw_entry, dict):
                item_id = int(raw_entry["id"])
                category = raw_entry["category"]
            else:
                item_id = int(raw_entry)
                category = None
            if item_id <= 0 or item_id in seen_ids:
                raise ValueError
            if category is not None and category not in valid_categories:
                raise ValueError
            seen_ids.add(item_id)
            normalized_entries.append((item_id, category))
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": _("Die Artikelsortierung ist ungültig.")}, status=400)

    with transaction.atomic():
        shopping_list = ShoppingList.objects.select_for_update().get(pk=shopping_list.pk)
        active_items = list(shopping_list.items.select_for_update().filter(
            is_completed=False,
            next_due_date__isnull=True,
        ))
        items_by_id = {item.id: item for item in active_items}
        if not seen_ids.issubset(items_by_id):
            return JsonResponse({"ok": False, "error": _("Mindestens ein Artikel gehört nicht zu dieser Liste.")}, status=400)

        shopping_list.category_order = _normalized_category_order(shopping_list, category_order)
        shopping_list.save(update_fields=["category_order", "updated_at"])

        ordered_items = []
        for item_id, category in normalized_entries:
            item = items_by_id.pop(item_id)
            if category is not None:
                item.category = category
            ordered_items.append(item)
        ordered_items.extend(sorted(items_by_id.values(), key=lambda item: (item.position, item.created_at)))
        updated_at = timezone.now()
        for position, item in enumerate(ordered_items, 1):
            item.position = position
            item.updated_at = updated_at
        if ordered_items:
            ShoppingItem.objects.bulk_update(ordered_items, ["position", "category", "updated_at"])

    return _json_with_shopping_state(
        request,
        shopping_list,
        {"message": _("Ladenreihenfolge wurde gespeichert.")},
    )


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
