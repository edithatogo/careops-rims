#!/usr/bin/env python3
"""
Open Access Full-Text Paper Downloader and Archiver for CHHHS Publications.

Automated, keyless retrieval of open-access full-text PDFs using:
  1. Europe PMC / PubMed Central (PMC) direct PDF rendering
  2. Direct Open Access URLs (OpenAlex OAUrl)
  3. Repository landing page discovery (citation_pdf_url metadata tags)

Saves retrieved PDFs locally into data/papers/{CanonicalKey}.pdf and updates
registry metadata with download status, timestamps, and file sizes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = (
    "CHHHS-Research-Publications/1.0 "
    "(mailto:{{POLITE_EMAIL}}; Cairns and Hinterland Hospital and Health Service)"
)

DEFAULT_PAPERS_DIR = Path("data/papers")
DEFAULT_SEED_PATH = Path("private/ops/sharepoint-seed/publication-registry-seed.json")
DEFAULT_SEED_CSV = Path("private/ops/sharepoint-seed/publication-registry-seed.csv")


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as a filesystem filename."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)


def extract_pdf_url_from_html(html_text: str, base_url: str) -> Optional[str]:
    """Search HTML text for standard scholarly meta tags pointing to full-text PDF."""
    patterns = [
        r'<meta\s+name=["\']citation_pdf_url["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']citation_pdf_url["\']',
        r'<meta\s+name=["\']eprints\.document_url["\']\s+content=["\']([^"\']+\.pdf)["\']',
        r'<a\s+[^>]*href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\'][^>]*>(?:Download|PDF|Full\s*Text)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            url = match.group(1).strip()
            if url.startswith("//"):
                return "https:" + url
            elif url.startswith("/"):
                # Relative URL, resolve with base
                m = re.match(r'(https?://[^/]+)', base_url)
                if m:
                    return m.group(1) + url
            elif url.startswith("http://") or url.startswith("https://"):
                return url
    return None


def fetch_url(url: str, timeout: int = 20, max_bytes: int = 50 * 1024 * 1024) -> Tuple[int, bytes, str]:
    """
    Fetch content from URL with polite headers.
    Returns (status_code, body_bytes, content_type).
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/xhtml+xml,text/html,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "").lower()
        body = resp.read(max_bytes)
        return resp.status, body, content_type


def get_candidate_urls(item: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Generate ordered list of (url, source_label) candidates for a publication.
    """
    candidates: List[Tuple[str, str]] = []
    seen = set()

    pmcid = (item.get("PMCID") or "").strip()
    if pmcid:
        if not pmcid.upper().startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        # Europe PMC direct PDF renderer (fast, reliable)
        epmc_url = f"https://europepmc.org/articles/{pmcid}?pdf=render"
        candidates.append((epmc_url, "EuropePMC"))
        seen.add(epmc_url)
        # NCBI PMC direct fallback
        ncbi_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
        candidates.append((ncbi_url, "PubMedCentral"))
        seen.add(ncbi_url)

    epmc_ft = (item.get("EuropePMC_FullTextURL") or "").strip()
    if epmc_ft and epmc_ft not in seen:
        candidates.append((epmc_ft, "EuropePMC_FullText"))
        seen.add(epmc_ft)

    oa_url = (item.get("OAUrl") or "").strip()
    if oa_url and oa_url not in seen:
        candidates.append((oa_url, "OpenAlex_OAUrl"))
        seen.add(oa_url)

    return candidates


def download_single_paper(
    item: Dict[str, Any],
    output_dir: Path,
    force: bool = False,
    delay: float = 0.2,
) -> Dict[str, Any]:
    """
    Attempt downloading full-text PDF for a single publication.
    Returns download result metadata.
    """
    canonical_key = item.get("CanonicalKey") or sanitize_filename(item.get("Title", "unknown")[:50])
    target_filename = f"{canonical_key}.pdf"
    target_path = output_dir / target_filename

    # If file already exists and is valid, reuse
    if not force and target_path.exists() and target_path.stat().st_size > 1024:
        with open(target_path, "rb") as f:
            magic = f.read(5)
            if magic.startswith(b"%PDF-"):
                return {
                    "CanonicalKey": canonical_key,
                    "PDFDownloadStatus": "Already Exists",
                    "LocalPDFPath": str(target_path),
                    "PDFDownloadedUTC": datetime.fromtimestamp(target_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "PDFFileSize": target_path.stat().st_size,
                    "PDFSourceURL": item.get("PDFSourceURL", ""),
                }

    candidates = get_candidate_urls(item)
    if not candidates:
        return {
            "CanonicalKey": canonical_key,
            "PDFDownloadStatus": "No Open Access URL Available",
            "LocalPDFPath": "",
            "PDFDownloadedUTC": "",
            "PDFFileSize": 0,
            "PDFSourceURL": "",
        }

    for url, label in candidates:
        try:
            time.sleep(delay)
            status, body, content_type = fetch_url(url)
            if status != 200 or len(body) < 20:
                continue

            # Check if direct PDF
            if body.startswith(b"%PDF-") and len(body) >= 1024:
                target_path.write_bytes(body)
                now_utc = datetime.now(timezone.utc).isoformat()
                return {
                    "CanonicalKey": canonical_key,
                    "PDFDownloadStatus": "Downloaded",
                    "LocalPDFPath": str(target_path),
                    "PDFDownloadedUTC": now_utc,
                    "PDFFileSize": len(body),
                    "PDFSourceURL": url,
                    "PDFSource": label,
                }

            # If HTML, attempt to find citation_pdf_url
            if "text/html" in content_type or "application/xhtml" in content_type:
                try:
                    html_str = body[:500000].decode("utf-8", errors="ignore")
                    discovered_pdf_url = extract_pdf_url_from_html(html_str, url)
                    if discovered_pdf_url and discovered_pdf_url != url:
                        time.sleep(delay)
                        d_status, d_body, _ = fetch_url(discovered_pdf_url)
                        if d_status == 200 and d_body.startswith(b"%PDF-") and len(d_body) >= 1024:
                            target_path.write_bytes(d_body)
                            now_utc = datetime.now(timezone.utc).isoformat()
                            return {
                                "CanonicalKey": canonical_key,
                                "PDFDownloadStatus": "Downloaded",
                                "LocalPDFPath": str(target_path),
                                "PDFDownloadedUTC": now_utc,
                                "PDFFileSize": len(d_body),
                                "PDFSourceURL": discovered_pdf_url,
                                "PDFSource": f"{label}_DiscoveredPDF",
                            }
                except Exception:
                    pass

        except Exception:
            continue

    return {
        "CanonicalKey": canonical_key,
        "PDFDownloadStatus": "Download Failed: Unreachable or Paywalled",
        "LocalPDFPath": "",
        "PDFDownloadedUTC": "",
        "PDFFileSize": 0,
        "PDFSourceURL": "",
    }


def download_papers(
    publications: List[Dict[str, Any]],
    output_dir: Path = DEFAULT_PAPERS_DIR,
    month: Optional[str] = None,
    limit: Optional[int] = None,
    canonical_key: Optional[str] = None,
    force: bool = False,
    delay: float = 0.2,
    seed_json_path: Optional[Path] = None,
    seed_csv_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Batch download papers matching criteria.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter target list
    targets = publications
    if canonical_key:
        targets = [p for p in targets if p.get("CanonicalKey") == canonical_key]
    elif month:
        targets = [p for p in targets if p.get("PublicationMonth") == month]

    # Prioritize items with OA links, sorting PMCID items first
    targets = [p for p in targets if p.get("PMCID") or p.get("EuropePMC_FullTextURL") or p.get("OAUrl")]
    targets.sort(key=lambda x: (0 if (x.get("PMCID") or "").strip() else 1, 0 if (x.get("EuropePMC_FullTextURL") or "").strip() else 1))

    if limit and limit > 0:
        targets = targets[:limit]

    stats = {"total_targeted": len(targets), "downloaded": 0, "already_exists": 0, "failed": 0}
    results: List[Dict[str, Any]] = []

    print(f"Beginning download run for {len(targets)} publications into '{output_dir}'...")

    for i, item in enumerate(targets, 1):
        res = download_single_paper(item, output_dir, force=force, delay=delay)
        results.append(res)
        status = res["PDFDownloadStatus"]
        if status == "Downloaded":
            stats["downloaded"] += 1
            print(f"[{i}/{len(targets)}] [OK] Downloaded: {res['CanonicalKey'][:16]}... ({res['PDFFileSize'] // 1024} KB) from {res.get('PDFSource', 'Direct')}")
        elif status == "Already Exists":
            stats["already_exists"] += 1
            print(f"[{i}/{len(targets)}] [SKIP] Already on disk: {res['CanonicalKey'][:16]}...")
        else:
            stats["failed"] += 1
            print(f"[{i}/{len(targets)}] [FAIL] {res['CanonicalKey'][:16]}... ({status})")

        # Periodically flush progress to seed every 25 items
        if seed_json_path and seed_csv_path and (i % 25 == 0):
            try:
                update_seed_registry(seed_json_path, seed_csv_path, results)
            except Exception:
                pass

    return results, stats



def update_seed_registry(
    seed_json_path: Path,
    seed_csv_path: Path,
    download_results: List[Dict[str, Any]],
) -> int:
    """Update seed JSON and CSV files with download results."""
    if not seed_json_path.exists():
        return 0

    with open(seed_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res_map = {r["CanonicalKey"]: r for r in download_results if r.get("CanonicalKey")}
    updated_count = 0

    for item in data:
        key = item.get("CanonicalKey")
        if key in res_map:
            res = res_map[key]
            # Only update if downloaded or already exists, or not yet set
            if res["PDFDownloadStatus"] in ("Downloaded", "Already Exists"):
                item["LocalPDFPath"] = res["LocalPDFPath"]
                item["PDFDownloadStatus"] = res["PDFDownloadStatus"]
                item["PDFDownloadedUTC"] = res["PDFDownloadedUTC"]
                item["PDFFileSize"] = res["PDFFileSize"]
                if res.get("PDFSourceURL"):
                    item["PDFSourceURL"] = res["PDFSourceURL"]
                updated_count += 1
            elif not item.get("PDFDownloadStatus"):
                item["PDFDownloadStatus"] = res["PDFDownloadStatus"]

    # Write back JSON
    with open(seed_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Write back CSV
    if seed_csv_path.exists() and data:
        all_fieldnames: List[str] = []
        for r in data:
            for k in r.keys():
                if k not in all_fieldnames:
                    all_fieldnames.append(k)

        with open(seed_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_fieldnames)
            writer.writeheader()
            for r in data:
                writer.writerow(r)

    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Download and archive Open Access full-text research papers.")
    parser.add_argument("--month", type=str, help="Target publication month (YYYY-MM), e.g. 2026-08")
    parser.add_argument("--limit", type=int, help="Maximum number of papers to download")
    parser.add_argument("--canonical-key", type=str, help="Specific CanonicalKey to download")
    parser.add_argument("--all", action="store_true", help="Download all available OA papers")
    parser.add_argument("--force", action="store_true", help="Force re-download even if file already exists")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PAPERS_DIR, help="Destination directory for PDFs")
    parser.add_argument("--seed-json", type=Path, default=DEFAULT_SEED_PATH, help="Path to seed registry JSON")
    parser.add_argument("--seed-csv", type=Path, default=DEFAULT_SEED_CSV, help="Path to seed registry CSV")
    parser.add_argument("--no-update-seed", action="store_true", help="Do not update the seed files")
    args = parser.parse_args()

    if not args.seed_json.exists():
        print(f"Error: Seed registry JSON not found at {args.seed_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.seed_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    results, stats = download_papers(
        publications=data,
        output_dir=args.output_dir,
        month=args.month,
        limit=args.limit,
        canonical_key=args.canonical_key,
        force=args.force,
        seed_json_path=None if args.no_update_seed else args.seed_json,
        seed_csv_path=None if args.no_update_seed else args.seed_csv,
    )

    print("\nDownload Summary:")
    print(f"  Targeted:       {stats['total_targeted']}")
    print(f"  Downloaded:     {stats['downloaded']}")
    print(f"  Already Exists: {stats['already_exists']}")
    print(f"  Failed/Closed:  {stats['failed']}")

    if not args.no_update_seed and results:
        updated = update_seed_registry(args.seed_json, args.seed_csv, results)
        print(f"Updated {updated} seed registry records with PDF download metadata.")


if __name__ == "__main__":
    main()
