import json
import unittest
from pathlib import Path

from scripts.validate_calendar_flow_contract import validate


class CalendarFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "config/flows/funding-calendar-upsert.definition.json"
        cls.definition = json.loads(path.read_text(encoding="utf-8"))
        cls.flow = cls.definition["properties"]["definition"]

    def test_contract_is_sharepoint_only_and_schema_complete(self):
        text = json.dumps(self.definition)
        self.assertIn("CalendarRowsJson", text)
        self.assertIn("shared_sharepointonline", text)
        self.assertNotIn("shared_onedriveforbusiness", text)
        self.assertEqual([], validate(self.flow))

    def test_serial_loop_and_exact_match_guards(self):
        loop = self.flow["actions"]["Apply_to_each_Calendar_Row"]
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        nested = loop["actions"]
        self.assertIn("DUPLICATE_DEADLINE_KEY", json.dumps(nested["Condition_Duplicate_DeadlineKey"]))
        self.assertEqual(nested["Condition_Is_New_Calendar_Row"]["expression"]["equals"][1], 0)
        exactly_one = nested["Condition_Is_New_Calendar_Row"]["else"]["actions"]["Condition_Exactly_One_Calendar_Row"]
        self.assertEqual(exactly_one["expression"]["equals"][1], 1)


if __name__ == "__main__":
    unittest.main()
