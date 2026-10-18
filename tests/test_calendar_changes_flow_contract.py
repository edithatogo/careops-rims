import json
import unittest

from scripts.validate_calendar_changes_flow_contract import DEFINITION, validate


class CalendarChangesFlowContractTests(unittest.TestCase):
    def test_sharepoint_only_serial_exact_match_contract(self):
        definition = json.loads(DEFINITION.read_text())["properties"]["definition"]
        self.assertEqual(validate(definition), [])


if __name__ == "__main__":
    unittest.main()
