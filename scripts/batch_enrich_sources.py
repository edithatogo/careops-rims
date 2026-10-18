"""Batch enrichment script for CHHHS Publication Registry.

Enriches baseline publication records with live OpenAlex, Crossref, and Dimensions
metadata (citations, open access status, funder acknowledgments, grant IDs) with
rate-limiting, retry handling, and persistent local caching.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_openalex import clean_doi, extract_openalex_metrics, fetch_openalex_work_by_doi, fetch_openalex_batch
from enrich_crossref import extract_crossref_metrics, fetch_crossref_work_by_doi
from enrich_europe_pmc import extract_europe_pmc_metrics, fetch_europe_pmc_work, fetch_europe_pmc_batch
from keyless_classifiers import (
    classify_funding_type,
    is_internal_funding,
    classify_indigenous_health_focus,
    classify_study_design,
    extract_clinical_trial_ids,
)
from clinical_attribution import enrich_record_clinical_attribution
from open_access_trials import enrich_record_open_access_trials
from project_utils import save_json
from export_publication_register import safe_cell

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

CACHE_DIR = ROOT / "private/ops/enrichment-cache"
cache_lock = threading.Lock()


def load_cache() -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "doi_enrichment_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict[str, Any]) -> None:
    cache_file = CACHE_DIR / "doi_enrichment_cache.json"
    with cache_lock:
        save_json(cache_file, cache)


def fetch_doi_metrics(doi: str, email: str, delay: float = 0.05) -> tuple[str, dict[str, Any]]:
    """Fetch OpenAlex, Crossref, and Europe PMC metrics for a single DOI."""
    cached: dict[str, Any] = {}
    # 1. Fetch OpenAlex
    try:
        oa_data = fetch_openalex_work_by_doi(doi, email=email)
        if oa_data:
            cached.update(extract_openalex_metrics(oa_data))
    except Exception as e:
        logger.warning("OpenAlex fetch error for %s: %s", doi, e)

    # 2. Fetch Crossref
    try:
        cr_data = fetch_crossref_work_by_doi(doi, email=email)
        if cr_data:
            cr_metrics = extract_crossref_metrics(cr_data)
            if cr_metrics.get("CitationCount_Crossref") is not None:
                cached["CitationCount_Crossref"] = cr_metrics["CitationCount_Crossref"]
            if cr_metrics.get("Crossref_Funders"):
                existing = cached.get("FunderNames")
                cached["FunderNames"] = f"{existing}; {cr_metrics['Crossref_Funders']}" if existing else cr_metrics["Crossref_Funders"]
            if cr_metrics.get("Crossref_Grants"):
                existing = cached.get("GrantIDs")
                cached["GrantIDs"] = f"{existing}; {cr_metrics['Crossref_Grants']}" if existing else cr_metrics["Crossref_Grants"]
    except Exception as e:
        logger.warning("Crossref fetch error for %s: %s", doi, e)

    # 3. Fetch Europe PMC (Keyless EBI)
    try:
        epmc_data = fetch_europe_pmc_work(doi=doi)
        if epmc_data:
            epmc_metrics = extract_europe_pmc_metrics(epmc_data)
            if epmc_metrics.get("PMCID") and not cached.get("PMCID"):
                cached["PMCID"] = epmc_metrics["PMCID"]
            if epmc_metrics.get("AuthorORCIDs"):
                cached["AuthorORCIDs"] = epmc_metrics["AuthorORCIDs"]
            if epmc_metrics.get("EuropePMC_Funders"):
                existing = cached.get("FunderNames")
                cached["FunderNames"] = f"{existing}; {epmc_metrics['EuropePMC_Funders']}" if existing else epmc_metrics["EuropePMC_Funders"]
            if epmc_metrics.get("EuropePMC_GrantIDs"):
                existing = cached.get("GrantIDs")
                cached["GrantIDs"] = f"{existing}; {epmc_metrics['EuropePMC_GrantIDs']}" if existing else epmc_metrics["EuropePMC_GrantIDs"]
    except Exception as e:
        logger.warning("Europe PMC fetch error for %s: %s", doi, e)

    cached["CitationMetricsObservedUTC"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if delay > 0:
        time.sleep(delay)
    return doi, cached


def enrich_record_from_cache(rec: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    raw_doi = rec.get("DOI")
    doi = clean_doi(raw_doi)
    if doi and doi in cache:
        cached = cache[doi]
        for k, v in cached.items():
            if v is not None:
                rec[k] = v

    # Apply deterministic keyless classifiers
    rec["FundingType"] = classify_funding_type(rec.get("FunderNames"))
    rec["IsInternalFunding"] = is_internal_funding(rec.get("FunderNames"), rec.get("AttributionEvidence"))
    rec["IndigenousHealthFocus"] = classify_indigenous_health_focus(
        mesh=rec.get("MeSHHeadings"),
        keywords=rec.get("AuthorKeywords"),
        title=rec.get("Title")
    )
    rec["StudyDesign"] = classify_study_design(
        mesh=rec.get("MeSHHeadings"),
        title=rec.get("Title")
    )
    ct_id = extract_clinical_trial_ids(f"{rec.get('Title', '')} {rec.get('AttributionEvidence', '')} {rec.get('MeSHHeadings', '')}")
    rec["ClinicalTrialID"] = ct_id or None

    # Apply clinical attribution & specialty classification
    enrich_record_clinical_attribution(rec)

    # Apply Open Access and clinical trial linkage
    enrich_record_open_access_trials(rec)

    return rec


def chunk_list(items: list[Any], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def main():
    parser = argparse.ArgumentParser(description="Batch enrich publications from OpenAlex, Crossref, and Europe PMC.")
    parser.add_argument("--input-json", type=Path, default=ROOT / "private/ops/sharepoint-seed/publication-registry-seed.json")
    parser.add_argument("--output-json", type=Path, default=ROOT / "private/ops/sharepoint-seed/publication-registry-seed.json")
    parser.add_argument("--output-csv", type=Path, default=ROOT / "private/ops/sharepoint-seed/publication-registry-seed.csv")
    parser.add_argument("--email", type=str, default=os.environ.get("RESEARCH_POLITE_EMAIL", ""))
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay in seconds between requests per worker")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent workers for polite pool API calls")
    args = parser.parse_args()

    if not args.input_json.exists():
        logger.error("Input file %s does not exist", args.input_json)
        sys.exit(1)

    with open(args.input_json, "r", encoding="utf-8") as f:
        records = json.load(f)

    logger.info("Loaded %d records for enrichment.", len(records))
    cache = load_cache()
    logger.info("Loaded %d cached DOI enrichments.", len(cache))

    to_process = records[:args.limit] if args.limit else records

    # Identify all unique cleaned DOIs needing fetch
    all_dois = set()
    for rec in to_process:
        doi = clean_doi(rec.get("DOI"))
        if doi:
            all_dois.add(doi)

    uncached_dois = [d for d in all_dois if d not in cache]
    logger.info("Unique DOIs: %d (already cached: %d, needing fetch: %d)", len(all_dois), len(all_dois) - len(uncached_dois), len(uncached_dois))

    start_time = time.time()

    # Step 1: Fetch completely uncached DOIs via full fetch_doi_metrics
    if uncached_dois:
        logger.info("Starting concurrent enrichment of %d uncached DOIs with %d workers...", len(uncached_dois), args.workers)
        completed_count = 0
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_doi = {
                executor.submit(fetch_doi_metrics, doi, args.email, args.delay): doi
                for doi in uncached_dois
            }
            for future in as_completed(future_to_doi):
                doi, metrics = future.result()
                with cache_lock:
                    cache[doi] = metrics
                completed_count += 1
                if completed_count % 50 == 0 or completed_count == len(uncached_dois):
                    save_cache(cache)
                    logger.info("Fetched %d / %d DOIs (cache size: %d)...", completed_count, len(uncached_dois), len(cache))

        save_cache(cache)

    # Step 2: Batch enrich Europe PMC metrics (PMCID, AuthorORCIDs, Europe PMC grants) if missing
    epmc_missing = [d for d in all_dois if "PMCID" not in cache.get(d, {})]
    if epmc_missing:
        logger.info("Fetching Europe PMC metadata for %d DOIs in batches of 25...", len(epmc_missing))
        chunks = list(chunk_list(epmc_missing, 25))
        with ThreadPoolExecutor(max_workers=min(args.workers, 6)) as executor:
            future_to_chunk = {
                executor.submit(fetch_europe_pmc_batch, chunk): chunk
                for chunk in chunks
            }
            done_chunks = 0
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                res_dict = future.result()
                with cache_lock:
                    for d in chunk:
                        cache.setdefault(d, {})
                        if d in res_dict:
                            epmc_m = res_dict[d]
                            cache[d].update(epmc_m)
                            if epmc_m.get("EuropePMC_Funders"):
                                existing = cache[d].get("FunderNames")
                                cache[d]["FunderNames"] = f"{existing}; {epmc_m['EuropePMC_Funders']}" if existing else epmc_m["EuropePMC_Funders"]
                            if epmc_m.get("EuropePMC_GrantIDs"):
                                existing = cache[d].get("GrantIDs")
                                cache[d]["GrantIDs"] = f"{existing}; {epmc_m['EuropePMC_GrantIDs']}" if existing else epmc_m["EuropePMC_GrantIDs"]
                        else:
                            cache[d]["PMCID"] = None
                            cache[d]["AuthorORCIDs"] = None
                done_chunks += 1
                if done_chunks % 10 == 0 or done_chunks == len(chunks):
                    save_cache(cache)
                    logger.info("Europe PMC progress: %d / %d batches completed...", done_chunks, len(chunks))
        save_cache(cache)

    # Step 3: Batch enrich OpenAlex FieldOfResearch if missing
    oa_missing = [d for d in all_dois if "FieldOfResearch" not in cache.get(d, {})]
    if oa_missing:
        logger.info("Fetching OpenAlex FieldOfResearch for %d DOIs in batches of 50...", len(oa_missing))
        chunks = list(chunk_list(oa_missing, 50))
        with ThreadPoolExecutor(max_workers=min(args.workers, 6)) as executor:
            future_to_chunk = {
                executor.submit(fetch_openalex_batch, chunk, args.email): chunk
                for chunk in chunks
            }
            done_chunks = 0
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                res_dict = future.result()
                with cache_lock:
                    for d in chunk:
                        cache.setdefault(d, {})
                        if d in res_dict:
                            oa_m = res_dict[d]
                            for k, v in oa_m.items():
                                if k not in cache[d] or cache[d][k] is None:
                                    cache[d][k] = v
                        else:
                            cache[d]["FieldOfResearch"] = None
                done_chunks += 1
                if done_chunks % 10 == 0 or done_chunks == len(chunks):
                    save_cache(cache)
                    logger.info("OpenAlex progress: %d / %d batches completed...", done_chunks, len(chunks))
        save_cache(cache)

    # Now apply cache to all records
    for rec in records:
        enrich_record_from_cache(rec, cache)

    elapsed = time.time() - start_time
    logger.info("Enrichment pass completed in %.1f seconds.", elapsed)

    # Save JSON
    save_json(args.output_json, records)
    logger.info("Saved enriched JSON to %s", args.output_json)

    # Save CSV
    fieldnames = list(records[0].keys())
    # Ensure extended columns are present in header
    extended_fields = [
        "FunderNames", "GrantIDs", "FundingType", "IsInternalFunding",
        "ClinicalTrialID", "IndigenousHealthFocus", "StudyDesign",
        "LeadershipRole", "ANZSRCFoRCode", "ANZSRCFoRDivision", "ClinicalSpecialty",
        "OACategory", "OAComplianceNHMRC", "TrialRegistryID", "TrialRegistryURL",
        "FieldOfResearch", "PMCID", "AuthorORCIDs", "EuropePMC_Funders",
        "EuropePMC_GrantIDs", "EuropePMC_OpenAccess", "EuropePMC_FullTextURL",
        "EuropePMC_CitedByCount", "MeSHHeadings", "AuthorKeywords",
        "OpenAccessStatus", "OAUrl", "AffiliationsRaw", "AffiliationHierarchy",
        "CitationCount_Scopus", "CitationCount_Crossref", "CitationCount_OpenAlex",
        "CitationMetricsObservedUTC"
    ]
    for ef in extended_fields:
        if ef not in fieldnames:
            fieldnames.append(ef)

    with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            safe_row = {k: safe_cell(v) if isinstance(v, str) else v for k, v in r.items()}
            writer.writerow(safe_row)

    logger.info("Saved enriched CSV to %s", args.output_csv)


if __name__ == "__main__":
    main()
