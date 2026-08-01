from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ToolFeedback


class ModerationDashboardFeedbackTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="feedback-moderator",
            password="testpass-123",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def test_dashboard_hides_done_feedback_but_keeps_actionable_statuses(self):
        open_feedback = ToolFeedback.objects.create(
            title="Offenes Dashboard-Feedback",
            message="Muss noch geprueft werden.",
            status=ToolFeedback.STATUS_OPEN,
        )
        planned_feedback = ToolFeedback.objects.create(
            title="Geplantes Dashboard-Feedback",
            message="Ist fuer spaeter eingeplant.",
            status=ToolFeedback.STATUS_PLANNED,
        )
        done_feedback = ToolFeedback.objects.create(
            title="Erledigtes Dashboard-Feedback",
            message="Ist bereits abgeschlossen.",
            status=ToolFeedback.STATUS_DONE,
        )

        response = self.client.get(reverse("moderation"))

        self.assertEqual(response.status_code, 200)
        feedback_items = list(response.context["feedback_items"])
        self.assertIn(open_feedback, feedback_items)
        self.assertIn(planned_feedback, feedback_items)
        self.assertNotIn(done_feedback, feedback_items)
        self.assertNotContains(response, done_feedback.title)

    def test_feedback_panel_spans_the_full_dashboard_grid(self):
        response = self.client.get(reverse("moderation"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        heading_position = content.index("<h2>Feedback</h2>")
        section_position = content.rfind("<section", 0, heading_position)
        section_tag = content[section_position:content.index(">", section_position)]
        self.assertIn('class="moderation-panel is-wide"', section_tag)
