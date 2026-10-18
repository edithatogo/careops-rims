import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from grants_registry import merge_observations, normalize_opportunity, normalize_url, sharepoint_field_map


class GrantsRegistryTests(unittest.TestCase):
    def test_rss_atom_and_api_shapes_normalize_to_same_key(self):
        rss = {"Source": "NHMRC", "SourceID": "G-1", "title": "Tropical Health Grant", "link": "HTTPS://Funder.example/opportunity/1/", "deadline": "2027-04"}
        api = {"Source": "NHMRC", "ExternalID": "G-1", "Title": "Tropical Health Grant", "URL": "https://funder.example/opportunity/1", "ClosingDate": "2027-04"}
        self.assertEqual(normalize_opportunity(rss)["OpportunityKey"], normalize_opportunity(api)["OpportunityKey"])
        self.assertEqual(normalize_opportunity(rss)["DeadlinePrecision"], "month")

    def test_missing_date_stays_unknown(self):
        item = normalize_opportunity({"Source": "DGR", "Title": "Open call", "URL": "https://example.org/call"})
        self.assertIsNone(item["Deadline"])
        self.assertEqual(item["DeadlinePrecision"], "unknown")

    def test_duplicate_merge_retains_source_observations(self):
        records = merge_observations([
            {"Source": "A", "SourceID": "1", "Title": "Call", "URL": "https://a.example/1"},
            {"Source": "A", "SourceID": "1", "Title": "Call", "URL": "https://a.example/1"},
        ])
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]["SourceObservations"]), 2)

    def test_source_isolation_and_sharepoint_mapping(self):
        record = normalize_opportunity({"Source": "B", "SourceID": "2", "Title": "Call", "URL": "https://b.example/2"})
        mapped = sharepoint_field_map(record)
        self.assertEqual(mapped["Source"], "B")
        self.assertIn("EvidenceHash", mapped)
        self.assertEqual(normalize_url("HTTPS://B.EXAMPLE/2/"), "https://b.example/2")

    def test_naive_or_invalid_observation_timestamp_is_reviewed(self):
        naive = normalize_opportunity({"Title": "Call", "URL": "https://example.org/call", "RetrievedUTC": "2026-09-20T12:00:00"})
        invalid = normalize_opportunity({"Title": "Call", "URL": "https://example.org/call", "RetrievedUTC": "not-a-timestamp"})
        self.assertEqual(naive["RetrievedTimestampStatus"], "missing_timezone")
        self.assertEqual(invalid["RetrievedTimestampStatus"], "invalid")
        self.assertEqual(naive["ReviewStatus"], "Needs Review")
        self.assertEqual(invalid["ReviewStatus"], "Needs Review")

    def test_non_http_url_is_not_actionable_evidence(self):
        item = normalize_opportunity({
            "Source": "X", "SourceID": "1", "Title": "Call", "URL": "javascript:alert(1)",
            "RetrievedUTC": "2026-09-20T00:00:00Z",
        })
        self.assertEqual(item["URL"], "")
        self.assertEqual(item["ReviewStatus"], "Needs Review")

    def test_identity_and_display_fields_are_not_stringified(self):
        for field, value in (("SourceID", True), ("Title", 7), ("URL", ["https://example.org"]), ("ReviewStatus", False)):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"field {field}"):
                    normalize_opportunity({field: value})

    def test_amount_rejects_structured_or_boolean_values_but_accepts_numeric(self):
        for value in ({"currency": "AUD", "value": 100}, [100], True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "field Amount"):
                    normalize_opportunity({"Title": "Call", "URL": "https://example.org/call", "Amount": value})
        self.assertEqual(normalize_opportunity({"Title": "Call", "URL": "https://example.org/call", "Amount": 100000})["Amount"], "100000")

    def test_source_row_url_is_preserved_as_distinct_evidence(self):
        item = normalize_opportunity({
            "Source": "X", "SourceID": "1", "Title": "Call",
            "URL": "https://example.org/calendar", "SourceRowURL": "https://example.org/call/1",
        })
        self.assertEqual(item["SourceRowURL"], "https://example.org/call/1")
        self.assertEqual(sharepoint_field_map(item)["SourceRowURL"], "https://example.org/call/1")


if __name__ == "__main__":
    unittest.main()
