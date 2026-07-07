from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models import VacationHoliday, VacationPeriod, VacationYearSetting
from app.views.vacation import build_vacation_period_rows, calculate_vacation_days, parse_holiday_date, parse_holiday_line


class VacationPlannerCalculationTests(TestCase):
    def test_calculates_vacation_days_for_holidays_weekends_and_half_days(self):
        cases = [
            (
                "weekday holiday",
                date(2026, 7, 6),
                date(2026, 7, 10),
                {date(2026, 7, 8)},
                {
                    "total_days": 5,
                    "weekend_days": 0,
                    "holiday_weekdays": 1,
                    "holiday_deduction_days": Decimal("1"),
                    "vacation_days": Decimal("4"),
                },
            ),
            (
                "weekend holiday is not double counted",
                date(2026, 12, 24),
                date(2026, 12, 28),
                {date(2026, 12, 26), date(2026, 12, 28)},
                {
                    "total_days": 5,
                    "weekend_days": 2,
                    "holiday_weekdays": 1,
                    "holiday_deduction_days": Decimal("1"),
                    "vacation_days": Decimal("2"),
                },
            ),
            (
                "half day holiday",
                date(2027, 5, 10),
                date(2027, 5, 12),
                {date(2027, 5, 11): Decimal("0.5")},
                {
                    "total_days": 3,
                    "weekend_days": 0,
                    "holiday_weekdays": 1,
                    "holiday_deduction_days": Decimal("0.5"),
                    "vacation_days": Decimal("2.5"),
                },
            ),
        ]

        for label, start_date, end_date, holidays, expected in cases:
            with self.subTest(label):
                result = calculate_vacation_days(start_date, end_date, holidays)
                for key, value in expected.items():
                    self.assertEqual(result[key], value)

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

    def test_add_vacation_creates_period_and_defaults_blank_title(self):
        cases = [
            {
                "post_title": "Sommerurlaub",
                "expected_title": "Sommerurlaub",
                "start": "2027-07-05",
                "end": "2027-07-09",
                "note": "Familie",
            },
            {
                "post_title": "   ",
                "expected_title": "Urlaub",
                "start": "2027-08-02",
                "end": "2027-08-04",
                "note": "",
            },
        ]

        for case in cases:
            with self.subTest(case["expected_title"]):
                response = self.client.post(
                    reverse("vacation_planner"),
                    {
                        "action": "add_vacation",
                        "year": "2027",
                        "vacation_title": case["post_title"],
                        "vacation_start": case["start"],
                        "vacation_end": case["end"],
                        "vacation_note": case["note"],
                    },
                )

                self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
                self.assertTrue(
                    VacationPeriod.objects.filter(
                        user=self.user,
                        title=case["expected_title"],
                        start_date=date.fromisoformat(case["start"]),
                        end_date=date.fromisoformat(case["end"]),
                        note=case["note"],
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

    def test_save_year_setting_updates_total_days(self):
        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "save_year_setting",
                "year": "2027",
                "total_days": "28",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertEqual(
            VacationYearSetting.objects.get(user=self.user, year=2027).total_days,
            28,
        )

    def test_update_vacation_changes_period_fields(self):
        period = VacationPeriod.objects.create(
            user=self.user,
            title="Alt",
            start_date=date(2027, 6, 1),
            end_date=date(2027, 6, 3),
            note="Vorher",
        )

        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "update_vacation",
                "year": "2027",
                "vacation_id": str(period.id),
                "vacation_title": "Neu",
                "vacation_start": "2027-06-07",
                "vacation_end": "2027-06-11",
                "vacation_note": "Nachher",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        period.refresh_from_db()
        self.assertEqual(period.title, "Neu")
        self.assertEqual(period.start_date, date(2027, 6, 7))
        self.assertEqual(period.end_date, date(2027, 6, 11))
        self.assertEqual(period.note, "Nachher")

    def test_delete_vacation_removes_period(self):
        period = VacationPeriod.objects.create(
            user=self.user,
            title="Sommer",
            start_date=date(2027, 7, 5),
            end_date=date(2027, 7, 9),
        )

        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "delete_vacation",
                "year": "2027",
                "vacation_id": str(period.id),
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertFalse(VacationPeriod.objects.filter(id=period.id).exists())

    def test_update_holiday_rejects_duplicate_date(self):
        VacationHoliday.objects.create(user=self.user, date=date(2027, 1, 1), name="Neujahr")
        holiday = VacationHoliday.objects.create(user=self.user, date=date(2027, 5, 1), name="Alt")

        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "update_holiday",
                "year": "2027",
                "holiday_id": str(holiday.id),
                "holiday_name": "Doppelt",
                "holiday_date": "2027-01-01",
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        holiday.refresh_from_db()
        self.assertEqual(holiday.date, date(2027, 5, 1))
        self.assertEqual(holiday.name, "Alt")

    def test_delete_holiday_removes_holiday(self):
        holiday = VacationHoliday.objects.create(user=self.user, date=date(2027, 10, 3), name="Einheit")

        response = self.client.post(
            reverse("vacation_planner"),
            {
                "action": "delete_holiday",
                "year": "2027",
                "holiday_id": str(holiday.id),
            },
        )

        self.assertRedirects(response, f"{reverse('vacation_planner')}?year=2027")
        self.assertFalse(VacationHoliday.objects.filter(id=holiday.id).exists())

    def test_english_locale_renders_current_vacation_planner_labels(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("vacation_planner"), {"year": "2027"})

        self.assertContains(response, "New period")
        self.assertContains(response, "Saved periods")
        self.assertContains(response, "Not counted")
        self.assertContains(response, "Select a period to check the vacation days.")
