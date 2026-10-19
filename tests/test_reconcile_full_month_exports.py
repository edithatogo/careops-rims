"""Paired complete-export oracle; all inputs are synthetic assertions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_publication_register import assemble_paginated_export, export_errors, key_hash
from reconcile_full_month_exports import reconcile


def paged(rows, scope, generation="synthetic-generation"):
    return {
        "data_kind": "synthetic", "scope": scope,
        "source_snapshot_id": "synthetic-snapshot", "coverage_note": "Synthetic only",
        "generation_id": generation, "expected_keys_generation_id": generation,
        "expected_canonical_count": len(rows), "expected_canonical_keys": [r["CanonicalKey"] for r in rows],
        "expected_key_sha256": key_hash(rows),
        "pages": [{"page_number": 1, "generation_id": generation,
                   "has_more": False, "records": copy.deepcopy(rows)}],
    }


class PairedExportTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((ROOT / "tests/fixtures/webfirst-export-synthetic.json").read_text())["records"]
        self.full = paged(self.rows, {"mode": "all", "reporting_month": None})
        self.month_rows = [r for r in self.rows if r["PublicationMonth"] == "2026-08"]
        self.month = paged(self.month_rows, {"mode": "month", "reporting_month": "2026-08"})

    def _make_live(self):
        for envelope in (self.full, self.month):
            records = envelope['pages'][0]['records']
            for row in records:
                row['CanonicalKey'] = row['CanonicalKey'].replace('TEST:', 'PMID:')
                row['Title'] = row['Title'].replace('[SYNTHETIC] ', '')
            keys = [row['CanonicalKey'] for row in records]
            envelope['data_kind'] = 'live_export'
            envelope['expected_canonical_keys'] = keys
            envelope['expected_key_sha256'] = key_hash(records)

    def test_complete_partition_and_same_generation(self):
        result = reconcile(self.full, self.month)
        self.assertEqual(result["full_count"], len(self.rows))
        self.assertEqual(result["monthly_count"], len(self.month_rows))
        self.assertFalse(result["native_provenance_verified_by_this_script"])

    def test_rejects_missing_month_even_if_month_key_query_agrees(self):
        self.month = paged(self.month_rows[:-1], self.month["scope"])
        with self.assertRaisesRegex(ValueError, "missing_count=1") as caught:
            reconcile(self.full, self.month)
        self.assertNotIn(self.month_rows[-1]["CanonicalKey"], str(caught.exception))

    def test_rejects_independent_month_query_drift(self):
        self.month["expected_canonical_keys"] = []
        with self.assertRaisesRegex(ValueError, "independent canonical key set"):
            reconcile(self.full, self.month)

    def test_rejects_mixed_generation(self):
        self.month = paged(self.month_rows, self.month["scope"], "other-generation")
        with self.assertRaisesRegex(ValueError, "generation_id"):
            reconcile(self.full, self.month)

    def test_live_exports_require_query_and_refresh_correlation(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            row["CanonicalKey"] = row["CanonicalKey"].replace("TEST:", "PMID:")
            row["Title"] = row["Title"].replace("[SYNTHETIC] ", "")
        self.full = paged(rows, {"mode": "all", "reporting_month": None})
        self.month = paged([r for r in rows if r["PublicationMonth"] == "2026-08"],
                           {"mode": "month", "reporting_month": "2026-08"})
        self._make_live()
        fingerprint = hashlib.sha256(b'bound synthetic query bundle').hexdigest()
        self.full['extraction_contract_sha256'] = self.month['extraction_contract_sha256'] = fingerprint
        with self.assertRaisesRegex(ValueError, "query_version"):
            reconcile(self.full, self.month)
        self.full["query_version"] = self.month["query_version"] = "v1"
        with self.assertRaisesRegex(ValueError, "model_refresh_correlation"):
            reconcile(self.full, self.month)
        self.full["model_refresh_correlation"] = self.month["model_refresh_correlation"] = "refresh-1"
        fingerprint = hashlib.sha256(b'bound synthetic query bundle').hexdigest()
        self.full['extraction_contract_sha256'] = self.month['extraction_contract_sha256'] = fingerprint
        result = reconcile(self.full, self.month)
        self.assertEqual(result["query_version"], "v1")
        self.assertEqual(result['extraction_contract_sha256'], fingerprint)

    def test_live_exports_require_canonical_query_contract_fingerprint(self):
        self._make_live()
        with self.assertRaisesRegex(ValueError, 'canonical extraction_contract_sha256'):
            reconcile(self.full, self.month)
        self.full['extraction_contract_sha256'] = 'a' * 64
        self.month['extraction_contract_sha256'] = 'A' * 64
        with self.assertRaisesRegex(ValueError, 'canonical extraction_contract_sha256'):
            reconcile(self.full, self.month)

    def test_live_exports_reject_different_query_contract_fingerprints(self):
        self._make_live()
        self.full['extraction_contract_sha256'] = 'a' * 64
        self.month['extraction_contract_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'differ in extraction_contract_sha256'):
            reconcile(self.full, self.month)

    def test_rejects_mixed_refresh_even_if_keys_and_generation_match(self):
        self.full["model_refresh_correlation"] = "refresh-1"
        self.month["model_refresh_correlation"] = "refresh-2"
        with self.assertRaisesRegex(ValueError, "model_refresh_correlation"):
            reconcile(self.full, self.month)

    def test_rejects_same_key_with_changed_metadata(self):
        self.month["pages"][0]["records"][0]["Authors"] = "Changed authors"
        with self.assertRaisesRegex(ValueError, "Monthly metadata differs"):
            reconcile(self.full, self.month)

    def test_rejects_truncated_full_page_chain(self):
        self.full["pages"][0]["records"] = self.full["pages"][0]["records"][:-1]
        with self.assertRaisesRegex(ValueError, "Paginated records differ"):
            reconcile(self.full, self.month)

    def test_rejects_padded_independent_canonical_keys(self):
        self.full["expected_canonical_keys"][0] = " " + self.full["expected_canonical_keys"][0]
        with self.assertRaisesRegex(ValueError, "canonical unpadded keys"):
            reconcile(self.full, self.month)

    def test_rejects_padded_keys_in_source_pages(self):
        row = self.full["pages"][0]["records"][0]
        row["CanonicalKey"] = " " + row["CanonicalKey"]
        with self.assertRaisesRegex(ValueError, "noncanonical key"):
            reconcile(self.full, self.month)

    def test_rejects_nonprintable_key_characters_in_source_pages(self):
        row = self.full["pages"][0]["records"][0]
        row["CanonicalKey"] += "\u0085"
        with self.assertRaisesRegex(ValueError, "noncanonical key"):
            reconcile(self.full, self.month)



if __name__ == "__main__":
    unittest.main()
