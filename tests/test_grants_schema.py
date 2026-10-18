import json
import unittest
from pathlib import Path

from scripts.grants_registry import normalize_opportunity, sharepoint_field_map


class GrantsSchemaTests(unittest.TestCase):
    def test_schema_matches_sharepoint_mapping_and_has_single_identity(self):
        root = Path(__file__).parents[1]
        schema = json.loads((root / "config/grants-registry.schema.json").read_text())
        names = [field["display_name"] for field in schema["fields"]]
        mapped = set(sharepoint_field_map(normalize_opportunity({"Title": "T", "URL": "https://x"})))
        self.assertEqual(schema["list_name"], "Grants Registry")
        self.assertEqual(schema["identity_field"], "OpportunityKey")
        identity = next(field for field in schema["fields"] if field["display_name"] == "OpportunityKey")
        self.assertTrue(identity["required"] and identity["indexed"] and identity["unique"])
        self.assertEqual(set(names), mapped)
        self.assertEqual(names.count("OpportunityKey"), 1)

    def test_schema_preserves_partial_deadline_as_text_contract(self):
        schema = json.loads((Path(__file__).parents[1] / "config/grants-registry.schema.json").read_text())
        types = {field["display_name"]: field["type"] for field in schema["fields"]}
        self.assertEqual(types["Deadline"], "text")
        self.assertEqual(types["DeadlineRaw"], "text")


if __name__ == "__main__":
    unittest.main()
