import json
import unittest
from pathlib import Path

from scripts.validate_watchlist_flow_contract import validate


class WatchlistFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "config/flows/funding-watchlist-upsert.definition.json"
        cls.definition = json.loads(path.read_text(encoding="utf-8"))
        cls.flow = cls.definition["properties"]["definition"]

    def test_contract_is_sharepoint_only_and_personal_watchlist(self):
        text = json.dumps(self.definition)
        self.assertIn("WatchlistRowsJson", text)
        self.assertIn("shared_sharepointonline", text)
        self.assertNotIn("shared_onedriveforbusiness", text)
        self.assertEqual([], validate(self.flow))

    def test_serial_loop_duplicate_guard_and_exact_update(self):
        loop = self.flow["actions"]["Apply_to_each_Watchlist_Row"]
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        nested = loop["actions"]
        self.assertIn("DUPLICATE_WATCHLIST_KEY", json.dumps(nested["Condition_Duplicate_OpportunityKey"]))
        self.assertEqual(nested["Condition_Is_New_Watchlist_Row"]["expression"]["equals"][1], 0)
        exactly_one = nested["Condition_Is_New_Watchlist_Row"]["else"]["actions"]["Condition_Exactly_One_Watchlist_Row"]
        self.assertEqual(exactly_one["expression"]["equals"][1], 1)


if __name__ == "__main__":
    unittest.main()
