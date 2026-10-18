import json
import unittest
from pathlib import Path

from scripts.validate_delivery_ledger_flow_contract import validate

class DeliveryLedgerFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "config/flows/funding-delivery-ledger-upsert.definition.json"
        cls.flow = json.loads(path.read_text(encoding="utf-8"))["properties"]["definition"]

    def test_contract_is_sharepoint_only_and_schema_complete(self):
        text = json.dumps(self.flow)
        self.assertIn("DeliveryRowsJson", text)
        self.assertIn("shared_sharepointonline", text)
        self.assertNotIn("shared_onedriveforbusiness", text)
        self.assertEqual([], validate(self.flow))

    def test_serial_loop_and_exact_match_guards(self):
        loop = self.flow["actions"]["Apply_to_each_Delivery_Row"]
        self.assertEqual(loop["runtimeConfiguration"]["concurrency"]["repetitions"], 1)
        nested = loop["actions"]
        self.assertIn("DUPLICATE_DELIVERY_EVENT_KEY", json.dumps(nested["Condition_Duplicate_DeliveryEventKey"]))
        self.assertEqual(nested["Condition_Is_New_Delivery_Row"]["expression"]["equals"][1], 0)
        exactly_one = nested["Condition_Is_New_Delivery_Row"]["else"]["actions"]["Condition_Exactly_One_Delivery_Row"]
        self.assertEqual(exactly_one["expression"]["equals"][1], 1)

if __name__ == "__main__": unittest.main()
