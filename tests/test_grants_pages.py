import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GrantsPageSurfaceTests(unittest.TestCase):
    def test_local_report_contains_three_additive_grants_pages(self):
        pages = json.loads((ROOT / "powerbi/CHHHS Research Publications.Report/definition/pages/pages.json").read_text())
        self.assertEqual(pages["pageOrder"][-3:], ["FundingOpportunities", "FundingCalendar", "MyFundingWatchlist"])

    def test_grants_model_is_empty_safe_and_explicitly_pending_native_readback(self):
        model = json.loads((ROOT / "audit/model.snapshot.json").read_text())["model"]
        grants = next(table for table in model["tables"] if table["name"] == "GrantsRegistry")
        self.assertIn("empty", grants["description"])
        self.assertIn("OpportunityKey", {column["name"] for column in grants["columns"]})
        self.assertIn("COUNTROWS(GrantsRegistry)", " ".join(measure["expression"] for measure in grants["measures"]))

    def test_user_scoped_grant_support_tables_are_separate_from_opportunities(self):
        model = json.loads((ROOT / "audit/model.snapshot.json").read_text())["model"]
        tables = {table["name"]: table for table in model["tables"]}
        self.assertEqual(
            {"FundingCalendar", "MyFundingWatchlist", "FundingDeliveryLedger"}.intersection(tables),
            {"FundingCalendar", "MyFundingWatchlist", "FundingDeliveryLedger"},
        )
        self.assertIn("DeadlineKey", {column["name"] for column in tables["FundingCalendar"]["columns"]})
        self.assertIn("Active", {column["name"] for column in tables["MyFundingWatchlist"]["columns"]})
        self.assertIn("DeliveryEventKey", {column["name"] for column in tables["FundingDeliveryLedger"]["columns"]})

    def test_dora_activity_projection_preserves_source_identity_and_project_id_uncertainty(self):
        model = json.loads((ROOT / "audit/model.snapshot.json").read_text())["model"]
        dora = next(table for table in model["tables"] if table["name"] == "DoraActivityRegistry")
        fields = {column["name"] for column in dora["columns"]}
        self.assertIn("DORAActivityKey", fields)
        self.assertIn("Project ID", fields)
        self.assertIn("DORAResourceID", fields)
        self.assertIn("non-unique", dora["description"])

    def test_relationship_projection_preserves_separate_endpoint_keys(self):
        model = json.loads((ROOT / "audit/model.snapshot.json").read_text())["model"]
        rel = next(table for table in model["tables"] if table["name"] == "GrantRelationships")
        fields = {column["name"] for column in rel["columns"]}
        self.assertTrue({"RelationshipKey", "FromKey", "ToKey", "EvidenceURL"} <= fields)
        self.assertIn("no implicit join", rel["description"])

    def test_calendar_change_projection_preserves_revision_history(self):
        model = json.loads((ROOT / "audit/model.snapshot.json").read_text())["model"]
        changes = next(table for table in model["tables"] if table["name"] == "FundingCalendarChanges")
        fields = {column["name"] for column in changes["columns"]}
        self.assertTrue({"ChangeKey", "PreviousRevision", "Revision", "PreviousDate", "CalculatedDate", "Cancelled"} <= fields)
        self.assertIn("source-preserving", changes["description"])


if __name__ == "__main__":
    unittest.main()
