"""Unit tests for Europe PMC keyless enrichment adapter."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_europe_pmc import (
    clean_doi,
    clean_pmid,
    build_europe_pmc_query,
    extract_europe_pmc_metrics,
)


class TestEuropePmc(unittest.TestCase):
    def test_clean_identifiers(self):
        self.assertEqual(clean_doi("https://doi.org/10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("10.1000/182"), "10.1000/182")
        self.assertIsNone(clean_doi("invalid-doi"))

        self.assertEqual(clean_pmid("12345678"), "12345678")
        self.assertEqual(clean_pmid(12345678), "12345678")
        self.assertIsNone(clean_pmid("not-a-number"))

    def test_build_query(self):
        self.assertEqual(build_europe_pmc_query(pmid="12345"), "EXT_ID:12345 AND SRC:MED")
        self.assertEqual(build_europe_pmc_query(doi="10.1000/182"), 'DOI:"10.1000/182"')
        self.assertIsNone(build_europe_pmc_query())

    def test_extract_metrics(self):
        sample_payload = {
            "pmcid": "PMC9876543",
            "isOpenAccess": "Y",
            "citedByCount": 15,
            "authorList": {
                "author": [
                    {
                        "fullName": "Mordaunt D",
                        "authorId": {"type": "ORCID", "value": "0000-0002-1234-5678"},
                    },
                    {
                        "fullName": "Smith J",
                    },
                ]
            },
            "grantsList": {
                "grant": [
                    {
                        "grantId": "APP123456",
                        "agency": "National Health and Medical Research Council",
                    },
                    {
                        "grantId": "EMF-2026-01",
                        "agency": "Emergency Medicine Foundation",
                    },
                ]
            },
            "fullTextUrlList": {
                "fullTextUrl": [
                    {"documentStyle": "html", "url": "https://europepmc.org/articles/PMC9876543"},
                    {"documentStyle": "pdf", "url": "https://europepmc.org/articles/PMC9876543?pdf=render"},
                ]
            },
        }

        metrics = extract_europe_pmc_metrics(sample_payload)
        self.assertEqual(metrics["PMCID"], "PMC9876543")
        self.assertEqual(metrics["AuthorORCIDs"], "0000-0002-1234-5678")
        self.assertIn("National Health and Medical Research Council", metrics["EuropePMC_Funders"])
        self.assertIn("Emergency Medicine Foundation", metrics["EuropePMC_Funders"])
        self.assertIn("APP123456", metrics["EuropePMC_GrantIDs"])
        self.assertIn("EMF-2026-01", metrics["EuropePMC_GrantIDs"])
        self.assertEqual(metrics["EuropePMC_OpenAccess"], "Open Access")
        self.assertEqual(metrics["EuropePMC_FullTextURL"], "https://europepmc.org/articles/PMC9876543?pdf=render")
        self.assertEqual(metrics["EuropePMC_CitedByCount"], 15)

    def test_fetch_europe_pmc_batch_mocked(self):
        from unittest.mock import patch, MagicMock
        from enrich_europe_pmc import fetch_europe_pmc_batch
        import io
        import json

        mock_response = MagicMock()
        mock_response.status = 200
        payload = {
            "resultList": {
                "result": [
                    {"doi": "10.1000/182", "pmcid": "PMC111111", "isOpenAccess": "Y"},
                    {"doi": "10.1000/183", "pmcid": "PMC222222", "isOpenAccess": "N"},
                ]
            }
        }
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            res = fetch_europe_pmc_batch(["10.1000/182", "10.1000/183"])
            self.assertIn("10.1000/182", res)
            self.assertIn("10.1000/183", res)
            self.assertEqual(res["10.1000/182"]["PMCID"], "PMC111111")
            self.assertEqual(res["10.1000/183"]["PMCID"], "PMC222222")


if __name__ == "__main__":
    unittest.main()
