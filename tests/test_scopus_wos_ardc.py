import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ingest_scopus_wos import (
    clean_scopus_eid,
    clean_wos_ut,
    match_and_enrich_from_external,
    parse_ardc_rla_csv,
    parse_scopus_csv,
    parse_wos_csv,
)


class TestScopusWosArdcIngestion(unittest.TestCase):
    def test_clean_scopus_eid(self):
        self.assertEqual(clean_scopus_eid("2-s2.0-85012345678"), "2-s2.0-85012345678")
        self.assertEqual(clean_scopus_eid("2-S2.0-9999"), "2-s2.0-9999")
        self.assertIsNone(clean_scopus_eid("invalid-eid"))
        self.assertIsNone(clean_scopus_eid(""))

    def test_clean_wos_ut(self):
        self.assertEqual(clean_wos_ut("WOS:000123456700001"), "WOS:000123456700001")
        self.assertEqual(clean_wos_ut("wos:a1b2c3d4"), "WOS:A1B2C3D4")
        self.assertIsNone(clean_wos_ut("invalid-ut"))

    def test_parse_scopus_csv(self):
        csv_content = (
            "Title,Authors,Year,Source title,Cited by,DOI,PubMed ID,EID,Author Keywords,Affiliations,Funding Details,Open Access\n"
            '"Clinical Audit of Tropical Infections","Smith J, Doe A",2024,"Medical Journal of Australia",15,"10.1016/j.mja.2024.01.001","38123456","2-s2.0-85012345678","melioidosis; sepsis","Cairns Hospital, QLD","Queensland Health Health and Medical Research Fellowship","Gold"\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "scopus_export.csv"
            p.write_text(csv_content, encoding="utf-8")

            records = parse_scopus_csv(p)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["DOI"], "10.1016/j.mja.2024.01.001")
            self.assertEqual(rec["PMID"], "38123456")
            self.assertEqual(rec["ScopusEID"], "2-s2.0-85012345678")
            self.assertEqual(rec["CitationCount_Scopus"], 15)
            self.assertEqual(rec["PublicationYear"], 2024)
            self.assertIn("melioidosis", rec["AuthorKeywords"])
            self.assertIn("Cairns Hospital", rec["AffiliationsRaw"])

    def test_parse_wos_csv(self):
        csv_content = (
            'Article Title,Authors,Publication Year,Source Title,"Times Cited, WoS Core",DOI,Pubmed Id,"UT (Unique WOS ID)",Author Keywords,Addresses,Funding Orgs,Grant Numbers\n'
            '"Genomic Epidemiology in FNQ","Taylor B, Adams K",2023,"Lancet Infectious Diseases",42,"10.1016/s1473-3099(23)00123-4","37890123","WOS:000987654300002","genomics; Cairns","Cairns and Hinterland HHS","NHMRC","APP1182345"\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "wos_export.csv"
            p.write_text(csv_content, encoding="utf-8")

            records = parse_wos_csv(p)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["DOI"], "10.1016/s1473-3099(23)00123-4")
            self.assertEqual(rec["PMID"], "37890123")
            self.assertEqual(rec["WoSID"], "WOS:000987654300002")
            self.assertEqual(rec["CitationCount_WoS"], 42)
            self.assertEqual(rec["GrantIDs"], "APP1182345")

    def test_parse_ardc_rla_csv(self):
        csv_content = (
            "ActivityID,GrantID,PublicationDOI,PublicationTitle,Funder,LeadInstitution,ResearcherName,ORCID\n"
            '"act-1092","MRFF-2022-001","10.1016/j.mja.2024.01.001","Clinical Audit of Tropical Infections","MRFF","Cairns Hospital","Smith, John","0000-0001-2345-6789"\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "ardc_export.csv"
            p.write_text(csv_content, encoding="utf-8")

            records = parse_ardc_rla_csv(p)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["ActivityID"], "act-1092")
            self.assertEqual(rec["GrantIDs"], "MRFF-2022-001")
            self.assertEqual(rec["DOI"], "10.1016/j.mja.2024.01.001")

    def test_match_and_enrich_from_external(self):
        registry = [
            {
                "CanonicalKey": "CANONICAL-TEST-01",
                "DOI": "10.1016/j.mja.2024.01.001",
                "PMID": "38123456",
                "Title": "Clinical Audit of Tropical Infections",
                "SourceSet": "PubMed; DORA",
            }
        ]
        scopus_items = [
            {
                "DOI": "10.1016/j.mja.2024.01.001",
                "CitationCount_Scopus": 15,
                "AuthorKeywords": "tropical; infections",
                "AffiliationsRaw": "Cairns Hospital",
            }
        ]
        matched = match_and_enrich_from_external(registry, scopus_items, source_label="Scopus")
        self.assertEqual(matched, 1)
        self.assertEqual(registry[0]["CitationCount_Scopus"], 15)
        self.assertEqual(registry[0]["AuthorKeywords"], "tropical; infections")
        self.assertEqual(registry[0]["AffiliationsRaw"], "Cairns Hospital")
        self.assertEqual(registry[0]["SourceSet"], "PubMed; DORA; Scopus")


if __name__ == "__main__":
    unittest.main()
