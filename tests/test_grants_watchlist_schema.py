import json
import unittest
from pathlib import Path


class FundingWatchlistSchemaTests(unittest.TestCase):
    def test_schema_is_personal_and_has_single_unique_identity(self):
        root = Path(__file__).parents[1]
        schema = json.loads((root / "config/funding-watchlist.schema.json").read_text())
        fields = schema["fields"]
        names = [field["display_name"] for field in fields]
        self.assertEqual(schema["list_name"], "My Funding Watchlist")
        self.assertEqual(schema["scope"], "current_user_personal_list")
        self.assertEqual(schema["identity_field"], "OpportunityKey")
        self.assertEqual(names, ["OpportunityKey", "Scope", "TargetKey", "Active"])
        identity = fields[0]
        self.assertTrue(identity["required"] and identity["indexed"] and identity["unique"])

    def test_active_defaults_to_false_and_scope_is_not_free_text(self):
        schema = json.loads((Path(__file__).parents[1] / "config/funding-watchlist.schema.json").read_text())
        fields = {field["display_name"]: field for field in schema["fields"]}
        self.assertEqual(fields["Scope"]["type"], "choice")
        self.assertEqual(fields["Scope"]["choices"], ["opportunity", "category", "funder"])
        self.assertIs(fields["Active"]["default"], False)


if __name__ == "__main__":
    unittest.main()
