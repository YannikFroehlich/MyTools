import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse


class TitleSuffixTests(TestCase):
    def test_login_title_ends_with_mytools_by_default(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, " MyTools</title>")

    @override_settings(TITLE_SUFFIX="-dev")
    def test_title_suffix_marks_the_dev_instance(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, " MyTools-dev</title>")

    def test_every_title_carries_the_suffix_without_gap(self):
        # A newline before the suffix would show up as "MyTools -dev" in the tab, and a
        # standalone page without the variable would not show it at all.
        root = Path(settings.BASE_DIR, "app", "templates")
        block = re.compile(r"\{% block title %\}(.*?)\{% endblock", re.S)
        for template in root.rglob("*.html"):
            text = template.read_text(encoding="utf-8")
            with self.subTest(template=str(template.relative_to(root))):
                for title in block.findall(text):
                    self.assertEqual(title, title.strip())
                if "<title>" in text and "{% block title %}" not in text:
                    self.assertIn("{{ title_suffix }}</title>", text)
