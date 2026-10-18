import unittest
from pathlib import Path
import json
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.grants_ingestion import ingest_batches, parse_feed
from scripts.grants_sources import load_catalogue, require_enabled_source

class GrantsSourceTests(unittest.TestCase):
    def catalogue(self):
        return json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())

    def test_current_catalogue_separates_awards_metadata_and_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'catalogue.json'
            p.write_text(json.dumps(self.catalogue()))
            rows = {r['source_id']: r for r in load_catalogue(p)}
        self.assertEqual(rows['arc-awards-api']['reconciliation']['admission'], 'context_only')
        self.assertEqual(rows['queensland-grants-finder-catalogue-api']['reconciliation']['admission'], 'metadata_only')
        self.assertEqual(rows['queensland-health-qgip-review-candidates-api']['reconciliation']['admission'], 'candidate_only')

    def test_catalogue_rejects_unsafe_endpoints_and_identity_drift(self):
        for field, value in [('source_id', True), ('source_id', ' padded '),
                             ('authority_url', 'http://example.org'),
                             ('api_url', 'https://official.example@attacker.test/path'),
                             ('enabled', 'true'), ('health_status', 'unverified')]:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as d:
                rows = self.catalogue(); rows[0][field] = value
                p = Path(d) / 'catalogue.json'; p.write_text(json.dumps(rows))
                with self.assertRaises(ValueError): load_catalogue(p)

    def test_disabled_source_is_rejected_before_acquisition(self):
        with tempfile.TemporaryDirectory() as d:
            rows = self.catalogue(); rows[0]['enabled'] = False
            p = Path(d) / 'catalogue.json'; p.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError, 'source_disabled'):
                require_enabled_source(p, rows[0]['source_id'])

    def test_atom_and_rss_shapes_are_preserved_as_canonical_records(self):
        rss = """<rss><channel><item><guid>r1</guid><title>Call</title><link>https://example.org/call/</link><description>Summary</description><deadline>2027-04</deadline></item></channel></rss>"""
        atom = """<feed xmlns='http://www.w3.org/2005/Atom'><entry><id>a1</id><title>Call</title><link href='https://example.org/call'/><summary>Summary</summary></entry></feed>"""
        a = parse_feed(rss, source="R", retrieved_at="2026-09-20T00:00:00+10:00")[0]
        b = parse_feed(atom, source="A", retrieved_at="2026-09-20T00:00:00+10:00")[0]
        self.assertEqual(a["DeadlinePrecision"], "month")
        self.assertEqual(a["URL"], "https://example.org/call")
        self.assertEqual(b["Title"], "Call")
        self.assertEqual(a["RetrievedTimestampStatus"], "valid")

    def test_bad_source_does_not_discard_successful_batch(self):
        result = ingest_batches([
            {"source": "good", "retrieved_at": "2026-09-20T00:00:00Z", "records": [{"Title": "Good", "URL": "https://example.org/g"}]},
            {"source": "bad", "retrieved_at": "2026-09-20T00:00:00Z", "xml": "<broken"},
        ])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual([item["status"] for item in result["health"]], ["succeeded", "failed"])
        self.assertFalse(result["accepted"])

    def test_malformed_batch_object_fails_closed_explicitly(self):
        with self.assertRaisesRegex(ValueError, "batch must be an object"):
            ingest_batches([None])

    def test_api_shaped_records_require_link_and_timezone(self):
        result = ingest_batches([
            {"source": "bad", "retrieved_at": "2026-09-20T00:00:00Z", "records": [{"Title": "No link"}]},
            {"source": "also-bad", "retrieved_at": "2026-09-20T00:00:00", "records": [{"Title": "No timezone", "URL": "https://example.org/1"}]},
        ])
        self.assertEqual(result["records"], [])
        self.assertEqual([item["status"] for item in result["health"]], ["failed", "failed"])
        self.assertFalse(result["accepted"])

    def test_duplicate_feed_identity_fails_closed(self):
        xml = """<rss><channel>
        <item><guid>same</guid><title>One</title><link>https://example.org/1</link></item>
        <item><guid>same</guid><title>Two</title><link>https://example.org/2</link></item>
        </channel></rss>"""
        with self.assertRaisesRegex(ValueError, "duplicate source identity"):
            parse_feed(xml, source="R", retrieved_at="2026-09-20T00:00:00Z")

    def test_missing_feed_title_fails_closed(self):
        xml = """<rss><channel><item><guid>r1</guid><link>https://example.org/1</link></item></channel></rss>"""
        with self.assertRaisesRegex(ValueError, "missing title"):
            parse_feed(xml, source="R", retrieved_at="2026-09-20T00:00:00Z")

    def test_missing_feed_identity_fails_closed(self):
        xml = """<rss><channel><item><title>Unbound call</title></item></channel></rss>"""
        with self.assertRaisesRegex(ValueError, "missing source identity"):
            parse_feed(xml, source="R", retrieved_at="2026-09-20T00:00:00Z")

    def test_duplicate_normalized_identity_within_source_batch_fails_closed(self):
        xml = """<rss><channel>
        <item><title>Same call</title><link>https://example.org/same</link></item>
        <item><title>Same call revised</title><link>https://example.org/same</link></item>
        </channel></rss>"""
        with self.assertRaisesRegex(ValueError, "duplicate OpportunityKey"):
            parse_feed(xml, source="R", retrieved_at="2026-09-20T00:00:00Z")

    def test_duplicate_api_identity_within_source_batch_fails_closed(self):
        result = ingest_batches([{
            "source": "api",
            "retrieved_at": "2026-09-20T00:00:00Z",
            "records": [
                {"Title": "One", "URL": "https://example.org/same"},
                {"Title": "Two", "URL": "https://example.org/same"},
            ],
        }])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["health"][0]["status"], "failed")
        self.assertFalse(result["accepted"])

    def test_ingestion_identities_and_urls_are_not_coerced(self):
        with self.assertRaisesRegex(ValueError, "source must be a non-empty string"):
            parse_feed("<rss><channel><item><title>Call</title><link>https://example.org/1</link></item></channel></rss>", source=True, retrieved_at="2026-09-20T00:00:00Z")
        result = ingest_batches([{
            "source": True,
            "retrieved_at": "2026-09-20T00:00:00Z",
            "records": [{"Title": "Call", "URL": 7}],
        }])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["health"][0]["status"], "failed")

    def test_source_identity_rejects_surrounding_whitespace(self):
        with self.assertRaisesRegex(ValueError, "feed source must not have surrounding whitespace"):
            parse_feed(
                "<rss><channel><item><guid>r1</guid><title>Call</title><link>https://example.org/1</link></item></channel></rss>",
                source=" source-a",
                retrieved_at="2026-09-20T00:00:00Z",
            )
        result = ingest_batches([{
            "source": " source-a",
            "retrieved_at": "2026-09-20T00:00:00Z",
            "records": [{"Title": "Call", "URL": "https://example.org/1"}],
        }])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["health"][0]["status"], "failed")
        self.assertIn("surrounding whitespace", result["health"][0]["error"])

    def test_api_source_fields_are_not_stringified_before_validation(self):
        result = ingest_batches([{
            "source": "api",
            "retrieved_at": "2026-09-20T00:00:00Z",
            "records": [{"Title": True, "SourceID": 7, "URL": "https://example.org/1"}],
        }])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["health"][0]["status"], "failed")
        self.assertIn("must be a string", result["health"][0]["error"])

    def test_api_identity_and_url_fields_reject_surrounding_whitespace(self):
        for field, value in (("SourceID", " source-id"), ("ExternalID", "external-id "),
                             ("RoundID", " round-1 "), ("URL", " https://example.org/1")):
            with self.subTest(field=field):
                result = ingest_batches([{
                    "source": "api",
                    "retrieved_at": "2026-09-20T00:00:00Z",
                    "records": [{"Title": "Call", field: value, **({} if field == "URL" else {"URL": "https://example.org/1"})}],
                }])
                self.assertFalse(result["accepted"])
                self.assertEqual(result["health"][0]["status"], "failed")
                self.assertIn("surrounding whitespace", result["health"][0]["error"])

    def test_current_record_uses_newest_observation_but_preserves_review(self):
        from scripts.grants_registry import merge_observations
        rows = merge_observations([
            {"Source":"X", "SourceID":"1", "Title":"Old", "URL":"https://x/1", "RetrievedUTC":"2026-09-19T00:00:00Z", "ReviewStatus":"Reviewed", "ReviewNotes":"human note"},
            {"Source":"X", "SourceID":"1", "Title":"New", "URL":"https://x/1", "RetrievedUTC":"2026-09-20T00:00:00Z"},
        ])
        self.assertEqual(rows[0]["Title"], "New")
        self.assertEqual(rows[0]["ReviewStatus"], "Reviewed")
        self.assertEqual(rows[0]["ReviewNotes"], "human note")
        self.assertEqual(len(rows[0]["SourceObservations"]), 2)


if __name__ == "__main__":
    unittest.main()
