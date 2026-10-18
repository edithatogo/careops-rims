import unittest
from pathlib import Path
import json
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.grants_ingestion import ingest_batches, parse_feed
from scripts.grants_sources import load_catalogue


class GrantsSourceTests(unittest.TestCase):
    def test_catalogue_has_required_sources_and_explicit_health(self):
        rows = load_catalogue(Path(__file__).parents[1] / "config/grants-sources.json")
        self.assertGreaterEqual(len(rows), 13)
        self.assertTrue(all(row["last_verified"] for row in rows))
        ids = {row["source_id"] for row in rows}
        self.assertTrue({
            "qh-health-practitioner-research", "metro-south-research-support",
            "metro-north-research-grants", "torres-cape-research-support",
        } <= ids)

    def test_catalogue_rejects_invalid_urls_and_dates(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["authority_url"] = "not-a-url"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "valid authority_url"):
                load_catalogue(handle.name)

        rows[0]["authority_url"] = "https://example.org"
        rows[0]["last_verified"] = "not-a-date"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "invalid last_verified date"):
                load_catalogue(handle.name)

        rows[0]["last_verified"] = "2999-12-31"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "future last_verified date"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_non_string_source_id(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["source_id"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "source_id must be a non-empty string"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_surrounding_source_id_whitespace(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["source_id"] = " nhmrc"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_non_string_urls(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["authority_url"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "valid authority_url"):
                load_catalogue(handle.name)

        rows[0]["authority_url"] = "https://example.org/authority"
        arc = next(row for row in rows if row["source_id"] == "arc")
        arc["authority_url"] = "https://example.org/authority"
        arc["api_url"] = 7
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "api_url must be a string or null"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_surrounding_url_whitespace(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["authority_url"] = " https://example.org/authority"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "authority_url must not have surrounding whitespace"):
                load_catalogue(handle.name)

        rows[0]["authority_url"] = "https://example.org/authority"
        arc = next(row for row in rows if row["source_id"] == "arc")
        arc["api_url"] = "https://example.org/api "
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "api_url must not have surrounding whitespace"):
                load_catalogue(handle.name)

    def test_catalogue_freshness_uses_brisbane_date(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        today = datetime.now(ZoneInfo("Australia/Brisbane")).date().isoformat()
        self.assertTrue(all(row["last_verified"] <= today for row in rows))
        self.assertTrue(load_catalogue(Path(__file__).parents[1] / "config/grants-sources.json"))

    def test_api_catalogue_requires_valid_api_url(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        arc = next(row for row in rows if row["source_id"] == "arc")
        arc["api_url"] = "not-a-url"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "valid api_url"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_malformed_optional_metadata(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["record_kind"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "record_kind must be a non-empty string or null"):
                load_catalogue(handle.name)

        rows[0].pop("record_kind")
        rows[0]["sample_fixture"] = 7
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "sample_fixture must be a non-empty string or null"):
                load_catalogue(handle.name)

        rows[0].pop("sample_fixture")
        rows[0]["api_url"] = False
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "api_url must be a string or null"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_surrounding_api_url_whitespace_for_non_api_rows(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["api_url"] = " https://example.org/api"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "api_url must not have surrounding whitespace"):
                load_catalogue(handle.name)

    def test_catalogue_rejects_surrounding_optional_metadata_whitespace(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        rows[0]["record_kind"] = " awards_only"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "record_kind must be a non-empty string or null"):
                load_catalogue(handle.name)

        rows[0].pop("record_kind")
        rows[0]["sample_fixture"] = "fixture.json "
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "sample_fixture must be a non-empty string or null"):
                load_catalogue(handle.name)

    def test_arc_public_api_is_verified_as_awards_only(self):
        rows = load_catalogue(Path(__file__).parents[1] / "config/grants-sources.json")
        arc = next(row for row in rows if row["source_id"] == "arc")
        self.assertEqual(arc["intake"], "api")
        self.assertEqual(arc["health_status"], "verified_sample")
        self.assertTrue(arc["api_url"].startswith("https://dataportal.arc.gov.au/NCGP/API/grants"))
        self.assertEqual(arc["record_kind"], "awards_only")
        self.assertIn("not an open-opportunity calendar", arc["coverage"])

    def test_queensland_grants_finder_api_is_metadata_only(self):
        rows = load_catalogue(Path(__file__).parents[1] / "config/grants-sources.json")
        finder = next(row for row in rows if row["source_id"] == "queensland-grants-finder")
        self.assertEqual(finder["intake"], "api")
        self.assertEqual(finder["health_status"], "verified_sample")
        self.assertEqual(finder["record_kind"], "metadata_only")
        self.assertIn("does not expose opportunity rows", finder["coverage"])

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
