"""Unit tests for Open Access classification and clinical trial registry linkages."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from open_access_trials import (
    classify_open_access_status,
    extract_trial_registrations,
    format_trial_registry_summary,
    enrich_record_open_access_trials,
)


class TestOpenAccessTrials(unittest.TestCase):
    def test_classify_gold_oa(self):
        cat, comp = classify_open_access_status("gold")
        self.assertEqual(cat, "Gold")
        self.assertEqual(comp, "Fully Compliant")

    def test_classify_hybrid_oa(self):
        cat, comp = classify_open_access_status("hybrid")
        self.assertEqual(cat, "Hybrid")
        self.assertEqual(comp, "Fully Compliant")

    def test_classify_green_oa(self):
        cat, comp = classify_open_access_status("green")
        self.assertEqual(cat, "Green")
        self.assertEqual(comp, "Fully Compliant")

    def test_classify_bronze_oa(self):
        cat, comp = classify_open_access_status("bronze")
        self.assertEqual(cat, "Bronze")
        self.assertEqual(comp, "Conditionally Compliant")

    def test_classify_closed(self):
        cat, comp = classify_open_access_status("closed")
        self.assertEqual(cat, "Closed")
        self.assertEqual(comp, "Non-Compliant")

    def test_classify_by_license(self):
        cat, comp = classify_open_access_status(None, license_str="CC-BY 4.0", is_oa=True)
        self.assertEqual(cat, "Gold")
        self.assertEqual(comp, "Fully Compliant")

    def test_extract_anzctr_trial(self):
        text = "This trial was registered with the Australian New Zealand Clinical Trials Registry (ACTRN12618000123456)."
        trials = extract_trial_registrations(text)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["registry"], "ANZCTR")
        self.assertEqual(trials[0]["trial_id"], "ACTRN12618000123456")
        self.assertEqual(
            trials[0]["trial_url"],
            "https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=ACTRN12618000123456"
        )

    def test_extract_nct_trial(self):
        text = "ClinicalTrials.gov identifier: NCT01234567"
        trials = extract_trial_registrations(text)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["registry"], "ClinicalTrials.gov")
        self.assertEqual(trials[0]["trial_id"], "NCT01234567")
        self.assertEqual(trials[0]["trial_url"], "https://clinicaltrials.gov/study/NCT01234567")

    def test_extract_multiple_trials(self):
        text = "Registered as ACTRN12620000654321 and NCT04567890 in clinical registries."
        trials = extract_trial_registrations(text)
        self.assertEqual(len(trials), 2)
        ids, urls = format_trial_registry_summary(trials)
        self.assertEqual(ids, "ACTRN12620000654321; NCT04567890")
        self.assertIn("https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=ACTRN12620000654321", urls)
        self.assertIn("https://clinicaltrials.gov/study/NCT04567890", urls)

    def test_enrich_record_open_access_trials(self):
        rec = {
            "Title": "A randomized trial of early ECMO in severe ARDS (ACTRN12619000987654)",
            "OpenAccessStatus": "gold",
            "License": "CC-BY",
        }
        enriched = enrich_record_open_access_trials(rec)
        self.assertEqual(enriched["OACategory"], "Gold")
        self.assertEqual(enriched["OAComplianceNHMRC"], "Fully Compliant")
        self.assertEqual(enriched["TrialRegistryID"], "ACTRN12619000987654")
        self.assertEqual(
            enriched["TrialRegistryURL"],
            "https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=ACTRN12619000987654"
        )


if __name__ == "__main__":
    unittest.main()
