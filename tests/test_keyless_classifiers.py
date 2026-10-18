"""Unit tests for deterministic keyless classifiers."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from keyless_classifiers import (
    classify_funding_type,
    is_internal_funding,
    classify_indigenous_health_focus,
    classify_study_design,
    extract_clinical_trial_ids,
)


class TestKeylessClassifiers(unittest.TestCase):
    def test_classify_funding_type(self):
        self.assertEqual(classify_funding_type(None), "Unfunded / Departmental")
        self.assertEqual(classify_funding_type(""), "Unfunded / Departmental")
        self.assertEqual(classify_funding_type("National Health and Medical Research Council"), "Commonwealth (NHMRC/MRFF)")
        self.assertEqual(classify_funding_type("Medical Research Future Fund"), "Commonwealth (NHMRC/MRFF)")
        self.assertEqual(classify_funding_type("Queensland Health Junior Doctor Research Fellowship"), "State / Qld Health")
        self.assertEqual(classify_funding_type("Emergency Medicine Foundation; Cairns Hospital Foundation"), "Philanthropic / Foundation")
        self.assertEqual(classify_funding_type("Merck Sharp & Dohme; Pfizer"), "Commercial / Industry Trial")
        self.assertEqual(classify_funding_type("James Cook University"), "University Partner")
        self.assertEqual(classify_funding_type("Random German Charity"), "Other External Funder")

    def test_is_internal_funding(self):
        self.assertTrue(is_internal_funding("Cairns Hospital Foundation Research Grant"))
        self.assertTrue(is_internal_funding(None, "Funded via CHHHS SERTA grant"))
        self.assertFalse(is_internal_funding("NHMRC Project Grant", "Affiliated with Cairns Hospital"))

    def test_indigenous_health_focus(self):
        self.assertTrue(classify_indigenous_health_focus(mesh="Oceanic Ancestry Group; Diabetes"))
        self.assertTrue(classify_indigenous_health_focus(keywords="Torres Strait health"))
        self.assertTrue(classify_indigenous_health_focus(title="Rheumatic heart disease in Cape York communities"))
        self.assertFalse(classify_indigenous_health_focus(mesh="Cardiology", keywords="Hypertension", title="Blood pressure in adults"))

    def test_study_design(self):
        self.assertEqual(classify_study_design(mesh="Randomized Controlled Trial", title="A trial of drug X"), "Randomized Controlled Trial")
        self.assertEqual(classify_study_design(title="Systematic review of sepsis management"), "Systematic Review / Meta-Analysis")
        self.assertEqual(classify_study_design(title="Clinical practice guideline for stroke"), "Clinical Practice Guideline")
        self.assertEqual(classify_study_design(title="A retrospective cohort study of ICU admissions"), "Observational / Cohort Study")
        self.assertEqual(classify_study_design(title="An unusual case report of melioidosis"), "Case Report")
        self.assertEqual(classify_study_design(title="Laboratory investigation of bacterial membrane"), "Other Biomedical / Translational")

    def test_extract_clinical_trial_ids(self):
        self.assertEqual(extract_clinical_trial_ids("Registered under ACTRN12618000123456 in trial register"), "ACTRN12618000123456")
        self.assertEqual(extract_clinical_trial_ids("ClinicalTrials.gov identifier NCT01234567."), "NCT01234567")
        self.assertEqual(
            extract_clinical_trial_ids("Both ACTRN12618000123456 and NCT01234567 were recorded"),
            "ACTRN12618000123456; NCT01234567"
        )
        self.assertIsNone(extract_clinical_trial_ids("No trial numbers here"))


if __name__ == "__main__":
    unittest.main()
