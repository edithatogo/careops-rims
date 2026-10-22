import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone

from scripts.prepare_query_projection_archive import build_raw_archive_extension, FOLDER, RAW_PAGE_LIMIT, _walk
from tests.test_prepare_pubmed_raw_source_capture import chunks

MODEL = "00000000-0000-4000-8000-000000000001"
WORKSPACE = "00000000-0000-4000-8000-000000000002"
BATCH = "00000000-0000-4000-8000-000000000003"
REQUEST = "00000000-0000-4000-8000-000000000004"
NOW = datetime(2026, 10, 13, 2, tzinfo=timezone.utc)


def baseline():
    def operation(op, parameters, previous=None):
        return {"type": "OpenApiConnection", "inputs": {
            "host": {"operationId": op, "connectionName": "existing-qualified-connector"},
            "parameters": parameters}, "runAfter": {previous: ["Succeeded"]} if previous else {}}
    return {"schemaVersion": "1.0.0.0", "properties": {
        "connectionReferences": {"existing": {"connection": {"name": "fixture-reference"}}},
        "definition": {"triggers": {"manual": {"type": "Request", "kind": "Button"}},
            "actions": {
                "Read_current_validation": operation("ExecuteDatasetQuery", {
                    "groupid": WORKSPACE, "datasetid": MODEL, "specification/query": 'EVALUATE ROW("Fixture",1)'}),
                "Batch": {"type": "Compose", "inputs": BATCH, "runAfter": {"Read_current_validation": ["Succeeded"]}},
                "Get_file_content_using_path": operation("GetFileContentByPath", {"path": FOLDER + "/fixture.json"}, "Batch"),
                "Existing_marker_branch": {"type": "If", "expression": True, "runAfter": {"Batch": ["Succeeded"]}, "actions": {},
                    "else": {"actions": {"Create_file": operation("CreateFile", {"folderPath": FOLDER, "name": "fixture.json", "body": "fixture"})}}},
                "Accepted_commit": {"type": "Compose", "inputs": "existing accepted commit", "runAfter": {"Existing_marker_branch": ["Succeeded"]}},
            }}}}


def capture(status="accepted"):
    rows = chunks(b'{"unmapped":{"future":null}}')
    return {"kind": "pubmed_raw_archive_capture_v1", "native_capture": False,
        "batch_id": BATCH, "workspace_id": WORKSPACE, "model_id": MODEL,
        "source_request_id": REQUEST, "source_started_at_utc": "2026-10-13T00:59:00Z",
        "source_completed_at_utc": "2026-10-13T01:01:00Z", "source_scope": ["PubMedSourceSnapshot"],
        "source_capture_definition_sha256": "a" * 64,
        "independent_response_count": 1, "independent_chunk_count": len(rows),
        "expected_requests": [{"endpoint": "efetch.fcgi", "request": {"db": "pubmed", "id": "1"}}],
        "typed_status": status, "typed_projection_failures": 0 if status == "accepted" else 1,
        "typed_audit_counts": {"rows": 9, "distinct_checks": 9, "expected_checks": 9, "failed_rows": 0},
        "pages": [{"rows": rows, "after": [-1, -1]}, {"rows": [], "after": [0, 0]}]}


class RawArchiveExtensionTests(unittest.TestCase):
    def build(self, document=None, receipt=None):
        return build_raw_archive_extension(document or baseline(), receipt or capture(), test_only=True, now=NOW)

    def test_prefix_preserves_trigger_connections_and_every_original_action_except_entry_dependency(self):
        old = baseline()
        frozen = copy.deepcopy(old)
        new, evidence = self.build(old)
        self.assertEqual(old, frozen)
        self.assertEqual(new["properties"]["connectionReferences"], old["properties"]["connectionReferences"])
        self.assertEqual(new["properties"]["definition"]["triggers"], old["properties"]["definition"]["triggers"])
        actions = new["properties"]["definition"]["actions"]
        for name, original in old["properties"]["definition"]["actions"].items():
            changed = copy.deepcopy(actions[name])
            changed["runAfter"] = original["runAfter"]
            self.assertEqual(changed, original)
        self.assertEqual(actions["Read_current_validation"]["runAfter"], {"RawStage_Require_accepted_projection": ["Succeeded"]})
        self.assertFalse(evidence["native_written"])
        self.assertFalse(evidence["routine_automation_accepted"])

    def test_rejected_capture_is_staged_before_acceptance_gate_and_has_no_new_commit_marker(self):
        new, evidence = self.build(receipt=capture("rejected"))
        actions = new["properties"]["definition"]["actions"]
        gate = actions["RawStage_Require_accepted_projection"]
        self.assertIn("RAW_TYPED_GENERATION_REJECTED", gate["inputs"])
        self.assertEqual(gate["runAfter"], {"RawStage_Descriptor_Require_exact_readback": ["Succeeded"]})
        self.assertEqual(evidence["observation_descriptor"]["typed_status"], "rejected")
        self.assertFalse(evidence["observation_descriptor"]["accepted_commit"])
        self.assertTrue(all(not f["name"].startswith("commit-") for f in evidence["files"]))

    def test_logical_audit_failure_is_retained_without_being_treated_as_accepted(self):
        c = capture("rejected")
        c["typed_projection_failures"] = 0
        c["typed_audit_counts"]["failed_rows"] = 1
        new, evidence = self.build(receipt=c)
        self.assertEqual(evidence["observation_descriptor"]["typed_status"], "rejected")
        self.assertIn("'rejected'", new["properties"]["definition"]["actions"]["RawStage_Require_accepted_projection"]["inputs"])
        c["typed_status"] = "accepted"
        with self.assertRaisesRegex(ValueError, "contradicts"):
            self.build(receipt=c)

    def test_existing_file_is_replay_checked_or_fails_and_creation_requires_explicit_404(self):
        new, _ = self.build()
        branch = new["properties"]["definition"]["actions"]["RawStage_Pages"]["actions"]["RawStage_Page_Has_rows"]["actions"]["RawStage_Page_Exists"]
        self.assertIn("RAW_ARCHIVE_CONFLICT", branch["actions"]["RawStage_Page_Require_replay"]["inputs"])
        otherwise = branch["else"]["actions"]
        self.assertIn("404", otherwise["RawStage_Page_Require_absent"]["inputs"])
        self.assertEqual(otherwise["RawStage_Page_Write"]["runAfter"], {"RawStage_Page_Require_absent": ["Succeeded"]})

    def test_source_pages_are_compared_to_the_frozen_capture_before_each_write(self):
        new, _ = self.build()
        loop = new["properties"]["definition"]["actions"]["RawStage_Pages"]
        actions = loop["actions"]
        self.assertIn("RAW_SOURCE_GENERATION_DRIFT", actions["RawStage_Page_Require_current_capture"]["inputs"])
        self.assertEqual(actions["RawStage_Page_Has_rows"]["runAfter"], {"RawStage_Page_Require_current_capture": ["Succeeded"]})
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        self.assertEqual(actions["RawStage_Page_Has_rows"]["actions"]["RawStage_Page_Existing"]["runAfter"], {"RawStage_Page_Content": ["Succeeded"]})

    def test_connector_date_coercion_cannot_change_fractional_timestamp_text_at_rest(self):
        # Native page 97 failed because the connector changed .350 into .35.
        # The transport must protect actual source text, without substituting
        # an expected timestamp or relaxing the existing exact header check.
        for fraction in ("350", "460", "000"):
            with self.subTest(fraction=fraction):
                c = capture()
                timestamp = "2026-10-13T01:00:00." + fraction + "+00:00"
                for row in c["pages"][0]["rows"]:
                    row["RawAcquiredUTC"] = timestamp
                new, evidence = self.build(receipt=c)
                actions = new["properties"]["definition"]["actions"]
                self.assertIn('"RAWUTC|" & PubMedSourceSnapshot[RawAcquiredUTC]',
                              actions["RawStage_Page_query_template"]["inputs"])
                loop = actions["RawStage_Pages"]["actions"]
                self.assertIn("RAWUTC|", loop["RawStage_Page_Bad_timestamp_transport"]["inputs"]["where"])
                self.assertIn("RAW_TIMESTAMP_TRANSPORT_INVALID", loop["RawStage_Page_Require_timestamp_transport"]["inputs"])
                self.assertEqual(loop["RawStage_Page_Rows"]["runAfter"],
                                 {"RawStage_Page_Require_timestamp_transport": ["Succeeded"]})
                self.assertEqual(loop["RawStage_Page_Rows"]["inputs"]["select"]["[RawAcquiredUTC]"],
                                 "@substring(item()?['[RawAcquiredUTC]'],7)")
                page = next(f for f in evidence["files"] if "-PubMedRawResponseChunks-" in f["name"])
                stored = json.loads(page["content"])
                self.assertEqual(stored, [{"[" + k + "]": v for k, v in row.items()}
                                          for row in c["pages"][0]["rows"]])
                self.assertNotIn("RAWUTC|", page["content"])
                self.assertIn("contains(outputs('RawStage_ResponseHeaders'),item())",
                              loop["RawStage_Page_Header_drift"]["inputs"]["where"])

    def test_large_capture_uses_constant_graph_and_never_embeds_payloads(self):
        small, _ = self.build()
        rows = chunks(b"x" * 4000000)
        c = capture()
        c["independent_chunk_count"] = len(rows)
        c["pages"] = []
        cursor = [-1, -1]
        for start in range(0, len(rows), RAW_PAGE_LIMIT):
            page = rows[start:start+RAW_PAGE_LIMIT]
            c["pages"].append({"after": cursor, "rows": page})
            cursor = [page[-1]["RawResponseIndex"], page[-1]["RawChunkIndex"]]
        c["pages"].append({"after": cursor, "rows": []})
        large, evidence = self.build(receipt=c)
        small_actions = list(_walk(small["properties"]["definition"]["actions"]))
        large_actions = list(_walk(large["properties"]["definition"]["actions"]))
        self.assertEqual(len(small_actions), len(large_actions))
        self.assertLess(len(large_actions), 100)
        self.assertNotIn(rows[0]["RawPayloadBase64"][:100], json.dumps(large))
        self.assertFalse(evidence["payloads_embedded_in_definition"])
        self.assertGreater(evidence["observation_descriptor"]["data_file_count"], 100)
        self.assertEqual(len(evidence["observation_descriptor"]["file_parts"]), 2)

    def test_independent_counts_request_coverage_and_terminal_page_are_required(self):
        cases = []
        for field, value in [("independent_response_count", 2), ("independent_chunk_count", True), ("expected_requests", [])]:
            c = capture(); c[field] = value; cases.append(c)
        c = capture(); c["pages"] = c["pages"][:-1]; cases.append(c)
        for c in cases:
            with self.assertRaises(ValueError):
                self.build(receipt=c)

    def test_empty_nonterminal_pages_missing_chunks_and_wrong_cursor_fail(self):
        for field in ("empty", "missing", "cursor"):
            c = capture()
            if field == "empty": c["pages"].insert(0, {"rows": [], "after": [-1, -1]})
            if field == "missing": c["pages"][0]["rows"][0]["RawChunkCount"] = 2
            if field == "cursor": c["pages"][-1]["after"] = [1, 0]
            with self.assertRaises(ValueError):
                self.build(receipt=c)

    def test_model_batch_or_folder_drift_and_raw_action_collision_fail(self):
        for case in ("model", "batch", "folder", "collision"):
            b = baseline()
            a = b["properties"]["definition"]["actions"]
            if case == "model": a["Read_current_validation"]["inputs"]["parameters"]["datasetid"] = WORKSPACE
            if case == "batch": a["Batch"]["inputs"] = REQUEST
            if case == "folder": a["Existing_marker_branch"]["else"]["actions"]["Create_file"]["inputs"]["parameters"]["folderPath"] = "/unapproved"
            if case == "collision": a["RawStage_Collision"] = {"type": "Compose", "inputs": "fixture", "runAfter": {}}
            with self.assertRaises(ValueError):
                self.build(document=b)

    def test_rejected_generation_retains_its_own_batch_without_rebasing_last_good_typed_writer(self):
        c = capture("rejected")
        c["batch_id"] = REQUEST
        new, evidence = self.build(receipt=c)
        self.assertEqual(new["properties"]["definition"]["actions"]["Batch"]["inputs"], BATCH)
        self.assertEqual(evidence["observation_descriptor"]["batch_id"], REQUEST)
        self.assertFalse(evidence["typed_manifest_bound_to_raw_r1"])

    def test_accepted_raw_and_typed_source_generation_mismatch_fails_before_staging(self):
        b = baseline()
        b["properties"]["definition"]["actions"]["Expected_manifest"] = {
            "type": "Compose", "inputs": {"BatchID": BATCH, "ModelID": MODEL,
            "ProcessingChain": {"steps": [{"role": "source_materialization", "type": "DataOnly",
                "tables": ["PubMedSourceSnapshot"], "status": "Completed", "request_id": BATCH,
                "started_at_utc": "2026-10-13T00:59:00Z", "completed_at_utc": "2026-10-13T01:01:00Z"}]}},
            "runAfter": {"Batch": ["Succeeded"]}}
        with self.assertRaisesRegex(ValueError, "generation differ"):
            self.build(document=b)

    def test_synthetic_capture_cannot_prepare_a_live_deployment_by_default(self):
        with self.assertRaisesRegex(ValueError, "native capture"):
            build_raw_archive_extension(baseline(), capture(), now=NOW)

    def test_freshness_uses_source_acquisition_not_response_observation_or_archive_time(self):
        c = capture(); c["source_started_at_utc"] = "2026-10-10T00:00:00Z"; c["source_completed_at_utc"] = "2026-10-10T01:00:00Z"
        c["pages"][0]["rows"][0]["RawAcquiredUTC"] = "2026-10-10T00:30:00Z"
        # Old evidence may be retained, but cannot pass the accepted-generation gate.
        new, _ = self.build(receipt=c)
        self.assertIn("2026-10-10T01:00:00Z", new["properties"]["definition"]["actions"]["RawStage_Require_accepted_projection"]["inputs"])
        self.assertNotIn("RawAcquiredUTC", new["properties"]["definition"]["actions"]["RawStage_Require_accepted_projection"]["inputs"])

    def test_definition_and_artifact_hashes_are_repeatable(self):
        self.assertEqual(self.build(), self.build())
        _, e = self.build()
        for artifact in e["files"]:
            self.assertEqual(artifact["sha256"], hashlib.sha256(artifact["content"].encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
