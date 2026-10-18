import unittest

from scripts.grants_calendar import build_icalendar, event_uid, project_event


POLICY = {"PolicyKey": "CHHHS-INTAKE", "Version": "2026.09", "OrganisationKey": "CHHHS", "AnchorKind": "application_close", "LeadDays": 2, "HolidayCalendarVersion": "QLD-2026", "EffectiveFrom": "2026-01-01", "CalendarOrBusinessDays": "business", "HolidayDates": ["2026-09-25"]}


class GrantsCalendarTests(unittest.TestCase):
    def test_exact_date_projects_institutional_tentative_event(self):
        row = {"OpportunityKey": "GRANT:1", "Title": "Call, one", "URL": "https://example.org/call", "Source": "NHMRC", "Deadline": "2026-09-28", "DeadlinePrecision": "day", "Status": "Open"}
        event = project_event(row, POLICY)
        self.assertEqual(event["Date"], "2026-09-23")
        self.assertEqual(event["Anchor"], "institutional")
        self.assertEqual(event["ExternalDeadline"], "2026-09-28")
        self.assertEqual(event["Status"], "TENTATIVE")
        self.assertIn("Call\\, one", build_icalendar([row], POLICY, generated_utc="2026-09-20T04:00:00Z"))

    def test_unknown_or_partial_date_is_omitted(self):
        row = {"OpportunityKey": "GRANT:2", "Title": "Unknown", "Deadline": "2026-09", "DeadlinePrecision": "month"}
        self.assertIsNone(project_event(row, POLICY))
        self.assertNotIn("GRANT:2", build_icalendar([row], POLICY, generated_utc="2026-09-20T04:00:00Z"))

    def test_cancellation_is_explicit_and_uid_changes_with_policy(self):
        row = {"OpportunityKey": "GRANT:3", "Title": "Cancelled", "URL": "https://example.org/cancelled", "Deadline": "2026-10-01", "DeadlinePrecision": "day", "Status": "Cancelled"}
        event = project_event(row, POLICY)
        self.assertEqual(event["Status"], "CANCELLED")
        self.assertNotEqual(event_uid("GRANT:3", "institutional", "CHHHS-INTAKE", "2026.09"), event_uid("GRANT:3", "institutional", "CHHHS-INTAKE", "2026.10"))

    def test_duplicate_event_uid_fails_closed(self):
        row = {"OpportunityKey": "GRANT:4", "Title": "Duplicate", "URL": "https://example.org/duplicate", "Deadline": "2026-10-01", "DeadlinePrecision": "day"}
        with self.assertRaisesRegex(ValueError, "duplicate calendar event UID"):
            build_icalendar([row, dict(row)], POLICY, generated_utc="2026-09-20T04:00:00Z")

    def test_exact_date_requires_authoritative_url_and_key(self):
        with self.assertRaisesRegex(ValueError, r"requires an HTTP\(S\) URL"):
            project_event({"OpportunityKey": "GRANT:5", "Title": "No link", "URL": "not-a-url", "Deadline": "2026-10-01", "DeadlinePrecision": "day"}, POLICY)
        with self.assertRaisesRegex(ValueError, "missing OpportunityKey"):
            project_event({"Title": "No key", "URL": "https://example.org/no-key", "Deadline": "2026-10-01", "DeadlinePrecision": "day"}, POLICY)

    def test_exact_date_identity_and_url_reject_surrounding_whitespace(self):
        for field, value in (("OpportunityKey", " GRANT:1"), ("URL", "https://example.org/grant ")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                    project_event({"OpportunityKey": "GRANT:1", "Title": "Call", "URL": "https://example.org/call", "Deadline": "2026-10-01", "DeadlinePrecision": "day", field: value}, POLICY)

    def test_calendar_inputs_are_not_coerced(self):
        with self.assertRaisesRegex(ValueError, "must be a string"):
            project_event({"OpportunityKey": 5, "Title": "Call", "URL": "https://example.org/call", "Deadline": "2026-10-01", "DeadlinePrecision": "day"}, POLICY)
        with self.assertRaisesRegex(ValueError, "URL"):
            project_event({"OpportunityKey": "GRANT:6", "Title": "Call", "URL": 5, "Deadline": "2026-10-01", "DeadlinePrecision": "day"}, POLICY)
        with self.assertRaisesRegex(ValueError, "Status"):
            project_event({"OpportunityKey": "GRANT:6", "Title": "Call", "URL": "https://example.org/call", "Status": False, "Deadline": "2026-10-01", "DeadlinePrecision": "day"}, POLICY)

    def test_uncertain_dates_do_not_hide_malformed_descriptive_fields(self):
        with self.assertRaisesRegex(ValueError, "Title"):
            project_event({"OpportunityKey": "GRANT:7", "Title": False, "Deadline": "2026-10", "DeadlinePrecision": "month"}, POLICY)

    def test_exact_day_rejects_impossible_date(self):
        with self.assertRaisesRegex(ValueError, "not a valid date"):
            project_event({"OpportunityKey": "GRANT:8", "Title": "Impossible", "URL": "https://example.org/impossible", "Deadline": "2026-02-30", "DeadlinePrecision": "day"}, POLICY)

    def test_icalendar_rejects_impossible_generation_timestamp(self):
        with self.assertRaisesRegex(ValueError, "valid UTC timestamp"):
            build_icalendar([], POLICY, generated_utc="2026-99-99T25:61:61Z")

    def test_icalendar_escapes_crlf_in_display_fields(self):
        row = {"OpportunityKey": "GRANT:9", "Title": "Line one\r\nLine two", "URL": "https://example.org/call", "Source": "NHMRC\r\nreview", "Deadline": "2026-10-01", "DeadlinePrecision": "day"}
        output = build_icalendar([row], POLICY, generated_utc="2026-09-20T04:00:00Z")
        self.assertNotIn("Line one\r", output)
        self.assertIn("SUMMARY:Line one\\n\\nLine two", output)
        self.assertIn("CATEGORIES:NHMRC\\n\\nreview", output)


if __name__ == "__main__":
    unittest.main()
