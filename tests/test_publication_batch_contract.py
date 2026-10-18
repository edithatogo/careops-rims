import unittest

from scripts.publication_batch_contract import (
    validate_paged_batch,
    validate_update_allowlist,
)


class PublicationBatchContractTests(unittest.TestCase):
    def test_complete_pages_reconcile_count_and_keys(self):
        pages = [
            {"rows": [{"SourceKey": "PMID:1"}], "cursor_before": "", "cursor_after": "PMID:1"},
            {"rows": [{"SourceKey": "PMID:2"}], "cursor_before": "PMID:1", "cursor_after": "PMID:2"},
            {"rows": [], "cursor_before": "PMID:2", "cursor_after": "PMID:2"},
        ]
        self.assertEqual(validate_paged_batch(pages, expected_count=2, expected_keys=["PMID:1", "PMID:2"]), [])

    def test_partial_response_and_duplicate_key_fail_closed(self):
        pages = [
            {"rows": [{"SourceKey": "PMID:1"}], "cursor_before": "", "cursor_after": "PMID:1", "partial": True},
            {"rows": [{"SourceKey": "PMID:1"}], "cursor_before": "PMID:1", "cursor_after": "PMID:1"},
        ]
        errors = validate_paged_batch(pages, expected_count=2, expected_keys=["PMID:1", "PMID:2"])
        self.assertTrue(any("partial" in error for error in errors))
        self.assertTrue(any("duplicate" in error for error in errors))

    def test_missing_progress_and_wrong_independent_set_fail_closed(self):
        pages = [{"rows": [{"SourceKey": "PMID:1"}], "cursor_before": "", "cursor_after": ""}]
        errors = validate_paged_batch(pages, expected_count=1, expected_keys=["PMID:2"])
        self.assertTrue(any("continuation cursor" in error for error in errors))
        self.assertTrue(any("set does not match" in error for error in errors))

    def test_update_allowlist_protects_manual_fields(self):
        self.assertEqual(validate_update_allowlist(["LastObservedUTC", "OAUrl"]), [])
        errors = validate_update_allowlist(["ReviewStatus", "FirstObservedUTC", "Unexpected"])
        self.assertTrue(any("manual fields" in error for error in errors))
        self.assertTrue(any("outside" in error for error in errors))

    def test_independent_reconciliation_inputs_are_explicit(self):
        errors = validate_paged_batch([], expected_count=True, expected_keys=[""])
        self.assertTrue(any("expected count" in error for error in errors))
        self.assertTrue(any("blank key" in error for error in errors))

        errors = validate_paged_batch([], expected_count=-1, expected_keys=[])
        self.assertTrue(any("expected count" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
