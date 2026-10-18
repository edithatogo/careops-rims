import json
import hashlib
import re
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dora_activity import DATASTORE_SEARCH, PACKAGE_SHOW, SOURCE_FIELDS, collect, select_resource
from collect_pubmed import canonical_json
from export_dora_activity import EXPORT_FIELDS, activity_key, build_rows


def record(project_id="1001", record_id=7):
    values = {name: f"value-{index}" for index, name in enumerate(SOURCE_FIELDS)}
    values["Project ID"] = project_id
    values["Full Project Title"] = "Synthetic DORA activity"
    return {"_id": record_id, **values}


class DoraActivityTests(unittest.TestCase):
    def fake_fetcher(self, url, params):
        if url == PACKAGE_SHOW:
            return {
                "name": "database-of-research-activity-dora",
                "id": "package-1",
                "title": "Database of Research Activity - DoRA",
                "metadata_modified": "2026-09-08T07:55:39Z",
                "resources": [{
                    "id": "resource-1", "name": "current", "format": "CSV",
                    "last_modified": "2026-09-08T07:55:28Z", "created": "2026-09-08T07:55:28Z",
                    "url": "https://example.invalid/current.csv", "hash": "abc", "datastore_active": True,
                }],
            }
        self.assertEqual(url, DATASTORE_SEARCH)
        fields = [{"id": "_id"}] + [{"id": name} for name in SOURCE_FIELDS]
        if params["offset"] == 0:
            return {"fields": fields, "records": [record("1001", 7), record("1002", 8)], "total": 3}
        return {"fields": fields, "records": [record("1003", 9)], "total": 3}

    def test_collects_all_pages_and_preserves_every_source_field(self):
        with tempfile.TemporaryDirectory() as folder:
            output = collect(Path(folder) / "activity", self.fake_fetcher, page_size=2)
            records = json.loads((output / "records.json").read_text())
            receipt = json.loads((output / "receipt.json").read_text())
        self.assertEqual(len(records), 3)
        self.assertEqual(set(records[0]), {"_id", *SOURCE_FIELDS})
        self.assertEqual(receipt["expected_count"], 3)
        self.assertTrue(receipt["raw_source_fields_preserved"])

    def test_schema_drift_is_rejected(self):
        def drift(url, params):
            result = self.fake_fetcher(url, params)
            if url == DATASTORE_SEARCH:
                result["fields"][-1]["id"] = "Unexpected field"
            return result
        with self.assertRaisesRegex(ValueError, "schema drift"):
            with tempfile.TemporaryDirectory() as folder:
                collect(Path(folder) / "activity", drift, page_size=2)

    def test_active_resource_id_must_be_a_non_empty_string(self):
        package = {
            "resources": [{
                "id": 7, "format": "CSV", "datastore_active": True,
                "last_modified": "2026-09-08T07:55:28Z",
            }]
        }
        with self.assertRaisesRegex(ValueError, "invalid id"):
            select_resource(package)

    def test_export_adds_provenance_without_dropping_source_columns(self):
        envelope = {
            "schema_version": "dora-activity-v1",
            "source_payload": {"resource": {"id": "resource-1", "name": "current", "url": "https://example.invalid/current.csv", "last_modified": "2026-09-08"}},
            "observed_at": "2026-09-20T00:00:00+00:00",
            "expected_count": 1,
            "retrieved_count": 1,
            "records": [record()],
        }
        rows = build_rows(envelope)
        self.assertEqual(set(rows[0]), set(EXPORT_FIELDS))
        self.assertEqual(rows[0]["Project ID"], "1001")
        self.assertEqual(rows[0]["DORAActivityKey"], "dora-activity:resource-1:7")

    def test_project_id_may_repeat_but_source_id_may_not(self):
        with tempfile.TemporaryDirectory() as folder:
            output = collect(Path(folder) / "activity", lambda url, params: (
                self.fake_fetcher(url, params) if url != DATASTORE_SEARCH else {
                    "fields": [{"id": "_id"}] + [{"id": name} for name in SOURCE_FIELDS],
                    "records": [record("same-project", 7), record("same-project", 8)],
                    "total": 2,
                }
            ), page_size=2)
            rows = json.loads((output / "records.json").read_text())
        self.assertEqual([row["Project ID"] for row in rows], ["same-project", "same-project"])

        def duplicate_source_id(url, params):
            result = self.fake_fetcher(url, params)
            if url == DATASTORE_SEARCH:
                result["records"] = [record("1001", 7), record("1002", 7)]
                result["total"] = 2
            return result
        with self.assertRaisesRegex(ValueError, "source _ids"):
            with tempfile.TemporaryDirectory() as folder:
                collect(Path(folder) / "activity", duplicate_source_id, page_size=2)

    def test_source_id_must_be_scalar_and_non_boolean(self):
        for invalid_id in (True, {"row": 7}, [7]):
            def invalid_source_id(url, params, invalid_id=invalid_id):
                result = self.fake_fetcher(url, params)
                if url == DATASTORE_SEARCH:
                    result["records"] = [record("1001", invalid_id)]
                    result["total"] = 1
                return result
            with self.subTest(invalid_id=invalid_id), self.assertRaisesRegex(ValueError, "no source _id"):
                with tempfile.TemporaryDirectory() as folder:
                    collect(Path(folder) / "activity", invalid_source_id, page_size=2)

    def test_source_id_rejects_surrounding_whitespace(self):
        def padded_source_id(url, params):
            result = self.fake_fetcher(url, params)
            if url == DATASTORE_SEARCH:
                result["records"] = [record("1001", " 7")]
                result["total"] = 1
            return result
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                collect(Path(folder) / "activity", padded_source_id, page_size=2)

    def test_rims_schema_declares_every_source_field(self):
        schema = json.loads((ROOT / "config/dora-activity-registry.schema.json").read_text())
        names = {field["name"] for field in schema["fields"]}
        self.assertTrue(set(SOURCE_FIELDS).issubset(names))
        self.assertIn("DORAActivityKey", names)
        self.assertIn("DORARecordID", names)
        fields = {field["name"]: field for field in schema["fields"]}
        self.assertTrue(fields["DORAActivityKey"]["unique"])

    def test_rims_query_rejects_duplicate_activity_keys(self):
        query = (ROOT / "config/DoraActivityRegistry.m").read_text()
        self.assertIn('List.Distinct(Keys)', query)
        self.assertIn('DORAActivityKey values are not unique', query)

    def test_rims_query_projects_every_schema_field(self):
        schema = json.loads((ROOT / "config/dora-activity-registry.schema.json").read_text())
        query = (ROOT / "config/DoraActivityRegistry.m").read_text()
        selected = query.split("Selected = Table.SelectColumns(Registry, {", 1)[1].split("}, MissingField.Error)", 1)[0]
        projected = set(re.findall(r'"([^"]+)"', selected))
        self.assertEqual(projected, {field["name"] for field in schema["fields"]})

    def test_rims_query_fails_closed_on_missing_columns(self):
        query = (ROOT / "config/DoraActivityRegistry.m").read_text()
        self.assertIn("MissingField.Error", query)
        self.assertNotIn("MissingField.UseNull", query)

    def test_export_rejects_coerced_provenance_types(self):
        envelope = {
            "schema_version": "dora-activity-v1",
            "source_payload": {"resource": {"id": "resource-1", "url": "https://example.invalid/current.csv"}},
            "observed_at": "2026-09-20T00:00:00+00:00",
            "expected_count": 1,
            "retrieved_count": 1,
            "records": [record()],
        }
        for field, value in (("retrieved_count", "1"), ("expected_count", "1"), ("observed_at", 123),):
            malformed = dict(envelope)
            malformed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "invalid|observation time"):
                build_rows(malformed)
        malformed = dict(envelope)
        malformed["source_payload"] = {"resource": {"id": {"id": 1}, "url": "https://example.invalid/current.csv"}}
        with self.assertRaisesRegex(ValueError, "resource id"):
            build_rows(malformed)

    def test_activity_key_rejects_boolean_or_structured_resource_ids(self):
        for resource_id in (True, {"id": "resource-1"}, ""):
            with self.subTest(resource_id=resource_id), self.assertRaisesRegex(ValueError, "resource id"):
                activity_key(resource_id, record())

    def test_export_rejects_unusable_url_or_timestamp_provenance(self):
        envelope = {
            "schema_version": "dora-activity-v1",
            "source_payload": {"resource": {"id": "resource-1", "url": "https://example.invalid/current.csv"}},
            "observed_at": "2026-09-20T00:00:00+00:00",
            "expected_count": 1,
            "retrieved_count": 1,
            "records": [record()],
        }
        malformed_url = dict(envelope)
        malformed_url["source_payload"] = {"resource": {"id": "resource-1", "url": "not-a-url"}}
        with self.assertRaisesRegex(ValueError, r"HTTP\(S\)"):
            build_rows(malformed_url)
        malformed_timestamp = dict(envelope)
        malformed_timestamp["observed_at"] = "2026-09-20T00:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_rows(malformed_timestamp)

    def test_export_rejects_partial_receipt_counts(self):
        envelope = {
            "schema_version": "dora-activity-v1",
            "source_payload": {"resource": {"id": "resource-1", "url": "https://example.invalid/current.csv"}},
            "observed_at": "2026-09-20T00:00:00+00:00",
            "expected_count": 2,
            "retrieved_count": 1,
            "records": [record()],
        }
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            build_rows(envelope)

    def test_export_verifies_present_receipt_hashes(self):
        records = [record()]
        envelope = {
            "schema_version": "dora-activity-v1",
            "source_payload": {"resource": {"id": "resource-1", "url": "https://example.invalid/current.csv"}},
            "observed_at": "2026-09-20T00:00:00+00:00",
            "expected_count": 1,
            "retrieved_count": 1,
            "records": records,
            "records_sha256": hashlib.sha256(canonical_json(records).encode("utf-8")).hexdigest(),
            "record_id_sha256": hashlib.sha256(canonical_json(["7"]).encode("utf-8")).hexdigest(),
        }
        self.assertEqual(len(build_rows(envelope)), 1)
        envelope["records_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "records_sha256"):
            build_rows(envelope)


if __name__ == "__main__":
    unittest.main()
