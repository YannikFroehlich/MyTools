from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from app.access_control import access_key_for_url_name
from app.models import ShoppingItem, ShoppingList
from app.open_food_facts import ProductLookupUnavailable, lookup_product
from app.platform_utils import tool_by_key


class ShoppingListViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="shopper", password="secret123")
        self.other_user = user_model.objects.create_user(username="other", password="secret123")

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def create_item(self, *, owner=None, **kwargs):
        owner = owner or self.user
        shopping_list, _created = ShoppingList.objects.get_or_create(
            owner=owner,
            is_default=True,
            defaults={"name": "Mein Einkaufszettel"},
        )
        defaults = {
            "name": "Milch",
            "quantity": Decimal("2.00"),
            "unit": ShoppingItem.UNIT_PACK,
            "unit_price": Decimal("1.49"),
            "category": ShoppingItem.CATEGORY_CHILLED,
        }
        defaults.update(kwargs)
        return ShoppingItem.objects.create(shopping_list=shopping_list, **defaults)

    def test_page_requires_login(self):
        response = self.client.get(reverse("shopping_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_page_creates_default_list_and_loads_template(self):
        self.login()

        response = self.client.get(reverse("shopping_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/shopping_list.html")
        self.assertContains(response, "Einkaufszettel")
        self.assertContains(response, 'id="shopping-camera-open"')
        self.assertContains(response, 'id="shopping-scanner-dialog"')
        self.assertContains(response, 'id="shopping-add-toggle"')
        self.assertContains(response, 'name="recurrence"')
        self.assertTrue(ShoppingList.objects.filter(owner=self.user, is_default=True).exists())

    def test_add_item_parses_german_price_and_calculates_total(self):
        self.login()

        response = self.client.post(reverse("shopping_list"), {
            "name": "Hafermilch",
            "quantity": "2",
            "unit": ShoppingItem.UNIT_PACK,
            "unit_price": "1,49",
            "category": ShoppingItem.CATEGORY_CHILLED,
            "note": "Ungesüßt",
            "barcode": "12345678",
            "recurrence": ShoppingItem.RECURRENCE_WEEKLY,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        item = ShoppingItem.objects.get(shopping_list__owner=self.user)
        self.assertEqual(item.quantity, Decimal("2.00"))
        self.assertEqual(item.unit_price, Decimal("1.49"))
        self.assertEqual(item.recurrence, ShoppingItem.RECURRENCE_WEEKLY)
        self.assertEqual(item.line_total, Decimal("2.9800"))
        self.assertContains(response, "Hafermilch")
        self.assertContains(response, "2,98 €")

    def test_invalid_quantity_does_not_create_item(self):
        self.login()

        response = self.client.post(reverse("shopping_list"), {
            "name": "Brot",
            "quantity": "0",
            "unit": ShoppingItem.UNIT_PIECE,
            "category": ShoppingItem.CATEGORY_BAKERY,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShoppingItem.objects.filter(shopping_list__owner=self.user).exists())
        self.assertContains(response, "Die Menge muss größer als 0 sein.")

    def test_update_toggle_and_delete_item(self):
        item = self.create_item()
        self.login()

        update_response = self.client.post(reverse("shopping_item_update", args=[item.id]), {
            "name": "Vollmilch",
            "quantity": "1.5",
            "unit": ShoppingItem.UNIT_LITER,
            "unit_price": "1.20",
            "category": ShoppingItem.CATEGORY_CHILLED,
            "note": "3,5 %",
        })
        self.assertRedirects(update_response, reverse("shopping_list"))
        item.refresh_from_db()
        self.assertEqual(item.name, "Vollmilch")
        self.assertEqual(item.quantity, Decimal("1.50"))

        toggle_response = self.client.post(reverse("shopping_item_toggle", args=[item.id]))
        self.assertRedirects(toggle_response, reverse("shopping_list"))
        item.refresh_from_db()
        self.assertTrue(item.is_completed)
        self.assertIsNotNone(item.completed_at)

        delete_response = self.client.post(reverse("shopping_item_delete", args=[item.id]))
        self.assertRedirects(delete_response, reverse("shopping_list"))
        self.assertFalse(ShoppingItem.objects.filter(id=item.id).exists())

    def test_items_are_isolated_between_users(self):
        own_item = self.create_item()
        foreign_item = self.create_item(owner=self.other_user, name="Geheimer Einkauf")
        self.login()

        response = self.client.get(reverse("shopping_list"))
        self.assertContains(response, own_item.name)
        self.assertNotContains(response, foreign_item.name)

        toggle_response = self.client.post(reverse("shopping_item_toggle", args=[foreign_item.id]))
        self.assertEqual(toggle_response.status_code, 404)
        foreign_item.refresh_from_db()
        self.assertFalse(foreign_item.is_completed)

    def test_clear_completed_only_removes_current_users_items(self):
        own_completed = self.create_item(is_completed=True)
        other_completed = self.create_item(owner=self.other_user, name="Fremd", is_completed=True)
        self.login()

        response = self.client.post(reverse("shopping_clear_completed"))

        self.assertRedirects(response, reverse("shopping_list"))
        self.assertFalse(ShoppingItem.objects.filter(id=own_completed.id).exists())
        self.assertTrue(ShoppingItem.objects.filter(id=other_completed.id).exists())

    @patch("app.views.shopping.timezone.localdate", return_value=date(2026, 7, 14))
    def test_recurring_item_is_planned_instead_of_completed(self, _localdate_mock):
        item = self.create_item(recurrence=ShoppingItem.RECURRENCE_WEEKLY)
        self.login()

        response = self.client.post(reverse("shopping_item_toggle", args=[item.id]))

        self.assertRedirects(response, reverse("shopping_list"))
        item.refresh_from_db()
        self.assertFalse(item.is_completed)
        self.assertIsNone(item.completed_at)
        self.assertEqual(item.next_due_date, date(2026, 7, 21))

    @patch("app.views.shopping.timezone.localdate", return_value=date(2027, 1, 31))
    def test_monthly_recurrence_handles_end_of_month(self, _localdate_mock):
        item = self.create_item(recurrence=ShoppingItem.RECURRENCE_MONTHLY)
        self.login()

        self.client.post(reverse("shopping_item_toggle", args=[item.id]))

        item.refresh_from_db()
        self.assertEqual(item.next_due_date, date(2027, 2, 28))

    @patch("app.views.shopping.timezone.localdate", return_value=date(2026, 7, 14))
    def test_due_recurring_item_returns_to_active_list(self, _localdate_mock):
        item = self.create_item(
            recurrence=ShoppingItem.RECURRENCE_BIWEEKLY,
            next_due_date=date(2026, 7, 14),
        )
        self.login()

        response = self.client.get(reverse("shopping_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(item, response.context["active_items"])
        self.assertEqual(response.context["planned_count"], 0)
        item.refresh_from_db()
        self.assertIsNone(item.next_due_date)

    @patch("app.views.shopping.timezone.localdate", return_value=date(2026, 7, 14))
    def test_planned_item_can_be_activated_now_and_stays_private(self, _localdate_mock):
        item = self.create_item(
            recurrence=ShoppingItem.RECURRENCE_WEEKLY,
            next_due_date=date(2026, 7, 21),
        )
        foreign_item = self.create_item(
            owner=self.other_user,
            recurrence=ShoppingItem.RECURRENCE_WEEKLY,
            next_due_date=date(2026, 7, 21),
        )
        self.login()

        page_response = self.client.get(reverse("shopping_list"))
        self.assertIn(item, page_response.context["planned_items"])
        self.assertContains(page_response, "21. Juli 2026")

        foreign_response = self.client.post(reverse("shopping_item_activate", args=[foreign_item.id]))
        self.assertEqual(foreign_response.status_code, 404)

        response = self.client.post(reverse("shopping_item_activate", args=[item.id]))
        self.assertRedirects(response, reverse("shopping_list"))
        item.refresh_from_db()
        self.assertIsNone(item.next_due_date)
        foreign_item.refresh_from_db()
        self.assertEqual(foreign_item.next_due_date, date(2026, 7, 21))

    def test_tool_is_registered_for_catalog_and_access_control(self):
        tool = tool_by_key("shopping_list")

        self.assertIsNotNone(tool)
        self.assertEqual(tool["url_name"], "shopping_list")
        self.assertEqual(access_key_for_url_name("shopping_list"), "shopping_list")
        self.assertEqual(access_key_for_url_name("shopping-product-api"), "shopping_list")
        self.assertEqual(access_key_for_url_name("shopping_item_activate"), "shopping_list")


class ShoppingProductApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-shopper", password="secret123")
        self.client.force_login(self.user)

    @patch("app.views.shopping.lookup_product")
    def test_product_endpoint_returns_normalized_product(self, lookup_mock):
        lookup_mock.return_value = {
            "barcode": "3017620422003",
            "name": "Nuss-Nougat-Creme",
            "brand": "Beispiel",
            "quantity": "400 g",
            "image_url": "https://images.openfoodfacts.org/product.jpg",
        }

        response = self.client.get(reverse("shopping-product-api", args=["3017620422003"]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["product"]["name"], "Nuss-Nougat-Creme")

    @patch("app.views.shopping.lookup_product", return_value=None)
    def test_product_endpoint_returns_404_for_unknown_product(self, _lookup_mock):
        response = self.client.get(reverse("shopping-product-api", args=["12345678"]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["ok"])

    @patch("app.views.shopping.lookup_product", side_effect=ProductLookupUnavailable)
    def test_product_endpoint_has_manual_fallback_message(self, _lookup_mock):
        response = self.client.get(reverse("shopping-product-api", args=["12345678"]))

        self.assertEqual(response.status_code, 503)
        self.assertIn("manuell", response.json()["error"])


@override_settings(OPEN_FOOD_FACTS_USER_AGENT="MyToolsTests/1.0 (tests@example.com)")
class OpenFoodFactsClientTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("app.open_food_facts.requests.get")
    def test_lookup_uses_cache_and_identifiable_user_agent(self, get_mock):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "product": {
                "product_name_de": "Testprodukt",
                "brands": "Testmarke",
                "quantity": "500 g",
                "image_front_small_url": "https://images.openfoodfacts.org/test.jpg",
            },
        }
        get_mock.return_value = response

        first = lookup_product("3017620422003")
        second = lookup_product("3017620422003")

        self.assertEqual(first, second)
        self.assertEqual(first["name"], "Testprodukt")
        self.assertEqual(get_mock.call_count, 1)
        self.assertEqual(
            get_mock.call_args.kwargs["headers"]["User-Agent"],
            "MyToolsTests/1.0 (tests@example.com)",
        )
