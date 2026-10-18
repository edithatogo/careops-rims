#!/usr/bin/env python3
"""
Unit tests for Open Access full-text paper downloader.
"""

import json
import tempfile
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from download_oa_papers import (
    download_single_paper,
    extract_pdf_url_from_html,
    get_candidate_urls,
    sanitize_filename,
    update_seed_registry,
)


class TestDownloadOAPapers(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("a/b:c*d?e"), "a_b_c_d_e")
        self.assertEqual(sanitize_filename("normal-name_123"), "normal-name_123")

    def test_extract_pdf_url_from_html(self):
        # citation_pdf_url meta tag
        html1 = '<html><head><meta name="citation_pdf_url" content="https://example.org/doc.pdf"></head></html>'
        self.assertEqual(extract_pdf_url_from_html(html1, "https://example.org/page"), "https://example.org/doc.pdf")

        # relative URL
        html2 = '<html><head><meta name="citation_pdf_url" content="/content/paper.pdf"></head></html>'
        self.assertEqual(extract_pdf_url_from_html(html2, "https://example.org/articles/123"), "https://example.org/content/paper.pdf")

        # eprints tag
        html3 = '<html><head><meta name="eprints.document_url" content="https://repo.org/eprint/123.pdf"></head></html>'
        self.assertEqual(extract_pdf_url_from_html(html3, "https://repo.org/123"), "https://repo.org/eprint/123.pdf")

        # no PDF tag
        html_none = '<html><head><title>No PDF here</title></head></html>'
        self.assertIsNone(extract_pdf_url_from_html(html_none, "https://example.org"))

    def test_get_candidate_urls(self):
        item = {
            "PMCID": "PMC1234567",
            "EuropePMC_FullTextURL": "https://europepmc.org/articles/PMC1234567?pdf=render",
            "OAUrl": "https://doi.org/10.1234/custom.pdf",
        }
        candidates = get_candidate_urls(item)
        urls = [c[0] for c in candidates]
        self.assertIn("https://europepmc.org/articles/PMC1234567?pdf=render", urls)
        self.assertIn("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/pdf/", urls)
        self.assertIn("https://doi.org/10.1234/custom.pdf", urls)

    def test_download_single_paper_success_direct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            item = {
                "CanonicalKey": "test_key_001",
                "PMCID": "PMC999999",
            }
            fake_pdf_bytes = b"%PDF-1.4 Fake PDF stream for testing " + b"X" * 2000

            with patch("download_oa_papers.fetch_url", return_value=(200, fake_pdf_bytes, "application/pdf")):
                res = download_single_paper(item, out_dir, delay=0)

            self.assertEqual(res["PDFDownloadStatus"], "Downloaded")
            self.assertEqual(res["PDFFileSize"], len(fake_pdf_bytes))
            saved_file = out_dir / "test_key_001.pdf"
            self.assertTrue(saved_file.exists())
            self.assertEqual(saved_file.read_bytes(), fake_pdf_bytes)

    def test_download_single_paper_html_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            item = {
                "CanonicalKey": "test_key_discovery",
                "OAUrl": "https://publisher.com/article/100",
            }
            landing_html = b'<html><head><meta name="citation_pdf_url" content="https://publisher.com/article/100.pdf"></head></html>'
            fake_pdf_bytes = b"%PDF-1.5 Discovered PDF " + b"Z" * 1500

            def mock_fetch(url, **kwargs):
                if url == "https://publisher.com/article/100":
                    return 200, landing_html, "text/html"
                elif url == "https://publisher.com/article/100.pdf":
                    return 200, fake_pdf_bytes, "application/pdf"
                return 404, b"", ""

            with patch("download_oa_papers.fetch_url", side_effect=mock_fetch):
                res = download_single_paper(item, out_dir, delay=0)

            self.assertEqual(res["PDFDownloadStatus"], "Downloaded")
            self.assertIn("DiscoveredPDF", res.get("PDFSource", ""))
            saved_file = out_dir / "test_key_discovery.pdf"
            self.assertTrue(saved_file.exists())

    def test_download_single_paper_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            target = out_dir / "test_key_existing.pdf"
            existing_bytes = b"%PDF-1.4 Existing PDF " + b"E" * 2000
            target.write_bytes(existing_bytes)

            item = {"CanonicalKey": "test_key_existing", "PMCID": "PMC1111"}
            res = download_single_paper(item, out_dir, force=False, delay=0)

            self.assertEqual(res["PDFDownloadStatus"], "Already Exists")
            self.assertEqual(res["PDFFileSize"], len(existing_bytes))

    def test_download_single_paper_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            item = {"CanonicalKey": "closed_doc"}  # No links
            res = download_single_paper(item, out_dir, delay=0)
            self.assertEqual(res["PDFDownloadStatus"], "No Open Access URL Available")

    def test_update_seed_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            json_file = tmp_path / "seed.json"
            csv_file = tmp_path / "seed.csv"

            initial_data = [
                {"CanonicalKey": "key_1", "Title": "Paper 1"},
                {"CanonicalKey": "key_2", "Title": "Paper 2"},
            ]
            json_file.write_text(json.dumps(initial_data), encoding="utf-8")
            csv_file.write_text("CanonicalKey,Title\nkey_1,Paper 1\nkey_2,Paper 2\n", encoding="utf-8")

            results = [
                {
                    "CanonicalKey": "key_1",
                    "PDFDownloadStatus": "Downloaded",
                    "LocalPDFPath": "data/papers/key_1.pdf",
                    "PDFDownloadedUTC": "2026-09-18T04:00:00Z",
                    "PDFFileSize": 50000,
                    "PDFSourceURL": "https://example.org/key_1.pdf",
                }
            ]

            count = update_seed_registry(json_file, csv_file, results)
            self.assertEqual(count, 1)

            with open(json_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved[0]["PDFDownloadStatus"], "Downloaded")
            self.assertEqual(saved[0]["LocalPDFPath"], "data/papers/key_1.pdf")
            self.assertEqual(saved[0]["PDFFileSize"], 50000)


if __name__ == "__main__":
    unittest.main()
