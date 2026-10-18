import unittest

from scripts.grants_calendar_changes import change_record


class GrantsCalendarChangeTests(unittest.TestCase):
    def test_create_and_cancellation_are_explicit(self):
        current = {"DeadlineKey": "DL:1", "OpportunityKey": "OP:1", "Revision": "v1", "CalculatedDate": "2026-10-01", "Cancelled": False, "SourceURL": "https://example.org/1", "ReviewStatus": "Needs Review"}
        created = change_record(None, current, observed_utc="2026-09-22T00:00:00Z")
        self.assertEqual(created["ChangeType"], "created")
        cancelled = dict(current, Revision="v2", Cancelled=True)
        record = change_record(current, cancelled, observed_utc="2026-09-23T00:00:00Z")
        self.assertEqual(record["ChangeType"], "cancelled")
        self.assertEqual(record["PreviousRevision"], "v1")

    def test_unchanged_revision_is_not_emitted(self):
        row = {"DeadlineKey": "DL:2", "OpportunityKey": "OP:2", "Revision": "v1", "CalculatedDate": "2026-10-01", "Cancelled": False, "ReviewStatus": "Included"}
        self.assertIsNone(change_record(row, dict(row), observed_utc="2026-09-22T00:00:00Z"))

    def test_input_types_and_evidence_fail_closed(self):
        row = {"DeadlineKey": "DL:3", "OpportunityKey": "OP:3", "Revision": "v1", "CalculatedDate": "2026-10-01", "Cancelled": False, "ReviewStatus": "Included"}
        with self.assertRaisesRegex(ValueError, "SourceURL"):
            change_record(None, dict(row, SourceURL="not-a-url"), observed_utc="2026-09-22T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "Cancelled"):
            change_record(None, dict(row, Cancelled="false"), observed_utc="2026-09-22T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "identities must match"):
            change_record(row, dict(row, OpportunityKey="OP:other"), observed_utc="2026-09-22T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "timezone"):
            change_record(None, row, observed_utc="2026-09-22T00:00:00")

    def test_change_identities_and_source_url_reject_surrounding_whitespace(self):
        row = {"DeadlineKey": "DL:3", "OpportunityKey": "OP:3", "Revision": "v1", "CalculatedDate": "2026-10-01", "Cancelled": False, "SourceURL": "https://example.org/3", "ReviewStatus": "Included"}
        with self.assertRaisesRegex(ValueError, "DeadlineKey"):
            change_record(None, dict(row, DeadlineKey=" DL:3"), observed_utc="2026-09-22T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "SourceURL"):
            change_record(None, dict(row, SourceURL=" https://example.org/3"), observed_utc="2026-09-22T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
