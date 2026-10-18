"""Offline native-archive consumer: preservation and incomplete/drift boundaries."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import grants_qld_qgip_api as qgip
from scripts.read_qgip_committed_source import read_commit


def write_commit(root, *, empty=False, count=2):
    rows = [] if empty else [
        {"Service ID": "synthetic-open", "Program title": "Synthetic programme",
         "Status": "Open", "Assistance type1": "Grant", "Website": "https://example.invalid/grant"},
        {"Service ID": "synthetic-closed", "Program title": "Retained closed programme",
         "Status": "Closed", "Future field": {"all": [False, 0, None, "café"]}},
    ]
    if not empty:
        rows.extend({"Service ID": f"synthetic-{i}", "Status": "Closed"}
                    for i in range(2, count))
    metadata = {
        "Index": ("datastore_search", {"resource_id": qgip.INDEX_RESOURCE_ID, "limit": 100, "offset": 0},
                  {"total": 1, "total_was_estimated": False, "records": [{"Agency": "QH", "Resource": qgip.RESOURCE_ID}]}),
        "Package": ("package_show", {"id": qgip.PACKAGE_NAME},
                    {"id": qgip.PACKAGE_ID, "name": qgip.PACKAGE_NAME, "license_id": "CC-BY-3.0",
                     "resources": [{"id": qgip.RESOURCE_ID}]}),
        "Resource": ("resource_show", {"id": qgip.RESOURCE_ID},
                     {"id": qgip.RESOURCE_ID, "package_id": qgip.PACKAGE_ID,
                      "last_modified": "2026-09-01T00:00:00Z", "hash": "synthetic"}),
        "Schema": ("datastore_info", {"id": qgip.RESOURCE_ID},
                   {"fields": [{"id": k, "type": "text"} for k in qgip.CLASSIFICATION_SCHEMA_FIELDS]}),
    }
    files = []

    def save(name, action, queries, result):
        body = {"request": {"method": "GET", "uri": qgip.API_BASE + action, "queries": queries},
                "captured_utc": "2026-10-16T00:00:00Z",
                "response": {"statusCode": 200, "headers": {"Content-Type": "application/json"},
                             "body": {"success": True, "result": result, "future_envelope": [None, False]}},
                "fidelity": "complete_native_HTTP_JSON_values; original_transport_bytes_not_certified"}
        (root / name).write_text(json.dumps(body, ensure_ascii=False))
        files.append({"name": name, "verification": "exact_base64_stored_content_readback"})

    for phase in ("before", "after"):
        for kind, (action, queries, result) in metadata.items():
            save(f"{kind}_{phase}.json", action, queries, result)
    for read in (1, 2):
        for offset in range(0, max(1, len(rows)), qgip.PAGE_SIZE):
            save(f"pass-{read}-offset-{offset}.json", "datastore_search",
                 {"resource_id": qgip.RESOURCE_ID, "limit": 100, "offset": offset},
                 {"total": len(rows), "offset": offset, "total_was_estimated": False,
                  "records": rows[offset:offset + qgip.PAGE_SIZE]})
    manifest = {"format": "rims-qgip-source-commit-v1", "source_id": qgip.SOURCE_ID,
                "resource_id": qgip.RESOURCE_ID, "package_id": qgip.PACKAGE_ID,
                "complete_reads": 2, "candidate_filter_applied": False, "canonical_admission": False,
                "schedule": "manual_only", "run": "synthetic-native-run", "source_total": len(rows),
                "committed_utc": "2026-10-16T00:01:00Z", "files": files}
    (root / "manifest.json").write_text(json.dumps(manifest))


def change(root, name, edit):
    p = root / name
    data = json.loads(p.read_text())
    edit(data)
    p.write_text(json.dumps(data))


class CommittedSourceTests(unittest.TestCase):
    def test_complete_multi_page_source_is_replayed_from_retained_files(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            write_commit(root, count=101)
            change(root, "manifest.json", lambda d: d["files"].reverse())
            result = read_commit(root)
            self.assertEqual(result["source_total"], 101)
            self.assertEqual(len(result["raw_source"]["pages"]), 2)
            self.assertEqual(len(result["raw_source"]["native_envelopes"]), 12)

    def test_reuses_candidate_policy_preserves_closed_unknown_and_envelope_values(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            write_commit(root)
            result = read_commit(root)
            self.assertEqual(result["source_total"], 2)
            self.assertEqual([x["SourceID"] for x in result["records"]], ["synthetic-open"])
            self.assertEqual(result["records"][0]["Status"], "Needs Review")
            self.assertFalse(result["accepted"])
            self.assertEqual(result["raw_source"]["pages"][0]["records"][1]["Future field"],
                             {"all": [False, 0, None, "café"]})
            self.assertEqual(result["raw_source"]["native_envelopes"]["Index_before.json"]["response"]["body"]["future_envelope"], [None, False])
            self.assertFalse(result["native_commit"]["original_transport_bytes_certified"])
            self.assertEqual(len(result["native_commit"]["stored_file_sha256"]), 10)

    def test_empty_source_requires_both_retained_pages(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            write_commit(root, empty=True)
            self.assertEqual(read_commit(root)["source_total"], 0)
            (root / "pass-2-offset-0.json").unlink()
            with self.assertRaises(ValueError):
                read_commit(root)

    def test_stable_additive_schema_and_unknown_values_remain_replayable(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            write_commit(root)
            for phase in ('before', 'after'):
                change(root, f'Schema_{phase}.json', lambda d: d['response']['body']['result']['fields'].append(
                    {'id': 'Future field', 'type': 'json'}))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = read_commit(root)
            self.assertEqual(result['source_total'], 2)
            self.assertEqual(len(result['records']), 1)
            self.assertIn({'id': 'Future field', 'type': 'json'},
                          result['raw_source']['native_envelopes']['Schema_before.json']['response']['body']['result']['fields'])
            self.assertEqual(result['raw_source']['pages'][0]['records'][1]['Future field'],
                             {'all': [False, 0, None, 'café']})
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_breaking_required_type_or_future_format_cannot_replace_last_good(self):
        for boundary in ('required_type', 'future_format'):
            with self.subTest(boundary=boundary), TemporaryDirectory() as t:
                root = Path(t) / 'source-commit'
                root.mkdir()
                write_commit(root)
                last_good = read_commit(root)
                accepted = Path(t) / 'last-good-output.json'
                accepted.write_text(json.dumps(last_good))
                accepted_bytes = accepted.read_bytes()
                if boundary == 'required_type':
                    for phase in ('before', 'after'):
                        change(root, f'Schema_{phase}.json', lambda d: d['response']['body']['result']['fields'][1].update({'type': 'integer'}))
                else:
                    change(root, 'manifest.json', lambda d: d.update({'format': 'rims-qgip-source-commit-v2'}))
                changed_source = {p.name: p.read_bytes() for p in root.iterdir()}
                with self.assertRaises(ValueError):
                    read_commit(root)
                self.assertEqual(last_good['records'][0]['SourceID'], 'synthetic-open')
                self.assertEqual(accepted.read_bytes(), accepted_bytes)
                self.assertEqual(changed_source, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_source_content_schema_or_resource_drift_rejects_commit(self):
        edits = [
            ("pass-2-offset-0.json", lambda d: d["response"]["body"]["result"]["records"][1].update({"Future field": "changed"})),
            ("Schema_after.json", lambda d: d["response"]["body"]["result"]["fields"][0].update({"type": "integer"})),
            ("Resource_after.json", lambda d: d["response"]["body"]["result"].update({"hash": "changed"})),
            ("Package_after.json", lambda d: d["response"]["body"]["result"]["resources"][0].update({"url": "https://example.invalid/changed"})),
        ]
        for name, edit in edits:
            with self.subTest(file=name), TemporaryDirectory() as t:
                root = Path(t)
                write_commit(root)
                change(root, name, edit)
                with self.assertRaises(ValueError):
                    read_commit(root)

    def test_manifest_scope_coverage_and_file_purpose_fail_closed(self):
        edits = [
            ("manifest.json", lambda d: d.update({"canonical_admission": True})),
            ("manifest.json", lambda d: d.update({"source_total": True})),
            ("manifest.json", lambda d: d["files"].append(copy.deepcopy(d["files"][0]))),
            ("pass-1-offset-0.json", lambda d: d["request"]["queries"].update({"offset": 100})),
            ("Index_before.json", lambda d: d["response"].update({"statusCode": 500})),
            ("Index_before.json", lambda d: d.update({"captured_utc": "2027-01-01T00:00:00Z"})),
        ]
        for name, edit in edits:
            with self.subTest(file=name), TemporaryDirectory() as t:
                root = Path(t)
                write_commit(root)
                change(root, name, edit)
                with self.assertRaises(ValueError):
                    read_commit(root)

    def test_no_network_fallback_and_disabled_catalogue_blocks_projection(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            write_commit(root)
            catalogue = json.loads(Path(qgip.DEFAULT_CATALOGUE).read_text())
            # Put policy outside the downloaded commit; it is not source evidence.
            with TemporaryDirectory() as p:
                path = Path(p) / "catalogue.json"
                for source in catalogue:
                    if source["source_id"] == qgip.SOURCE_ID:
                        source["enabled"] = False
                path.write_text(json.dumps(catalogue))
                with self.assertRaises(ValueError):
                    read_commit(root, catalogue_path=path)


if __name__ == "__main__":
    unittest.main()
