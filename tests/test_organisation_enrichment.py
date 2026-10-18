import unittest
from pathlib import Path

from scripts.organisation_enrichment import enrich_record, load_reference


class OrganisationEnrichmentTests(unittest.TestCase):
    def test_explicit_affiliation_maps_to_hierarchy(self):
        row = enrich_record({"Affiliations": "Department of Medicine, Cairns Base Hospital, CHHHS"})
        self.assertIn("chhhs", row["OrganisationKeys"])
        self.assertIn("chhhs:cairns", row["OrganisationKeys"])
        self.assertEqual(row["OrganisationMatchMethod"], "explicit-affiliation-alias")
        self.assertEqual(row["OrganisationMatchConfidence"], "high")

    def test_name_only_does_not_create_organisation_match(self):
        row = enrich_record({"Authors": "A Author"})
        self.assertEqual(row["OrganisationKeys"], "")
        self.assertEqual(row["OrganisationMatchConfidence"], "unknown")

    def test_reference_has_unique_keys_and_parent_links(self):
        reference = load_reference()
        self.assertEqual(len(reference), len(set(reference)))
        self.assertEqual(reference["chhhs:cairns"]["ParentOrganisationKey"], "chhhs")

    def test_generic_community_terms_do_not_match_unrelated_affiliation(self):
        row = enrich_record({"Affiliations": "Community Health, Brisbane"})
        self.assertEqual(row["OrganisationKeys"], "")
        self.assertEqual(row["OrganisationMatchConfidence"], "unknown")

    def test_partial_tokens_do_not_match_alias(self):
        row = enrich_record({"Affiliations": "Cairns Hospitality Research Centre"})
        self.assertEqual(row["OrganisationKeys"], "")

    def test_exact_affiliation_text_and_reference_dates_are_preserved(self):
        affiliation = "Department of Medicine, Cairns Base Hospital"
        row = enrich_record({"Affiliations": affiliation})
        self.assertEqual(row["AffiliationTextObserved"], affiliation)
        self.assertEqual(row["OrganisationReferenceVersion"], "2026-09-20")
        self.assertEqual(row["OrganisationEffectiveFrom"], "2026-09-20")

    def test_unknown_dates_are_not_created_for_unmatched_record(self):
        row = enrich_record({"Affiliations": "University of Queensland"})
        self.assertEqual(row["OrganisationEffectiveFrom"], "")
        self.assertEqual(row["OrganisationEffectiveTo"], "")

    def test_invalid_parent_links_are_rejected(self):
        with self.assertRaises(ValueError):
            load_reference(Path(__file__).parent / "fixtures" / "invalid-organisation-reference.json")

    def test_invalid_reference_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            load_reference(Path(__file__).parent / "fixtures" / "invalid-organisation-date.json")


if __name__ == "__main__":
    unittest.main()
