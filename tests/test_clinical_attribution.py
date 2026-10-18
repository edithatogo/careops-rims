"""Unit tests for clinical leadership attribution, ANZSRC FoR classification, and specialty mapping."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_attribution import (
    classify_authorship_leadership,
    classify_anzsrc_for,
    classify_clinical_specialty,
    enrich_record_clinical_attribution,
)


class TestClinicalAttribution(unittest.TestCase):
    def test_authorship_leadership_single_author_cairns(self):
        authors = "Mordaunt, RIMS maintainer"
        affiliations = "Department of Clinical Genomics, Cairns Hospital, Queensland, Australia"
        role = classify_authorship_leadership(authors, affiliations)
        self.assertEqual(role, "Cairns-Led")

    def test_authorship_leadership_first_author_cairns(self):
        authors = "Smith, John; Doe, Jane; Brown, Bob"
        affiliations = "1: Cairns Hospital, Cairns, QLD; 2: University of Sydney, NSW; 3: Monash University, VIC"
        role = classify_authorship_leadership(authors, affiliations)
        self.assertEqual(role, "Cairns-Led")

    def test_authorship_leadership_senior_author_cairns(self):
        authors = "Doe, Jane; Brown, Bob; Mordaunt, RIMS maintainer"
        affiliations = "1: University of Sydney, NSW; 2: Monash University, VIC; 3: Cairns Hospital, Cairns, QLD"
        role = classify_authorship_leadership(authors, affiliations)
        self.assertEqual(role, "Cairns-Led")

    def test_authorship_leadership_collaborative(self):
        authors = "Doe, Jane; Smith, John; Brown, Bob"
        # Middle author (Smith, John) is from Cairns
        author_affiliations = [
            {"author": "Doe, Jane", "affiliation": "University of Melbourne"},
            {"author": "Smith, John", "affiliation": "Cairns Hospital, QLD"},
            {"author": "Brown, Bob", "affiliation": "Harvard Medical School"},
        ]
        role = classify_authorship_leadership(authors, author_affiliations=author_affiliations)
        self.assertEqual(role, "Collaborative")

    def test_unordered_structured_affiliations_do_not_infer_leadership(self):
        role = classify_authorship_leadership(
            "Doe, Jane; Smith, John; Brown, Bob",
            author_affiliations=[
                {"author": "Doe, Jane", "affiliation": "Cairns Hospital"},
                {"author": "Smith, John", "affiliation": "University"},
                {"author": "Brown, Bob", "affiliation": "University"},
            ],
        )
        self.assertEqual(role, "Collaborative")

    def test_affiliation_sequence_alone_does_not_infer_first_author(self):
        role = classify_authorship_leadership(
            "Smith, John; Doe, Jane; Brown, Bob",
            "Cairns Hospital; University of Sydney; Monash University",
        )
        self.assertEqual(role, "Collaborative")

    def test_authorship_leadership_unattributed(self):
        authors = "Doe, Jane; Brown, Bob"
        affiliations = "University of Sydney; University of Melbourne"
        role = classify_authorship_leadership(authors, affiliations)
        self.assertEqual(role, "Unattributed")

    def test_anzsrc_for_biomedical_clinical(self):
        code, name = classify_anzsrc_for(
            title="Surgical outcomes in renal transplant recipients",
            mesh="Kidney Transplantation; Postoperative Complications",
            journal="Transplantation",
        )
        self.assertEqual(code, "32")
        self.assertEqual(name, "Biomedical and Clinical Sciences")

    def test_anzsrc_for_health_sciences(self):
        code, name = classify_anzsrc_for(
            title="Hospital discharge planning and nursing workload in regional health services",
            mesh="Nursing Staff, Hospital; Patient Discharge",
            journal="Journal of Nursing Management",
        )
        self.assertEqual(code, "42")
        self.assertEqual(name, "Health Sciences")

    def test_anzsrc_for_biological_sciences(self):
        code, name = classify_anzsrc_for(
            title="Phylogenetic analysis and genome sequencing of tropical fungal isolates",
            mesh="Phylogeny; Genome, Fungal",
            journal="Fungal Genetics and Biology",
        )
        self.assertEqual(code, "31")
        self.assertEqual(name, "Biological Sciences")

    def test_clinical_specialty_infectious_diseases(self):
        specialty = classify_clinical_specialty(
            title="Melioidosis cases in tropical North Queensland: a 20-year review",
            mesh="Melioidosis; Burkholderia pseudomallei",
            journal="Lancet Infectious Diseases",
        )
        self.assertEqual(specialty, "Infectious Diseases & Tropical Health")

    def test_clinical_specialty_emergency_critical_care(self):
        specialty = classify_clinical_specialty(
            title="High-flow nasal cannula in acute respiratory failure in the emergency department",
            mesh="Emergency Service, Hospital; Respiratory Insufficiency",
            journal="Annals of Emergency Medicine",
        )
        self.assertEqual(specialty, "Emergency & Critical Care")

    def test_clinical_specialty_cancer_care(self):
        specialty = classify_clinical_specialty(
            title="Immunotherapy response in advanced metastatic melanoma",
            mesh="Melanoma; Immunotherapy",
            journal="Journal of Clinical Oncology",
        )
        self.assertEqual(specialty, "Cancer Care")

    def test_clinical_specialty_cardiology(self):
        specialty = classify_clinical_specialty(
            title="Percutaneous coronary intervention versus coronary artery bypass grafting",
            mesh="Percutaneous Coronary Intervention; Coronary Artery Bypass",
            journal="Circulation",
        )
        self.assertEqual(specialty, "Medical Specialties")

    def test_enrich_record_clinical_attribution(self):
        rec = {
            "Authors": "Mordaunt, D; Smith, A",
            "Affiliations": "1: Cairns Hospital, QLD; 2: Townsville Hospital, QLD",
            "Title": "Genomic medicine in regional Queensland",
            "MeSHTerms": "Genomics; Regional Health",
            "Journal": "Internal Medicine Journal",
        }
        enriched = enrich_record_clinical_attribution(rec)
        self.assertEqual(enriched["LeadershipRole"], "Cairns-Led")
        self.assertEqual(enriched["ANZSRCFoRCode"], "32")
        self.assertEqual(enriched["ANZSRCFoRDivision"], "Biomedical and Clinical Sciences")
        self.assertEqual(enriched["ClinicalSpecialty"], "Medical Specialties")


if __name__ == "__main__":
    unittest.main()
