from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models import VacationHoliday, VacationPeriod
from app.views.vacation import build_vacation_period_rows, calculate_vacation_days, parse_holiday_date, parse_holiday_line


class VacationPlannerCalculationTests(TestCase):
    def test_calculates_weekdays_without_saved_holiday(self):
        result = calculate_vacation_days(
            date(2026, 7, 6),
            date(2026, 7, 10),
            {date(2026, 7, 8)},
        )

        self.assertEqual(result["total_days"], 5)
        self.assertEqual(result["weekend_days"], 0)
        self.assertEqual(result["holiday_weekdays"], 1)
        self.assertEqual(result["vacation_days"], 4)

    def test_weekend_and_holiday_are_not_double_counted(self):
        result = calculate_vacation_days(
            date(2026, 12, 24),
            date(2026, 12, 28),
            {date(2026, 12, 26), date(2026, 12, 28)},
        )

        self.assertEqual(result["total_days"], 5)
        self.assertEqual(result["weekend_days"], 2)
        self.assertEqual(result["holiday_weekdays"], 1)
        self.assertEqual(result["vacation_days"], 2)

    def test_vacation_period_summary_clips_cross_year_period(self):
        period = VacationPeriod(
            title="Winter",
            start_date=date(2026, 12, 30),
            end_date=date(2027, 1, 5),
        )

        rows, summary = build_vacation_period_rows(
            [period],
            2027,
            {date(2027, 1, 1)},
            date(2027, 1, 3),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["clipped_start"], date(2027, 1, 1))
        self.assertEqual(rows[0]["clipped_end"], date(2027, 1, 5))
        self.assertEqual(summary["total_days"], 2)
        self.assertEqual(summary["taken_days"], 0)
        self.assertEqual(summary["planned_days"], 2)


class VacationPlannerParserTests(TestCase):
    def test_parse_holiday_date_accepts_yearless_german_date(self):
        self.assertEqual(parse_holiday_date("03.10.", default_year=2027), date(2027, 10, 3))

    def test_parse_holiday_line_uses_default_year_and_name(self):
        holiday_date, name = parse_holiday_line("03.10. Tag der Deutschen Einheit", 2028)

        self.assertEqual(holiday_date, date(2028, 10, 3))
        self.assertEqual(name, "Tag der Deutschen Einheit")


class VacationPlannerViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="planner", password="test-pass")
        self.client.force_login(self.user)

    def test_add_holiday_creates_user_holiday(self):
        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "add_holiday",
                "year": "2027",
                "holiday_name": "Neujahr",
                "holiday_date": "2027-01-01",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertTrue(
            VacationHoliday.objects.filter(
                user=self.user,
                date=date(2027, 1, 1),
                name="Neujahr",
            ).exists()
        )

    def test_bulk_add_holidays_updates_existing_date(self):
        VacationHoliday.objects.create(user=self.user, date=date(2027, 1, 1), name="Alt")

        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "bulk_add_holidays",
                "year": "2027",
                "bulk_holidays": "2027-01-01 Neujahr\n03.10. Tag der Deutschen Einheit",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertEqual(VacationHoliday.objects.filter(user=self.user).count(), 2)
        self.assertEqual(
            VacationHoliday.objects.get(user=self.user, date=date(2027, 1, 1)).name,
            "Neujahr",
        )

    def test_add_vacation_creates_user_period(self):
        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "add_vacation",
                "year": "2027",
                "vacation_title": "Sommerurlaub",
                "vacation_start": "2027-07-05",
                "vacation_end": "2027-07-09",
                "vacation_note": "Familie",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertTrue(
            VacationPeriod.objects.filter(
                user=self.user,
                title="Sommerurlaub",
                start_date=date(2027, 7, 5),
                end_date=date(2027, 7, 9),
                note="Familie",
            ).exists()
        )

    def test_add_vacation_rejects_end_before_start(self):
        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "add_vacation",
                "year": "2027",
                "vacation_title": "Falsch",
                "vacation_start": "2027-07-09",
                "vacation_end": "2027-07-05",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertFalse(VacationPeriod.objects.filter(user=self.user).exists())
