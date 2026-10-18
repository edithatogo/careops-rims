import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeliveryLedgerContractTests(unittest.TestCase):
    def test_identity_and_required_fields(self):
        schema = json.loads((ROOT / "config/funding-delivery-ledger.schema.json").read_text())
        fields = {field["display_name"]: field for field in schema["fields"]}
        self.assertEqual(schema["identity_field"], "DeliveryEventKey")
        self.assertTrue(fields["DeliveryEventKey"]["required"])
        self.assertTrue(fields["DeliveryEventKey"]["unique"])
        for name in ("UserKey", "OpportunityKey", "EventType", "Revision", "Channel", "Status"):
            self.assertTrue(fields[name]["required"])

    def test_delivery_defaults_and_types(self):
        schema = json.loads((ROOT / "config/funding-delivery-ledger.schema.json").read_text())
        fields = {field["display_name"]: field for field in schema["fields"]}
        self.assertEqual(fields["OffsetDays"]["type"], "integer")
        self.assertEqual(fields["Status"]["default"], "Pending")
        self.assertEqual(fields["ErrorMessage"]["type"], "note")
