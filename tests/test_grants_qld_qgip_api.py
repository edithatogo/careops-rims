import unittest
import json
import io
import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from scripts.grants_qld_qgip_api import (
    API_BASE, INDEX_RESOURCE_ID, PACKAGE_ID, PACKAGE_NAME, RESOURCE_ID, PAGE_SIZE,
    MAX_RESPONSE_BYTES, _get_json, build_review_queue, fetch_review_queue,
    compare_snapshots, validate_catalogue_pointer,
    validate_catalogue_schema, main,
)


def row(source_id, *, status="Open", assistance="Grant"):
    return {
        "Service ID": source_id,
        "Program title": f"Program {source_id}",
        "Sub-program title": None,
        "Purpose": "Public synthetic fixture purpose",
        "Status": status,
        "Assistance type1": assistance,
        "Assistance type2": None,
        "Assistance type3": None,
        "Closing date (date format)": "2027-04-30",
        "Closing date (text)": "30 April 2027",
        "Website": "https://www.health.qld.gov.au/funding",
        "Eligibility": "Synthetic eligibility text",
    }


def snapshot(rows, *, updated="2026-09-01T00:00:00Z", retrieved="2026-09-25T00:00:00Z"):
    package = {"id": PACKAGE_ID, "license_id": "CC-BY-3.0"}
    resource = {"id": RESOURCE_ID, "package_id": PACKAGE_ID, "last_modified": updated}
    pages = []
    for offset in range(0, max(1, len(rows)), PAGE_SIZE):
        pages.append({"total": len(rows), "total_was_estimated": False, "offset": offset,
                      "records": rows[offset:offset + PAGE_SIZE]})
    return build_review_queue(package=package, resource=resource, pages=pages,
                              retrieved_at=retrieved)


class QGIPRawRetentionTests(unittest.TestCase):
    def test_closed_and_unknown_fields_survive_before_candidate_filter(self):
        rows = [row("open"), row("closed", status="Closed")]
        rows[1]["Future source field"] = {"nested": [None, "Unicode café", 0, False]}
        result = snapshot(rows)
        self.assertEqual([r["SourceID"] for r in result["records"]], ["open"])
        retained = result["raw_source"]["pages"][0]["records"]
        self.assertEqual(retained, rows)
        rows[1]["Future source field"]["nested"].append("later mutation")
        self.assertEqual(len(retained[1]["Future source field"]["nested"]), 4)
        self.assertFalse(result["accepted"])

    def test_http_capture_retains_exact_full_envelope_bytes(self):
        body = b'{ "success": true, "future_envelope": [null, false], "result": {"future_field": 1} }\n'
        receipts = []
        result = _get_json("datastore_search", {"resource_id": RESOURCE_ID},
                           lambda *_a, **_k: FakeResponse(body), retained_responses=receipts)
        self.assertEqual(result, {"future_field": 1})
        self.assertEqual(base64.b64decode(receipts[0]["body_base64"]), body)
        self.assertEqual(receipts[0]["body_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(receipts[0]["body_bytes"], len(body))

    def test_complete_fetch_retains_both_reads_and_metadata_bodies(self):
        opener, calls = fetch_fixture()
        result = fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)
        raw = result["raw_source"]
        self.assertEqual(sum(len(p["records"]) for p in raw["pages"]), 101)
        self.assertEqual(len(raw["http_responses"]), len(calls))
        envelopes = [json.loads(base64.b64decode(r["body_base64"]))
                     for r in raw["http_responses"]]
        self.assertTrue(all(e["success"] for e in envelopes))
        self.assertEqual(len(raw["http_responses"]), 12)


class FakeResponse:
    def __init__(self, body, *, status=200, content_type="application/json"):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self, limit=-1):
        return self.body[:limit]


def api_result(result):
    return {"success": True, "result": result}


def fetch_fixture(*, drift=False, package_drift=False, index_drift=False,
                  schema_drift=False, initial_schema_drift=None,
                  same_count_row_drift=False):
    rows = [row(f"id-{number}") for number in range(101)]
    metadata = {"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                "last_modified": "2026-09-01T00:00:00Z", "hash": "fixture-hash"}
    calls = []
    call_counts = {"package_show": 0, "index": 0, "datastore_info": 0}

    def opener(request, timeout=20):
        parsed = urlparse(request.full_url)
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        action = parsed.path.rsplit("/", 1)[-1]
        calls.append((action, params, timeout))
        if action == "datastore_search" and params.get("resource_id") == INDEX_RESOURCE_ID:
            call_counts["index"] += 1
            mapped_resource = "changed-resource" if index_drift and call_counts["index"] > 1 else RESOURCE_ID
            body = api_result({"total": 1, "total_was_estimated": False,
                               "records": [{"Agency": "QH", "Resource": mapped_resource}]})
        elif action == "package_show":
            call_counts["package_show"] += 1
            package_name = "changed-package" if package_drift and call_counts["package_show"] > 1 else PACKAGE_NAME
            body = api_result({"id": PACKAGE_ID, "name": package_name, "license_id": "CC-BY-3.0",
                               "resources": [{"id": RESOURCE_ID}]})
        elif action == "resource_show":
            selected = dict(metadata)
            if drift and sum(call[0] == "resource_show" for call in calls) > 1:
                selected["hash"] = "changed-hash"
            body = api_result(selected)
        elif action == "datastore_info":
            call_counts["datastore_info"] += 1
            fields = [{"id": field_id, "type": "text"} for field_id in (
                "Service ID", "Status", "Assistance type1", "Assistance type2", "Assistance type3")]
            if initial_schema_drift and call_counts["datastore_info"] == 1:
                field_id, replacement = initial_schema_drift
                if replacement is None:
                    fields = [field for field in fields if field["id"] != field_id]
                else:
                    next(field for field in fields if field["id"] == field_id)["id"] = replacement
            if schema_drift and call_counts["datastore_info"] > 1:
                fields[1]["type"] = "numeric"
            body = api_result({"fields": fields})
        elif action == "datastore_search":
            offset = int(params["offset"])
            current_rows = list(rows)
            if same_count_row_drift and sum(
                call[0] == "datastore_search" and call[1].get("resource_id") == RESOURCE_ID
                for call in calls
            ) > 2:
                current_rows[-1] = row("replacement")
            page_rows = current_rows[offset:offset + PAGE_SIZE]
            body = api_result({"total": len(rows), "total_was_estimated": False,
                               "offset": offset, "records": page_rows})
        else:
            raise AssertionError(f"unexpected CKAN action {action}")
        return FakeResponse(body)

    return opener, calls


class QueenslandQGIPAdapterTests(unittest.TestCase):
    def test_datastore_schema_requires_service_id_field_without_claiming_immutability(self):
        schema = validate_catalogue_schema({"fields": [
            {"id": field_id, "type": "text", "schema": {"uniquekey": False}}
            for field_id in ("Service ID", "Status", "Assistance type1", "Assistance type2", "Assistance type3")
        ]})
        self.assertEqual(schema, tuple((field_id, "text") for field_id in (
            "Service ID", "Status", "Assistance type1", "Assistance type2", "Assistance type3")))
        with self.assertRaisesRegex(ValueError, "classification field is missing or changed: Service ID"):
            validate_catalogue_schema({"fields": [{"id": "_id", "type": "int"}]})

    def test_datastore_schema_rejects_missing_renamed_or_nontext_classification_fields(self):
        required = ("Service ID", "Status", "Assistance type1", "Assistance type2", "Assistance type3")
        for field_id, replacement, expected in (
                ("Assistance type2", None, "Assistance type2"),
                ("Assistance type3", "Assistance type 3", "Assistance type3"),
                ("Status", "numeric", "Status")):
            fields = [{"id": name, "type": "text"} for name in required]
            if replacement is None:
                fields = [field for field in fields if field["id"] != field_id]
            elif replacement == "numeric":
                next(field for field in fields if field["id"] == field_id)["type"] = replacement
            else:
                next(field for field in fields if field["id"] == field_id)["id"] = replacement
            with self.subTest(field=field_id, replacement=replacement), self.assertRaisesRegex(
                    ValueError, f"classification field is missing or changed: {expected}"):
                validate_catalogue_schema({"fields": fields})

    def test_grants_finder_index_must_preserve_the_qh_resource_mapping(self):
        validate_catalogue_pointer({"total": 1, "total_was_estimated": False,
                                    "records": [{"Agency": "QH", "Resource": RESOURCE_ID}]})
        with self.assertRaisesRegex(ValueError, "mapping changed"):
            validate_catalogue_pointer({"total": 1, "total_was_estimated": False,
                                        "records": [{"Agency": "QH", "Resource": "other"}]})
        with self.assertRaisesRegex(ValueError, "exact"):
            validate_catalogue_pointer({"total": 1, "total_was_estimated": True,
                                        "records": [{"Agency": "QH", "Resource": RESOURCE_ID}]})

    def test_only_explicit_open_grant_rows_become_review_candidates(self):
        result = snapshot([
            row("open-grant"),
            row("closed-grant", status="Closed"),
            row("open-loan", assistance="Loan"),
        ])
        self.assertEqual(result["source_total"], 3)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["snapshot_complete"])
        self.assertEqual(len(result["records"]), 1)
        candidate = result["records"][0]
        self.assertEqual(candidate["SourceID"], "open-grant")
        self.assertEqual(candidate["RecordKind"], "OpportunityCandidate")
        self.assertEqual(candidate["ReviewStatus"], "Needs Review")
        self.assertEqual(candidate["Status"], "Needs Review")
        self.assertEqual(candidate["SourceStatus"], "Open")
        self.assertEqual(candidate["IdentityStatus"], "CandidateUnproven")
        self.assertEqual(candidate["FreshnessStatus"], "Needs Review")
        self.assertRegex(candidate["EvidenceHash"], r"^[0-9a-f]{64}$")
        self.assertRegex(candidate["BusinessEvidenceHash"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["snapshot_hash"], r"^[0-9a-f]{64}$")
        self.assertNotIn("OpportunityKey", candidate)
        self.assertNotIn("_id", candidate)

    def test_non_text_purpose_or_eligibility_fails_closed(self):
        for field in ("Purpose", "Eligibility"):
            for invalid in (0, False, [], {}):
                candidate = row(f"bad-{field}-{type(invalid).__name__}")
                candidate[field] = invalid
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, f"QGIP {field} must be text or null"):
                        snapshot([candidate])

    def test_missing_optional_purpose_and_eligibility_remain_empty_text(self):
        candidate = row("optional-text")
        candidate["Purpose"] = None
        candidate["Eligibility"] = None
        projected = snapshot([candidate])["records"][0]
        self.assertEqual(projected["Purpose"], "")
        self.assertEqual(projected["EligibilitySource"], "")

    def test_malformed_closing_date_fields_cannot_be_hidden_by_fallback(self):
        for field, invalid in (("Closing date (date format)", False),
                               ("Closing date (date format)", 0),
                               ("Closing date (date format)", []),
                               ("Closing date (text)", False),
                               ("Closing date (text)", 0),
                               ("Closing date (text)", [])):
            candidate = row(f"bad-closing-{field}-{type(invalid).__name__}")
            candidate[field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaisesRegex(
                    ValueError, "QGIP closing date must be text or null"):
                snapshot([candidate])

    def test_annual_snapshot_older_than_one_year_is_marked_for_review(self):
        result = snapshot([row("old")], updated="2025-09-01T00:00:00Z")
        self.assertEqual(result["records"][0]["FreshnessStatus"], "Needs Review")
        self.assertEqual(result["records"][0]["ReviewStatus"], "Needs Review")

    def test_incomplete_or_shifted_page_rejects_entire_snapshot(self):
        package = {"id": PACKAGE_ID, "license_id": "CC-BY-3.0"}
        resource = {"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                    "last_modified": "2026-09-01T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "page count"):
            build_review_queue(package=package, resource=resource,
                               pages=[{"total": 101, "total_was_estimated": False,
                                       "offset": 0, "records": [row("a")] }],
                               retrieved_at="2026-09-25T00:00:00Z")

    def test_estimated_count_cannot_claim_snapshot_completeness(self):
        with self.assertRaisesRegex(ValueError, "explicitly exact"):
            build_review_queue(package={"id": PACKAGE_ID, "license_id": "CC-BY-3.0"},
                               resource={"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                                         "last_modified": "2026-09-01T00:00:00Z"},
                               pages=[{"total": 0, "total_was_estimated": True,
                                       "offset": 0, "records": []}],
                               retrieved_at="2026-09-25T00:00:00Z")

    def test_duplicate_or_missing_service_id_rejects_all_rows(self):
        for rows, error in (([row("same"), row("same")], "duplicate Service ID"),
                            ([row("")], "missing Service ID"),
                            ([row(" padded ", status="Closed")], "padded Service ID"),
                            ([row("same"), row(" same ")], "padded Service ID")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                snapshot(rows)

    def test_assistance_type_requires_exact_normalized_grant_category(self):
        result = snapshot([row("ordinary-grant", assistance="grant  "),
                           row("guarantee", assistance="Guarantee"),
                           row("grant-program", assistance="Research grant program")])
        self.assertEqual([item["SourceID"] for item in result["records"]], ["ordinary-grant"])

    def test_builder_rejects_boolean_and_noninteger_totals(self):
        package = {"id": PACKAGE_ID, "license_id": "CC-BY-3.0"}
        resource = {"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                    "last_modified": "2026-09-01T00:00:00Z"}
        for value in (True, "0", 0.0):
            with self.subTest(total=value), self.assertRaisesRegex(ValueError, "exact integer total"):
                build_review_queue(package=package, resource=resource,
                                   pages=[{"total": value, "total_was_estimated": False,
                                           "offset": 0, "records": []}],
                                   retrieved_at="2026-09-25T00:00:00Z")

    def test_fetch_pages_exactly_and_emits_deterministic_snapshot_hash(self):
        opener, calls = fetch_fixture()
        result = fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)
        page_calls = [(params["limit"], params["offset"]) for action, params, _ in calls
                      if action == "datastore_search" and params.get("resource_id") == RESOURCE_ID]
        self.assertEqual(page_calls, [("100", "0"), ("100", "100"),
                                      ("100", "0"), ("100", "100")])
        self.assertEqual(result["source_total"], 101)
        self.assertEqual(len(result["records"]), 101)
        opener_again, _ = fetch_fixture()
        self.assertEqual(result["snapshot_hash"], fetch_review_queue(
            retrieved_at="2026-09-25T00:00:00Z", opener=opener_again)["snapshot_hash"])

    def test_fetch_rejects_resource_drift_during_paging(self):
        opener, _ = fetch_fixture(drift=True)
        with self.assertRaisesRegex(ValueError, "changed during snapshot"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)

    def test_fetch_rejects_same_count_content_drift_across_full_reads(self):
        opener, _ = fetch_fixture(same_count_row_drift=True)
        with self.assertRaisesRegex(ValueError, "rows changed between complete page reads"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)

    def test_fetch_rejects_datastore_schema_drift_during_paging(self):
        opener, _ = fetch_fixture(schema_drift=True)
        with self.assertRaisesRegex(ValueError, "classification field is missing or changed: Status|schema changed during snapshot"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)

    def test_fetch_rejects_initial_classification_schema_drift_before_reading_rows(self):
        opener, calls = fetch_fixture(initial_schema_drift=("Assistance type3", None))
        with self.assertRaisesRegex(ValueError, "classification field is missing or changed: Assistance type3"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)
        opportunity_page_calls = [call for call in calls
                                  if call[0] == "datastore_search" and
                                  call[1].get("resource_id") == RESOURCE_ID]
        self.assertEqual(opportunity_page_calls, [])

    def test_fetch_rejects_package_mapping_drift_during_paging(self):
        opener, _ = fetch_fixture(package_drift=True)
        with self.assertRaisesRegex(ValueError, "package mapping changed|package changed during snapshot"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)

    def test_fetch_rejects_grants_finder_pointer_drift_during_paging(self):
        opener, _ = fetch_fixture(index_drift=True)
        with self.assertRaisesRegex(ValueError, "mapping changed|pointer changed during snapshot"):
            fetch_review_queue(retrieved_at="2026-09-25T00:00:00Z", opener=opener)

    def test_same_day_digest_equality_is_only_repeatability_not_lifecycle_evidence(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable")], retrieved="2026-09-25T16:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["comparison"], "same_day_digest_equal")
        self.assertEqual(comparison["temporal_evidence"], "same_day_repeatability_only")
        self.assertEqual(comparison["added_service_ids"], [])
        self.assertEqual(comparison["removed_service_ids"], [])
        self.assertEqual(comparison["changed_service_ids"], [])
        self.assertFalse(comparison["service_id_identity_proven"])
        self.assertFalse(comparison["authoritative_lifecycle_semantics_proven"])
        self.assertFalse(comparison["canonical_admission"])

    def test_later_equal_digest_proves_only_no_change_between_dated_observations(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable")], retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["comparison"], "later_date_digest_equal")
        self.assertEqual(comparison["temporal_evidence"], "no_change_detected_across_dates")
        self.assertFalse(comparison["authoritative_lifecycle_semantics_proven"])

    def test_reordered_api_rows_are_not_mistaken_for_changed_source_content(self):
        prior = snapshot([row("first"), row("second")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("second"), row("first")], retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertFalse(comparison["ordered_snapshot_digest_equal"])
        self.assertEqual(comparison["comparison"], "later_date_digest_equal")
        self.assertEqual(comparison["added_service_ids"], [])
        self.assertEqual(comparison["removed_service_ids"], [])
        self.assertEqual(comparison["changed_service_ids"], [])
        self.assertFalse(comparison["canonical_admission"])

    def test_ckan_ordinal_rebuild_is_not_program_content_change(self):
        before = row("stable")
        before["_id"] = 1
        after = dict(before, _id=99)
        prior = snapshot([before], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([after], retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["comparison"], "later_date_digest_equal")
        self.assertFalse(comparison["raw_row_hashes_equal"])
        self.assertEqual(comparison["changed_service_ids"], [])
        self.assertEqual(comparison["raw_changed_service_ids"], ["stable"])
        self.assertEqual(comparison["business_changed_service_ids"], [])
        self.assertEqual(comparison["ckan_ordinal_only_changed_service_ids"], ["stable"])
        self.assertEqual(comparison["review_candidates_business_changed"], [])
        self.assertEqual(comparison["review_candidates_unchanged"], ["stable"])
        self.assertFalse(comparison["canonical_admission"])

    def test_review_candidate_transitions_are_separate_from_source_presence(self):
        prior = snapshot([row("closing"), row("opening", status="Closed"), row("stable")],
                         retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("closing", status="Closed"), row("opening"), row("stable")],
                           retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["added_service_ids"], [])
        self.assertEqual(comparison["removed_service_ids"], [])
        self.assertEqual(comparison["review_candidates_entered"], ["opening"])
        self.assertEqual(comparison["review_candidates_exited"], ["closing"])
        self.assertEqual(comparison["review_candidates_unchanged"], ["stable"])
        self.assertFalse(comparison["canonical_admission"])

    def test_review_candidate_evidence_cannot_disagree_with_complete_source_map(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable")], retrieved="2026-09-26T09:00:00Z")
        current["records"][0]["BusinessEvidenceHash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differs from source-row evidence"):
            compare_snapshots(prior, current)
        current = snapshot([row("stable")], retrieved="2026-09-26T09:00:00Z")
        current["records"].append(dict(current["records"][0]))
        with self.assertRaisesRegex(ValueError, "invalid source identity"):
            compare_snapshots(prior, current)

    def test_older_complete_receipt_without_candidate_business_hash_remains_comparable(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        prior["records"][0].pop("BusinessEvidenceHash")
        current = snapshot([row("stable")], retrieved="2026-09-26T09:00:00Z")
        self.assertEqual(compare_snapshots(prior, current)["review_candidates_unchanged"], ["stable"])

    def test_business_change_is_distinct_from_ordinal_change(self):
        before = row("stable")
        before["_id"] = 1
        after = dict(before, _id=99, Status="Closed")
        prior = snapshot([before], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([after], retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["business_changed_service_ids"], ["stable"])
        self.assertEqual(comparison["ckan_ordinal_only_changed_service_ids"], [])
        self.assertEqual(comparison["comparison"], "later_date_content_difference")
        self.assertTrue(comparison["content_changed_without_source_update"])

    def test_content_change_with_source_update_is_not_unannounced(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        changed = row("stable", status="Closed")
        current = snapshot([changed], updated="2026-09-26T00:00:00Z",
                           retrieved="2026-09-26T09:00:00Z")
        self.assertFalse(compare_snapshots(prior, current)["content_changed_without_source_update"])

    def test_ckan_naive_resource_timestamp_records_utc_basis(self):
        current = snapshot([row("stable")], updated="2026-09-01T00:00:00")
        self.assertEqual(current["source_updated_utc"], "2026-09-01T00:00:00Z")
        self.assertEqual(current["source_timestamp_basis"], "ckan_utc_naive")

    def test_missing_business_hashes_fail_closed(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable")], retrieved="2026-09-26T09:00:00Z")
        del current["business_row_hashes"]
        with self.assertRaisesRegex(ValueError, "business row hashes"):
            compare_snapshots(prior, current)

    def test_resource_update_without_row_change_is_metadata_only_evidence(self):
        prior = snapshot([row("same")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("same")], updated="2026-09-26T00:00:00Z",
                           retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["temporal_evidence"], "source_metadata_changed_across_dates")
        self.assertEqual(comparison["changed_service_ids"], [])
        self.assertFalse(comparison["authoritative_lifecycle_semantics_proven"])

    def test_equivalent_utc_source_timestamp_encodings_are_not_metadata_change(self):
        prior = snapshot([row("same")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("same")], retrieved="2026-09-26T09:00:00Z")
        current["source_updated_utc"] = "2026-09-01T10:00:00+10:00"
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["comparison"], "later_date_digest_equal")
        self.assertEqual(comparison["temporal_evidence"], "no_change_detected_across_dates")

    def test_comparator_rejects_boolean_source_total(self):
        prior = snapshot([row("same")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("same")], retrieved="2026-09-26T09:00:00Z")
        current["source_total"] = True
        with self.assertRaisesRegex(ValueError, "row count"):
            compare_snapshots(prior, current)

    def test_future_source_update_cannot_create_a_review_snapshot(self):
        with self.assertRaisesRegex(ValueError, "later than snapshot retrieval"):
            snapshot([row("stable")], updated="2026-09-26T00:00:00Z",
                     retrieved="2026-09-25T09:00:00Z")

    def test_snapshot_comparison_rejects_source_timestamp_regression(self):
        prior = snapshot([row("stable")], updated="2026-09-24T00:00:00Z",
                         retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable")], updated="2026-09-23T00:00:00Z",
                           retrieved="2026-09-26T09:00:00Z")
        with self.assertRaisesRegex(ValueError, "regressed"):
            compare_snapshots(prior, current)

    def test_later_digest_reports_added_removed_and_changed_ids_without_claiming_identity(self):
        prior = snapshot([row("retained"), row("removed"), row("changed")],
                         retrieved="2026-09-25T09:00:00Z")
        modified = row("changed")
        modified["Closing date (date format)"] = "2027-05-31"
        current = snapshot([row("retained"), row("added"), modified],
                           retrieved="2026-09-26T09:00:00Z")
        comparison = compare_snapshots(prior, current)
        self.assertEqual(comparison["comparison"], "later_date_content_difference")
        self.assertEqual(comparison["temporal_evidence"], "source_content_changed_across_dates")
        self.assertEqual(comparison["added_service_ids"], ["added"])
        self.assertEqual(comparison["removed_service_ids"], ["removed"])
        self.assertEqual(comparison["changed_service_ids"], ["changed"])
        self.assertFalse(comparison["observed_absence_is_tombstone"])
        self.assertFalse(comparison["service_id_identity_proven"])
        self.assertFalse(comparison["canonical_admission"])

    def test_snapshot_comparison_rejects_same_or_reversed_time_and_incomplete_input(self):
        prior = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        same_time = snapshot([row("stable")], retrieved="2026-09-25T09:00:00Z")
        earlier = snapshot([row("stable")], retrieved="2026-09-24T09:00:00Z")
        with self.assertRaisesRegex(ValueError, "must be later"):
            compare_snapshots(prior, same_time)
        with self.assertRaisesRegex(ValueError, "must be later"):
            compare_snapshots(prior, earlier)
        incomplete = dict(prior, snapshot_complete=False)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            compare_snapshots(prior, incomplete)

    def test_snapshot_comparison_rejects_padded_observation_keys(self):
        prior = snapshot([row("stable", status="Closed")], retrieved="2026-09-25T09:00:00Z")
        current = snapshot([row("stable", status="Closed")], retrieved="2026-09-26T09:00:00Z")
        padded = dict(current)
        padded["source_row_hashes"] = {" stable": current["source_row_hashes"]["stable"]}
        padded["business_row_hashes"] = {" stable": current["business_row_hashes"]["stable"]}
        with self.assertRaisesRegex(ValueError, "valid per-Service-ID hashes"):
            compare_snapshots(prior, padded)

    def test_json_fetch_enforces_http_content_type_and_byte_limits(self):
        with self.assertRaisesRegex(ValueError, "HTTP 429"):
            _get_json("anything", {}, lambda *_a, **_k: FakeResponse(b"{}", status=429))
        with self.assertRaisesRegex(ValueError, "not JSON"):
            _get_json("anything", {}, lambda *_a, **_k: FakeResponse(b"{}", content_type="text/html"))
        oversized = b"x" * (MAX_RESPONSE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "byte limit"):
            _get_json("anything", {}, lambda *_a, **_k: FakeResponse(oversized))

    def test_wrong_package_resource_or_license_fails_closed(self):
        package = {"id": "wrong", "license_id": "CC-BY-3.0"}
        resource = {"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                    "last_modified": "2026-09-01T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "identity or expected licence"):
            build_review_queue(package=package, resource=resource,
                               pages=[{"total": 0, "total_was_estimated": False, "offset": 0, "records": []}],
                               retrieved_at="2026-09-25T00:00:00Z")

    def test_candidate_requires_text_fields_and_timezone_aware_observation(self):
        malformed = row("bad")
        malformed["Program title"] = ["unexpected"]
        with self.assertRaisesRegex(ValueError, "titles must be text"):
            snapshot([malformed])
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            build_review_queue(package={"id": PACKAGE_ID, "license_id": "CC-BY-3.0"},
                               resource={"id": RESOURCE_ID, "package_id": PACKAGE_ID,
                                         "last_modified": "2026-09-01T00:00:00Z"},
                               pages=[{"total": 0, "total_was_estimated": False, "offset": 0, "records": []}],
                               retrieved_at="2026-09-25T00:00:00")

    def test_cli_help_and_default_invocation_do_not_fetch_live_data(self):
        fetcher = Mock(side_effect=AssertionError("unexpected live API call"))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([], fetcher=fetcher), 0)
        self.assertIn("--fetch", output.getvalue())
        fetcher.assert_not_called()

        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"], fetcher=fetcher)
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--fetch", output.getvalue())
        fetcher.assert_not_called()

    def test_cli_fetch_requires_explicit_flag(self):
        fetcher = Mock(return_value={"snapshot_complete": True})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--fetch"], fetcher=fetcher), 0)
        fetcher.assert_called_once_with()
        self.assertIn('"snapshot_complete": true', output.getvalue())

    def test_cli_fetch_never_prints_retained_source(self):
        payload = {"snapshot_complete": True, "source_total": 1, "records": [],
                   "raw_source": {"http_responses": ["PRIVATE_RAW_SENTINEL"]}}
        output = io.StringIO()
        with redirect_stdout(output):
            main(["--fetch"], fetcher=Mock(return_value=payload))
        self.assertNotIn("PRIVATE_RAW_SENTINEL", output.getvalue())
        self.assertNotIn("raw_source", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["source_total"], 1)

    def test_cli_output_rejects_outside_private_before_fetch(self):
        fetcher = Mock()
        with TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                main(["--fetch", "--output", str(Path(directory) / "raw.json")], fetcher=fetcher)
        fetcher.assert_not_called()

    def test_cli_output_exclusive_private_receipt(self):
        root = Path(__file__).resolve().parents[1] / "private/ops"
        root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=root) as directory:
            path = Path(directory) / "snapshot.json"
            payload = {"snapshot_complete": True, "records": [], "raw_source": "retained"}
            with redirect_stdout(io.StringIO()):
                main(["--fetch", "--output", str(path)], fetcher=Mock(return_value=payload))
            self.assertEqual(json.loads(path.read_text()), payload)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            fetcher = Mock()
            with self.assertRaises(SystemExit):
                main(["--fetch", "--output", str(path)], fetcher=fetcher)
            fetcher.assert_not_called()
            self.assertEqual(json.loads(path.read_text()), payload)

    def test_cli_fetch_obeys_catalogue_disabled_switch(self):
        catalogue = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        next(row for row in catalogue if row["source_id"] == "queensland-health-qgip-review-candidates-api")["enabled"] = False
        fetcher = Mock(side_effect=AssertionError("disabled source must not fetch"))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            path.write_text(json.dumps(catalogue))
            with self.assertRaises(SystemExit) as raised:
                main(["--fetch", "--catalogue", str(path)], fetcher=fetcher)
        self.assertEqual(raised.exception.code, 2)
        fetcher.assert_not_called()

    def test_direct_qgip_fetch_obeys_catalogue_disabled_switch(self):
        catalogue = json.loads((Path(__file__).parents[1] / "config/grants-sources.json").read_text())
        next(row for row in catalogue if row["source_id"] == "queensland-health-qgip-review-candidates-api")["enabled"] = False
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            path.write_text(json.dumps(catalogue))
            with self.assertRaisesRegex(ValueError, "source_disabled"):
                fetch_review_queue(catalogue_path=path,
                                   opener=lambda *_args, **_kwargs: self.fail("network called"))


if __name__ == "__main__":
    unittest.main()
