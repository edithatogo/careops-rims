import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_dora_activity_flow_contract as contract
from scripts.validate_dora_activity_flow_contract import validate


class DoraActivityFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "config/flows/dora-activity-registry-upsert.definition.json"
        cls.definition = json.loads(path.read_text(encoding="utf-8"))

    def test_tracked_flow_is_sharepoint_only_and_valid(self):
        self.assertEqual(validate(self.definition["properties"]["definition"]), [])
        text = json.dumps(self.definition)
        self.assertNotIn("shared_onedriveforbusiness", text)
        self.assertNotIn("OneDrive", text)

    def test_serial_loop_and_exact_match_guards_are_required(self):
        definition = self.definition["properties"]["definition"]
        loop = definition["actions"]["Apply_to_each_DORA_Activity"]
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        nested = loop["actions"]
        self.assertEqual(nested["Condition_Is_New_DORA_Activity"]["expression"]["equals"][1], 0)
        self.assertEqual(nested["Condition_Is_New_DORA_Activity"]["else"]["actions"]["Condition_Exactly_One_DORA_Activity"]["expression"]["equals"][1], 1)

    def test_missing_source_mapping_is_rejected(self):
        definition = copy.deepcopy(self.definition["properties"]["definition"])
        create = definition["actions"]["Apply_to_each_DORA_Activity"]["actions"]["Condition_Is_New_DORA_Activity"]["actions"]["SharePoint_Create_item"]
        del create["inputs"]["parameters"]["item/PI_x0020_Email"]
        self.assertTrue(any("PI Email" in error for error in validate(definition)))

    def test_onedrive_or_duplicate_guard_drift_is_rejected(self):
        definition = copy.deepcopy(self.definition["properties"]["definition"])
        lookup = definition["actions"]["Apply_to_each_DORA_Activity"]["actions"]["SharePoint_Get_items"]
        lookup["inputs"]["host"]["apiId"] = "/providers/Microsoft.PowerApps/apis/shared_onedriveforbusiness"
        self.assertTrue(any("SharePoint Online" in error for error in validate(definition)))

    def test_non_unique_registry_schema_is_rejected(self):
        schema_path = Path(__file__).parents[1] / "config/dora-activity-registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        identity = next(field for field in schema["fields"] if field["name"] == "DORAActivityKey")
        identity["unique"] = False
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder) / schema_path.name
            replacement.write_text(json.dumps(schema), encoding="utf-8")
            original_path = contract.SCHEMA_PATH
            contract.SCHEMA_PATH = replacement
            try:
                self.assertTrue(any("must declare DORAActivityKey unique" in error for error in validate(self.definition["properties"]["definition"])))
            finally:
                contract.SCHEMA_PATH = original_path

    def test_schema_field_addition_requires_flow_mapping(self):
        schema_path = Path(__file__).parents[1] / "config/dora-activity-registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["fields"].append({"name": "Future source field", "type": "text"})
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder) / schema_path.name
            replacement.write_text(json.dumps(schema), encoding="utf-8")
            original_path = contract.SCHEMA_PATH
            contract.SCHEMA_PATH = replacement
            try:
                self.assertTrue(any("must match the canonical registry schema fields" in error for error in validate(self.definition["properties"]["definition"])))
            finally:
                contract.SCHEMA_PATH = original_path


if __name__ == "__main__":
    unittest.main()
