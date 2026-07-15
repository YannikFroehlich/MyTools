import json
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
        self.assertContains(response, 'id="shopping-advanced-toggle"')
        self.assertContains(response, 'id="shopping-mode-toolbar"')
        self.assertContains(response, 'id="shopping-suggestions-data"')
        self.assertContains(response, 'id="shopping-sync-status"')
        self.assertContains(response, 'class="shopping-button shopping-button-soft shopping-reorder-toggle"')
        self.assertContains(response, "/static/app/js/shopping_offline.js")
        self.assertContains(response, 'name="recurrence"')
        self.assertTrue(ShoppingList.objects.filter(owner=self.user, is_default=True).exists())

    def test_active_items_are_grouped_in_store_order(self):
        chilled = self.create_item(name="Joghurt", category=ShoppingItem.CATEGORY_CHILLED)
        bakery = self.create_item(name="Brot", category=ShoppingItem.CATEGORY_BAKERY)
        self.login()

        response = self.client.get(reverse("shopping_list"))

        groups = response.context["active_groups"]
        self.assertEqual([group["category"] for group in groups], [
            ShoppingItem.CATEGORY_BAKERY,
            ShoppingItem.CATEGORY_CHILLED,
        ])
        self.assertEqual(groups[0]["items"], [bakery])
        self.assertEqual(groups[1]["items"], [chilled])
        self.assertContains(response, 'data-shopping-category="bakery"')
        self.assertContains(response, 'data-shopping-category="chilled"')

    def test_completed_history_creates_ranked_suggestions_and_excludes_active_names(self):
        self.create_item(name="Brot", category=ShoppingItem.CATEGORY_BAKERY, is_completed=True)
        self.create_item(name="Brot", category=ShoppingItem.CATEGORY_BAKERY, is_completed=True)
        self.create_item(name="Milch", is_completed=True)
        self.create_item(name="Milch")
        self.login()

        response = self.client.get(reverse("shopping_list"))

        suggestions = response.context["shopping_suggestions"]
        self.assertTrue(response.context["has_historical_suggestions"])
        self.assertEqual(suggestions[0]["name"], "Brot")
        self.assertEqual(suggestions[0]["usage_count"], 2)
        self.assertNotIn("Milch", [suggestion["name"] for suggestion in suggestions])

    def test_new_list_uses_starter_suggestions_in_empty_state(self):
        self.login()

        response = self.client.get(reverse("shopping_list"))

        self.assertFalse(response.context["has_historical_suggestions"])
        self.assertEqual(response.context["shopping_suggestions"][0]["kind"], "starter")
        self.assertContains(response, 'data-shopping-suggestion-index="0"')
        self.assertContains(response, "Milch")

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

    def test_json_add_warns_about_duplicates_and_can_be_confirmed(self):
        self.create_item(name="Milch", barcode="12345678")
        self.login()
        data = {
            "name": "Milch",
            "quantity": "1",
            "unit": ShoppingItem.UNIT_PIECE,
            "category": ShoppingItem.CATEGORY_CHILLED,
            "barcode": "12345678",
        }

        warning = self.client.post(
            reverse("shopping_list"),
            data,
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(warning.status_code, 409)
        self.assertTrue(warning.json()["duplicate"])
        self.assertEqual(ShoppingItem.objects.filter(shopping_list__owner=self.user).count(), 1)

        data["allow_duplicate"] = "1"
        confirmed = self.client.post(
            reverse("shopping_list"),
            data,
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(confirmed.status_code, 201)
        self.assertEqual(ShoppingItem.objects.filter(shopping_list__owner=self.user).count(), 2)

    def test_duplicate_can_increase_existing_quantity(self):
        item = self.create_item(name="Milch", quantity=Decimal("2.00"), unit=ShoppingItem.UNIT_PACK)
        self.login()

        response = self.client.post(
            reverse("shopping_list"),
            {
                "name": "Milch",
                "quantity": "3",
                "unit": ShoppingItem.UNIT_PIECE,
                "category": ShoppingItem.CATEGORY_CHILLED,
                "duplicate_action": "merge",
            },
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["merged"])
        self.assertIn("list_html", response.json())
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("5.00"))
        self.assertEqual(item.unit, ShoppingItem.UNIT_PACK)
        self.assertEqual(ShoppingItem.objects.filter(shopping_list__owner=self.user).count(), 1)

    def test_inline_update_only_changes_quantity_and_price(self):
        item = self.create_item(note="Bleibt erhalten", barcode="12345678")
        self.login()

        response = self.client.post(
            reverse("shopping_item_update", args=[item.id]),
            {"inline": "1", "quantity": "3,5", "unit_price": "2,19"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["line_total"], "7.67")
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("3.50"))
        self.assertEqual(item.unit_price, Decimal("2.19"))
        self.assertEqual(item.note, "Bleibt erhalten")
        self.assertEqual(item.barcode, "12345678")

    def test_json_delete_can_be_undone_with_signed_token(self):
        item = self.create_item(name="Undo-Milch", note="Wieder da")
        self.login()

        deleted = self.client.post(
            reverse("shopping_item_delete", args=[item.id]),
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(ShoppingItem.objects.filter(id=item.id).exists())
        restored = self.client.post(
            reverse("shopping_item_restore"),
            {"token": deleted.json()["restore_token"]},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(restored.status_code, 200)
        restored_item = ShoppingItem.objects.get(shopping_list__owner=self.user, name="Undo-Milch")
        self.assertEqual(restored_item.note, "Wieder da")

    def test_invalid_restore_token_is_rejected(self):
        self.login()

        response = self.client.post(
            reverse("shopping_item_restore"),
            {"token": "not-a-valid-token"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json()["ok"])

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

    def test_json_toggle_returns_live_list_state(self):
        item = self.create_item()
        self.login()

        response = self.client.post(
            reverse("shopping_item_toggle", args=[item.id]),
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["active"], 0)
        self.assertEqual(response.json()["summary"]["completed"], 1)
        self.assertIn("shopping-completed-card", response.json()["list_html"])
        self.assertIn("Milch", response.json()["list_html"])

    def test_store_order_can_reorder_categories_and_items(self):
        first = self.create_item(name="Brot", category=ShoppingItem.CATEGORY_BAKERY, position=1)
        chilled = self.create_item(name="Joghurt", category=ShoppingItem.CATEGORY_CHILLED, position=2)
        second = self.create_item(name="Brötchen", category=ShoppingItem.CATEGORY_BAKERY, position=3)
        self.login()

        response = self.client.post(
            reverse("shopping_reorder"),
            data=json.dumps({
                "categories": [ShoppingItem.CATEGORY_CHILLED, ShoppingItem.CATEGORY_BAKERY],
                "items": [
                    {"id": chilled.id, "category": ShoppingItem.CATEGORY_CHILLED},
                    {"id": second.id, "category": ShoppingItem.CATEGORY_BAKERY},
                    {"id": first.id, "category": ShoppingItem.CATEGORY_BAKERY},
                ],
            }),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        shopping_list = ShoppingList.objects.get(owner=self.user, is_default=True)
        self.assertEqual(shopping_list.category_order[:2], [
            ShoppingItem.CATEGORY_CHILLED,
            ShoppingItem.CATEGORY_BAKERY,
        ])
        chilled.refresh_from_db()
        second.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual([chilled.position, second.position, first.position], [1, 2, 3])

        page = self.client.get(reverse("shopping_list"))
        self.assertEqual([group["category"] for group in page.context["active_groups"][:2]], [
            ShoppingItem.CATEGORY_CHILLED,
            ShoppingItem.CATEGORY_BAKERY,
        ])
        self.assertEqual(page.context["active_groups"][1]["items"], [second, first])

    def test_store_order_rejects_foreign_items(self):
        own_item = self.create_item(name="Eigen")
        foreign_item = self.create_item(owner=self.other_user, name="Fremd")
        self.login()

        response = self.client.post(
            reverse("shopping_reorder"),
            data=json.dumps({
                "categories": [ShoppingItem.CATEGORY_OTHER],
                "items": [{"id": own_item.id, "category": own_item.category}, {"id": foreign_item.id, "category": foreign_item.category}],
            }),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ShoppingList.objects.get(owner=self.user, is_default=True).category_order, [])

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
        self.assertEqual(access_key_for_url_name("shopping_item_restore"), "shopping_list")
        self.assertEqual(access_key_for_url_name("shopping_state_api"), "shopping_list")
        self.assertEqual(access_key_for_url_name("shopping_reorder"), "shopping_list")

    def test_offline_shopping_shell_and_service_worker_are_public(self):
        self.client.logout()

        shell = self.client.get(reverse("shopping_offline"))
        worker = self.client.get(reverse("pwa_service_worker"))

        self.assertEqual(shell.status_code, 200)
        self.assertContains(shell, "shopping-offline-content")
        self.assertEqual(worker.status_code, 200)
        self.assertContains(worker, reverse("shopping_offline"))
        self.assertContains(worker, "mytools-shopping-sync")


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
