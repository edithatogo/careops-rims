import unittest
import copy
import json
import tempfile
import uuid
import zipfile
from pathlib import Path

from scripts.validate_publication_platform_contract import (
    MANIFEST,
    PACKAGE,
    _definition,
    _tracked_definition,
    validate,
    validate_manifest,
)
from scripts.build_sharepoint_upsert_package import build_package, load_target


class PublicationPlatformContractTests(unittest.TestCase):
    def require_private_package(self):
        if not PACKAGE.exists():
            self.skipTest("private live package is not present in source archive")

    def test_package_contract_is_valid_when_present(self):
        self.require_private_package()
        self.assertEqual(validate(_definition()), [])

    def test_tracked_definition_matches_flow_contract(self):
        self.assertEqual(validate(_tracked_definition()), [])

    def test_daily_recurrence_trigger_is_required(self):
        definition = copy.deepcopy(_tracked_definition())
        definition["triggers"]["Recurrence"]["recurrence"]["schedule"]["hours"] = ["21"]
        self.assertIn("recurrence must run daily at 20:00 UTC", validate(definition))

    def test_manifest_has_one_canonical_flow_resource(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(validate_manifest(manifest), [])
        manifest["details"]["displayName"] = "legacy flow"
        self.assertIn("manifest root must use the canonical flow display name", validate_manifest(manifest))

    def test_record_loop_is_required(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"].pop("Apply_to_each_Publication")
        self.assertIn("registry writes must be inside an explicit record loop", validate(definition))

    def test_parallel_writes_are_rejected(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"]["Apply_to_each_Publication"]["runtimeConfiguration"]["concurrency"]["repetitions"] = 20
        self.assertIn("record loop must use single-write concurrency", validate(definition))

    def test_duplicate_source_keys_fail_closed(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"]["Apply_to_each_Publication"]["actions"].pop("Condition_Duplicate_SourceKey")
        self.assertIn("duplicate SourceKey results must fail closed", validate(definition))

    def test_create_and_update_writes_use_sharepoint_and_same_target(self):
        definition = copy.deepcopy(_tracked_definition())
        condition = definition["actions"]["Apply_to_each_Publication"]["actions"]["Condition_Is_New_Publication"]
        condition["actions"]["SharePoint_Create_item"]["inputs"]["host"]["apiId"] = (
            "/providers/Microsoft.PowerApps/apis/shared_onedriveforbusiness"
        )
        self.assertIn("SharePoint_Create_item must use the SharePoint Online connector", validate(definition))

        definition = copy.deepcopy(_tracked_definition())
        condition = definition["actions"]["Apply_to_each_Publication"]["actions"]["Condition_Is_New_Publication"]
        condition["else"]["actions"]["Condition_Exactly_One_Publication"]["actions"]["SharePoint_Update_item"]["inputs"]["parameters"]["table"] = "different-list"
        self.assertIn("SharePoint_Update_item must target the same SharePoint site and list as lookup", validate(definition))

    def test_sharepoint_operations_and_authentication_are_explicit(self):
        definition = copy.deepcopy(_tracked_definition())
        nested = definition["actions"]["Apply_to_each_Publication"]["actions"]
        nested["SharePoint_Get_items"]["inputs"]["host"]["operationId"] = "PostItem"
        self.assertIn("registry lookup must use the SharePoint GetItems operation", validate(definition))

        definition = copy.deepcopy(_tracked_definition())
        create = definition["actions"]["Apply_to_each_Publication"]["actions"]["Condition_Is_New_Publication"]["actions"]["SharePoint_Create_item"]
        create["inputs"].pop("authentication")
        self.assertIn("SharePoint_Create_item must declare connector authentication", validate(definition))

    def test_nested_terminate_is_not_used_for_duplicate_failure(self):
        self.assertNotIn("Terminate_Duplicate_SourceKey", str(_tracked_definition()))

    def test_duplicate_lookup_cannot_reach_update(self):
        condition = _tracked_definition()["actions"]["Apply_to_each_Publication"]["actions"]["Condition_Is_New_Publication"]
        guard = condition["else"]["actions"]["Condition_Exactly_One_Publication"]
        self.assertEqual(guard["expression"]["equals"][1], 1)
        self.assertIn("SharePoint_Update_item", guard["actions"])

    def test_record_actions_cannot_be_top_level(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"]["SharePoint_Get_items"] = copy.deepcopy(
            definition["actions"]["Apply_to_each_Publication"]["actions"]["SharePoint_Get_items"]
        )
        self.assertIn("record-scoped SharePoint actions must not be top-level", validate(definition))

    def test_placeholder_target_is_not_accepted_as_native_target(self):
        with self.assertRaises(ValueError):
            load_target(Path("config/sharepoint-publication-target.template.json"))

    def test_native_target_requires_model_id(self):
        self.require_private_package()
        self.assertEqual(len(load_target(Path("private/config/sharepoint-publication-target.json"))), 4)

    def test_native_target_requires_https_site_url(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.json"
            payload = {
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "unique_fields": ["source_key"],
                "fields": {name: "field_1" for name in {
                    "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                    "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                    "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                    "first_observed", "last_observed",
                }},
            }
            target.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_target(target)

    def test_native_target_requires_nonempty_field_mappings(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.json"
            fields = {name: "field_1" for name in {
                "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                "first_observed", "last_observed",
            }}
            fields["source_key"] = ""
            target.write_text(json.dumps({
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "unique_fields": ["source_key"],
                "fields": fields,
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_target(target)

    def test_native_target_rejects_non_string_identifiers_and_mappings(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.json"
            fields = {name: "field_1" for name in {
                "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                "first_observed", "last_observed",
            }}
            base = {
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "unique_fields": ["source_key"],
                "fields": fields,
            }
            for key in ("site_url", "list_id", "model_id"):
                invalid = {**base, key: 7}
                target.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "identifiers must be strings"):
                    load_target(target)
            invalid_fields = {**base, "fields": {**fields, "source_key": 7}}
            target.write_text(json.dumps(invalid_fields), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "field mappings must be strings"):
                load_target(target)

    def test_native_target_rejects_surrounding_whitespace_in_identifiers_and_mappings(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.json"
            fields = {name: "field_1" for name in {
                "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                "first_observed", "last_observed",
            }}
            base = {
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "unique_fields": ["source_key"],
                "fields": fields,
            }
            for key in ("site_url", "list_id", "model_id"):
                invalid = {**base, key: f" {base[key]}"}
                target.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                    load_target(target)
            invalid_fields = {**base, "fields": {**fields, "source_key": "field_1 "}}
            target.write_text(json.dumps(invalid_fields), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "field mappings must not"):
                load_target(target)

    def test_native_target_requires_unique_source_key_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.json"
            target.write_text(json.dumps({
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "fields": {name: "field_1" for name in {
                    "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                    "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                    "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                    "first_observed", "last_observed",
                }},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique SourceKey"):
                load_target(target)

    def test_package_lookup_uses_configured_source_key_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline = root / "baseline.zip"
            target = root / "target.json"
            flow_path = "Microsoft.Flow/flows/flow/definition.json"
            definition = {
                "properties": {
                    "definition": {
                        "actions": {
                            "Run_a_query_against_a_dataset": {"inputs": {"parameters": {}}}
                        },
                        "triggers": {},
                    },
                    "connectionReferences": {},
                }
            }
            manifest = {
                "details": {"displayName": "baseline"},
                "resources": {"flow": {
                    "type": "Microsoft.Flow/flows",
                    "dependsOn": [],
                    "details": {"displayName": "baseline"},
                }},
            }
            fields = {name: "field_1" for name in {
                "title", "source_key", "canonical_key", "authors", "journal", "publication_year",
                "publication_month", "publication_date_raw", "publication_date_precision", "source_set",
                "pmid", "doi", "matched_facilities", "attribution_evidence", "review_status",
                "first_observed", "last_observed",
            }}
            fields["source_key"] = "SourceKeyInternal"
            target.write_text(json.dumps({
                "site_url": "https://example.sharepoint.com/sites/dev",
                "list_id": str(uuid.uuid4()),
                "model_id": str(uuid.uuid4()),
                "unique_fields": ["source_key"],
                "fields": fields,
            }), encoding="utf-8")
            with zipfile.ZipFile(baseline, "w") as archive:
                archive.writestr(flow_path, json.dumps(definition))
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("Microsoft.Flow/flows/flow/apisMap.json", "{}")
                archive.writestr("Microsoft.Flow/flows/flow/connectionsMap.json", "{}")

            private_root = Path(__file__).resolve().parent.parent / "private"
            with tempfile.TemporaryDirectory(dir=private_root) as native_folder:
                output = Path(native_folder) / "output.zip"
                build_package(baseline, output, target)
                with zipfile.ZipFile(output) as archive:
                    built = json.loads(archive.read(flow_path))
            lookup = built["properties"]["definition"]["actions"][
                "Apply_to_each_Publication"
            ]["actions"]["SharePoint_Get_items"]
            self.assertEqual(
                lookup["inputs"]["parameters"]["$filter"],
                "SourceKeyInternal eq '@{replace(string(item()?['SourceKey']),'''','''''')}'",
            )

    def test_unknown_run_after_dependency_is_rejected(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"]["Apply_to_each_Publication"]["actions"]["SharePoint_Get_items"]["runAfter"] = {"Missing": ["Succeeded"]}
        self.assertTrue(any("unknown runAfter" in error for error in validate(definition)))

    def test_publication_loop_consumes_rows_query_not_readiness_summary(self):
        self.require_private_package()
        definition = copy.deepcopy(_definition())
        definition["actions"]["Apply_to_each_Publication"]["foreach"] = (
            "@coalesce(body('Run_a_query_against_a_dataset')?['results'][0]?['tables'][0]?['rows'], createArray())"
        )
        self.assertIn("record loop must depend on the publication rows query", validate(definition))

    def test_publication_rows_query_is_a_bounded_projection(self):
        definition = _tracked_definition()
        query = definition["actions"]["Run_publication_rows_query"]["inputs"]["parameters"]["specification/query"]
        self.assertIn("TOPN(100", query)
        self.assertIn('"SourceKey"', query)
        self.assertNotIn("RETURN FILTER(Rows, Ready)", query)


if __name__ == "__main__":
    unittest.main()
