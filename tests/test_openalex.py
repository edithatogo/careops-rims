"""Unit tests for OpenAlex keyless enrichment adapter."""
import json
import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_openalex import (
    clean_doi,
    extract_openalex_metrics,
    fetch_openalex_batch,
)


class TestOpenAlex(unittest.TestCase):
    def test_clean_doi(self):
        self.assertEqual(clean_doi("https://doi.org/10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("http://dx.doi.org/10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("doi: 10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("10.1000/182"), "10.1000/182")
        self.assertIsNone(clean_doi("invalid-doi"))
        self.assertIsNone(clean_doi(None))

    def test_extract_openalex_metrics(self):
        sample_payload = {
            "id": "https://openalex.org/W123456789",
            "cited_by_count": 42,
            "open_access": {
                "oa_status": "gold",
                "oa_url": "https://journal.org/article.pdf",
            },
            "grants": [
                {"funder_display_name": "NHMRC", "award_id": "APP12345"},
                {"funder_display_name": "Queensland Health", "award_id": "QH2026"},
            ],
            "mesh": [
                {"descriptor_name": "Cardiovascular Diseases"},
                {"descriptor_name": "Indigenous Health"},
            ],
            "keywords": [
                {"keyword": "tropical medicine"},
                {"keyword": "far north queensland"},
            ],
            "authorships": [
                {
                    "institutions": [
                        {"display_name": "Cairns Hospital", "ror": "https://ror.org/123", "country_code": "AU"}
                    ]
                }
            ],
            "primary_topic": {
                "display_name": "Tropical Infectious Diseases",
                "field": {"display_name": "Medicine"},
            },
        }

        metrics = extract_openalex_metrics(sample_payload)
        self.assertEqual(metrics["OpenAlexID"], "https://openalex.org/W123456789")
        self.assertEqual(metrics["CitationCount_OpenAlex"], 42)
        self.assertEqual(metrics["OpenAccessStatus"], "Gold")
        self.assertEqual(metrics["OAUrl"], "https://journal.org/article.pdf")
        self.assertIn("NHMRC", metrics["FunderNames"])
        self.assertIn("Queensland Health", metrics["FunderNames"])
        self.assertIn("APP12345", metrics["GrantIDs"])
        self.assertIn("Cardiovascular Diseases", metrics["MeSHHeadings"])
        self.assertIn("tropical medicine", metrics["AuthorKeywords"])
        self.assertIn("Cairns Hospital", metrics["AffiliationsRaw"])
        self.assertEqual(metrics["FieldOfResearch"], "Medicine")

    def test_fetch_openalex_batch_mocked(self):
        mock_response = MagicMock()
        mock_response.status = 200
        payload = {
            "results": [
                {"doi": "https://doi.org/10.1000/182", "cited_by_count": 10},
                {"doi": "https://doi.org/10.1000/183", "cited_by_count": 20},
            ]
        }
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("enrich_openalex._open_request", return_value=mock_response):
            res = fetch_openalex_batch(["10.1000/182", "10.1000/183"])
            self.assertIn("10.1000/182", res)
            self.assertIn("10.1000/183", res)
            self.assertEqual(res["10.1000/182"]["CitationCount_OpenAlex"], 10)
            self.assertEqual(res["10.1000/183"]["CitationCount_OpenAlex"], 20)


if __name__ == "__main__":
    unittest.main()
