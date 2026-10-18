"""Dimensions export ingestion and mapping module for CHHHS Publication Registry.

Parses exported publications from Dimensions (CSV or JSON) and extracts
citation metrics, field citation ratio (FCR), relative citation ratio (RCR),
and grant funding details.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def clean_doi(raw_doi: Any) -> str | None:
    """Normalize DOI string."""
    if not raw_doi or not isinstance(raw_doi, str):
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', cleaned, flags=re.I).strip()
    if re.fullmatch(r'10\.\d{4,9}/\S+', cleaned):
        return cleaned.lower()
    return None


def clean_pmid(raw_pmid: Any) -> str | None:
    """Normalize PMID string."""
    if not raw_pmid:
        return None
    p = str(raw_pmid).strip()
    if p.isdigit() and int(p) > 0:
        return p
    return None


def parse_dimensions_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse a Dimensions CSV export file into standardized publication records."""
    records = []
    if not file_path.exists():
        raise FileNotFoundError(f"Dimensions export not found: {file_path}")

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dim_id = row.get("Dimensions Publication ID") or row.get("Publication ID") or row.get("id")
            doi = clean_doi(row.get("DOI") or row.get("doi"))
            pmid = clean_pmid(row.get("PMID") or row.get("pmid"))
            title = row.get("Title") or row.get("title") or ""

            times_cited = row.get("Times cited") or row.get("citations_count") or row.get("Times Cited")
            try:
                citation_count = int(times_cited) if times_cited is not None and str(times_cited).strip().isdigit() else None
            except (ValueError, TypeError):
                citation_count = None

            rcr = row.get("Relative Citation Ratio (RCR)") or row.get("RCR")
            fcr = row.get("Field Citation Ratio (FCR)") or row.get("FCR")
            oa_status = row.get("Open Access") or row.get("open_access")

            funders = row.get("Funding Agency") or row.get("Funders")
            grants = row.get("Grant Number") or row.get("Grants")

            rec = {
                "source": "dimensions",
                "source_record_id": str(dim_id or doi or pmid or title),
                "DimensionsID": str(dim_id) if dim_id else None,
                "DOI": doi,
                "PMID": pmid,
                "Title": title.strip(),
                "Authors": row.get("Authors") or "",
                "Journal": row.get("Source title") or row.get("Journal") or "",
                "PublicationYear": int(row["Publication Year"]) if row.get("Publication Year", "").isdigit() else None,
                "CitationCount_Dimensions": citation_count,
                "RCR": float(rcr) if rcr and str(rcr).replace(".", "", 1).isdigit() else None,
                "FCR": float(fcr) if fcr and str(fcr).replace(".", "", 1).isdigit() else None,
                "OpenAccessStatus": str(oa_status).strip() if oa_status else None,
                "FunderNames": str(funders).strip() if funders else None,
                "GrantIDs": str(grants).strip() if grants else None,
            }
            records.append(rec)

    return records


def match_and_enrich_from_dimensions(registry_records: list[dict[str, Any]], dimensions_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match Dimensions records to registry items by DOI or PMID, merging citation metrics."""
    doi_map = {}
    pmid_map = {}
    for d in dimensions_records:
        if d.get("DOI"):
            doi_map[d["DOI"]] = d
        if d.get("PMID"):
            pmid_map[d["PMID"]] = d

    enriched_count = 0
    for r in registry_records:
        dim_match = None
        r_doi = clean_doi(r.get("DOI"))
        r_pmid = clean_pmid(r.get("PMID"))

        if r_doi and r_doi in doi_map:
            dim_match = doi_map[r_doi]
        elif r_pmid and r_pmid in pmid_map:
            dim_match = pmid_map[r_pmid]

        if dim_match:
            enriched_count += 1
            if dim_match["CitationCount_Dimensions"] is not None:
                r["CitationCount_Dimensions"] = dim_match["CitationCount_Dimensions"]
            if dim_match["RCR"] is not None:
                r["RCR"] = dim_match["RCR"]
            if dim_match["FCR"] is not None:
                r["FCR"] = dim_match["FCR"]
            if dim_match["FunderNames"] and not r.get("FunderNames"):
                r["FunderNames"] = dim_match["FunderNames"]
            if dim_match["GrantIDs"] and not r.get("GrantIDs"):
                r["GrantIDs"] = dim_match["GrantIDs"]
            if dim_match["OpenAccessStatus"] and not r.get("OpenAccessStatus"):
                r["OpenAccessStatus"] = dim_match["OpenAccessStatus"]

            sources = set(s.strip() for s in (r.get("SourceSet") or "").split(";") if s.strip())
            sources.add("Dimensions")
            r["SourceSet"] = "; ".join(sorted(sources))

    logger.info("Enriched %d registry records from Dimensions export.", enriched_count)
    return registry_records
