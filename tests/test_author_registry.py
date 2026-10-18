import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from author_registry import author_statistics, build_author_registry, normalise_name


class AuthorRegistryTests(unittest.TestCase):
    def test_structured_pubmed_evidence_is_preserved(self):
        authors, evidence = build_author_registry([
            {"PMID": "123", "AuthorIndex": 1, "AuthorName": "Doe, Jane", "AffiliationIndex": 1,
             "AffiliationText": "Cairns Hospital", "EvidenceKind": "structured", "ORCID": "0000-0001"},
            {"PMID": "123", "AuthorIndex": 2, "AuthorName": "Smith, Alex", "AffiliationIndex": 2,
             "AffiliationText": "University", "EvidenceKind": "structured"},
        ])
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0]["IdentityStatus"], "Confirmed")
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0]["AffiliationText"], "Cairns Hospital")

    def test_name_only_dora_records_do_not_become_confirmed(self):
        authors, evidence = build_author_registry(dora_records=[
            {"DORAKey": "1/9", "DORAURL": "https://dora.example/1/9", "Authors": "Doe, Jane; Doe, Jane"}
        ])
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0]["IdentityStatus"], "Unresolved")
        self.assertEqual(len(evidence), 2)
        self.assertTrue(all(item["ReviewStatus"] == "Needs Review" for item in evidence))

    def test_statistics_expose_unknown_completeness(self):
        authors, evidence = build_author_registry(dora_records=[{"DORAKey": "1/9", "Authors": "Doe, Jane"}])
        stats = author_statistics(authors, evidence)
        self.assertEqual(stats["AuthorCount"], 1)
        self.assertEqual(stats["Completeness"], "not_established")

    def test_name_normalisation_is_non_destructive(self):
        self.assertEqual(normalise_name("Doe, Jane"), "doejane")


if __name__ == "__main__":
    unittest.main()
