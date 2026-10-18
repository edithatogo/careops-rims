import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_grants_flow_contract as contract
from scripts.validate_grants_flow_contract import validate


class GrantsFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "config/flows/grants-registry-reviewed-import.definition.json"
        cls.definition = json.loads(path.read_text(encoding="utf-8"))
        cls.actions = cls.definition["properties"]["definition"]["actions"]

    def test_manual_reviewed_import_contract_is_sharepoint_only(self):
        text = json.dumps(self.definition)
        self.assertIn("ReviewedRowsJson", text)
        self.assertIn("shared_sharepointonline", text)
        self.assertNotIn("shared_onedriveforbusiness", text)
        self.assertNotIn("OneDrive", text)

    def test_serial_loop_and_key_guard_are_required(self):
        loop = self.actions["Apply_to_each_Reviewed_Row"]
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        nested = loop["actions"]
        self.assertIn("SharePoint_Get_items", nested)
        self.assertIn("Condition_Duplicate_OpportunityKey", nested)
        self.assertIn("Condition_Is_New_Opportunity", nested)
        duplicate = nested["Condition_Duplicate_OpportunityKey"]
        failure_actions = duplicate["actions"]
        self.assertEqual(list(failure_actions), ["Compose_Duplicate_OpportunityKey_Failure"])
        diagnostic = failure_actions["Compose_Duplicate_OpportunityKey_Failure"]
        self.assertEqual(diagnostic["type"], "Compose")
        self.assertIn("DUPLICATE_OPPORTUNITY_KEY", diagnostic["inputs"])
        self.assertEqual(duplicate["else"]["actions"], {})
        is_new = nested["Condition_Is_New_Opportunity"]
        self.assertEqual(is_new["expression"]["equals"][1], 0)
        exactly_one = is_new["else"]["actions"]["Condition_Exactly_One_Opportunity"]
        self.assertEqual(exactly_one["expression"]["equals"][1], 1)

    def test_update_does_not_overwrite_manual_review_fields(self):
        update = self.actions["Apply_to_each_Reviewed_Row"]["actions"]["Condition_Is_New_Opportunity"]["else"]["actions"]["Condition_Exactly_One_Opportunity"]["actions"]["SharePoint_Update_item"]
        params = update["inputs"]["parameters"]
        self.assertNotIn("item/ReviewStatus", params)
        self.assertNotIn("item/ReviewNotes", params)

    def test_create_and_update_persist_source_row_evidence(self):
        nested = self.actions["Apply_to_each_Reviewed_Row"]["actions"]
        create = nested["Condition_Is_New_Opportunity"]["actions"]["SharePoint_Create_item"]
        update = nested["Condition_Is_New_Opportunity"]["else"]["actions"]["Condition_Exactly_One_Opportunity"]["actions"]["SharePoint_Update_item"]
        self.assertIn("item/SourceRowURL", create["inputs"]["parameters"])
        self.assertIn("item/SourceRowURL", update["inputs"]["parameters"])

    def test_sharepoint_operation_ids_and_authentication_are_explicit(self):
        nested = self.actions["Apply_to_each_Reviewed_Row"]["actions"]
        self.assertEqual(nested["SharePoint_Get_items"]["inputs"]["host"]["operationId"], "GetItems")
        guarded = nested["Condition_Is_New_Opportunity"]
        create = guarded["actions"]["SharePoint_Create_item"]
        update = guarded["else"]["actions"]["Condition_Exactly_One_Opportunity"]["actions"]["SharePoint_Update_item"]
        self.assertEqual(create["inputs"]["host"]["operationId"], "PostItem")
        self.assertEqual(update["inputs"]["host"]["operationId"], "PatchItem")
        self.assertTrue(create["inputs"].get("authentication"))
        self.assertTrue(update["inputs"].get("authentication"))

    def test_placeholders_are_explicit(self):
        text = json.dumps(self.definition)
        self.assertIn("{{SHAREPOINT_SITE_URL}}", text)
        self.assertIn("{{SHAREPOINT_LIST_ID}}", text)

    def test_shared_validator_accepts_tracked_definition(self):
        self.assertEqual([], validate(self.definition["properties"]["definition"]))

    def test_shared_validator_rejects_onedrive_registry_persistence(self):
        definition = json.loads(json.dumps(self.definition))
        definition["properties"]["definition"]["actions"]["Apply_to_each_Reviewed_Row"]["actions"]["SharePoint_Get_items"]["inputs"]["host"]["apiId"] = "/providers/Microsoft.PowerApps/apis/shared_onedriveforbusiness"
        self.assertIn("grants lookup must use the SharePoint Online connector", validate(definition["properties"]["definition"]))

    def test_non_unique_registry_schema_is_rejected(self):
        schema_path = Path(__file__).parents[1] / "config/grants-registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        identity = next(field for field in schema["fields"] if field["display_name"] == "OpportunityKey")
        identity["unique"] = False
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder) / schema_path.name
            replacement.write_text(json.dumps(schema), encoding="utf-8")
            original_path = contract.SCHEMA_PATH
            contract.SCHEMA_PATH = replacement
            try:
                self.assertIn("grants registry schema must declare OpportunityKey unique", validate(self.definition["properties"]["definition"]))
            finally:
                contract.SCHEMA_PATH = original_path

    def test_schema_field_addition_requires_create_mapping(self):
        schema_path = Path(__file__).parents[1] / "config/grants-registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["fields"].append({"display_name": "Future field", "type": "text"})
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder) / schema_path.name
            replacement.write_text(json.dumps(schema), encoding="utf-8")
            original_path = contract.SCHEMA_PATH
            contract.SCHEMA_PATH = replacement
            try:
                self.assertIn("grants create mappings must match the canonical registry schema fields", validate(self.definition["properties"]["definition"]))
            finally:
                contract.SCHEMA_PATH = original_path


if __name__ == "__main__":
    unittest.main()
