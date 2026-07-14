import re

import requests
from django.conf import settings
from django.core.cache import cache


OPEN_FOOD_FACTS_PRODUCT_URL = "https://world.openfoodfacts.org/api/v3/product/{barcode}.json"
BARCODE_RE = re.compile(r"^[0-9]{8,14}$")
PRODUCT_CACHE_SECONDS = 24 * 60 * 60
MISSING_PRODUCT_CACHE_SECONDS = 60 * 60


class ProductLookupUnavailable(Exception):
    """Raised when Open Food Facts cannot currently answer a lookup."""


def normalize_barcode(value):
    barcode = re.sub(r"[\s-]+", "", str(value or ""))
    return barcode if BARCODE_RE.fullmatch(barcode) else ""


def lookup_product(barcode):
    barcode = normalize_barcode(barcode)
    if not barcode:
        raise ValueError("invalid barcode")

    cache_key = f"open-food-facts:product:v1:{barcode}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.get("product") if cached.get("found") else None

    try:
        response = requests.get(
            OPEN_FOOD_FACTS_PRODUCT_URL.format(barcode=barcode),
            params={
                "fields": "code,product_name,product_name_de,brands,quantity,image_front_small_url,image_front_url",
                "cc": "de",
                "lc": "de",
            },
            headers={
                "User-Agent": settings.OPEN_FOOD_FACTS_USER_AGENT,
                "Accept": "application/json",
            },
            timeout=6,
        )
    except requests.RequestException as exc:
        raise ProductLookupUnavailable from exc

    if response.status_code == 404:
        cache.set(cache_key, {"found": False}, MISSING_PRODUCT_CACHE_SECONDS)
        return None

    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProductLookupUnavailable from exc

    if not isinstance(payload, dict):
        raise ProductLookupUnavailable

    product_data = payload.get("product")
    if not isinstance(product_data, dict):
        cache.set(cache_key, {"found": False}, MISSING_PRODUCT_CACHE_SECONDS)
        return None

    product = {
        "barcode": barcode,
        "name": str(product_data.get("product_name_de") or product_data.get("product_name") or "").strip()[:160],
        "brand": str(product_data.get("brands") or "").strip()[:120],
        "quantity": str(product_data.get("quantity") or "").strip()[:80],
        "image_url": str(product_data.get("image_front_small_url") or product_data.get("image_front_url") or "").strip()[:500],
    }
    cache.set(cache_key, {"found": True, "product": product}, PRODUCT_CACHE_SECONDS)
    return product
