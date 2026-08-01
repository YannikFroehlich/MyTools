from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ScrollRestorationAssetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = (
            Path(settings.BASE_DIR) / "app" / "static" / "app" / "js" / "base.js"
        ).read_text(encoding="utf-8")

    def test_scroll_position_is_saved_per_page_in_the_current_tab(self):
        self.assertIn("window.sessionStorage.setItem(storageKey", self.script)
        self.assertIn("window.location.pathname", self.script)
        self.assertIn("window.location.search", self.script)
        self.assertIn("window.addEventListener('pagehide'", self.script)

    def test_scroll_position_is_restored_without_breaking_anchor_links(self):
        self.assertIn("window.history.scrollRestoration = 'manual'", self.script)
        self.assertIn("window.location.hash", self.script)
        self.assertIn("window.scrollTo({", self.script)
        self.assertIn("restoreObserver.observe(document.body)", self.script)
