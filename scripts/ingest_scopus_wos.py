"""Scopus, Web of Science (WoS), and ARDC RLA Ingestion and Enrichment Module.

Parses structured exports from Scopus, Web of Science, and ARDC Research Link Australia,
extracting persistent identifiers (Scopus EID, WoS UT, ARDC Grant IDs), citation counts,
author affiliations, and funding details, and conservatively merges them into the
CHHHS Publication Registry.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

from enrich_openalex import clean_doi
from ingest_dimensions import clean_pmid

logger = logging.getLogger(__name__)


def clean_scopus_eid(raw_eid: Any) -> str | None:
    """Normalize Scopus EID (e.g. 2-s2.0-85012345678)."""
    if not raw_eid or not isinstance(raw_eid, str):
        return None
    eid = raw_eid.strip()
    if re.fullmatch(r'2-s2\.0-\d+', eid, flags=re.I):
        return eid.lower()
    return None


def clean_wos_ut(raw_ut: Any) -> str | None:
    """Normalize Web of Science UT identifier (e.g. WOS:000123456700001)."""
    if not raw_ut or not isinstance(raw_ut, str):
        return None
    ut = raw_ut.strip()
    if re.fullmatch(r'WOS:[A-Za-z0-9]+', ut, flags=re.I):
        return ut.upper()
    return None


def parse_scopus_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse a Scopus CSV export into standardized publication records."""
    records = []
    if not file_path.exists():
        raise FileNotFoundError(f"Scopus export not found: {file_path}")

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = clean_doi(row.get("DOI") or row.get("doi"))
            pmid = clean_pmid(row.get("PubMed ID") or row.get("PMID") or row.get("pubmed_id"))
            eid = clean_scopus_eid(row.get("EID") or row.get("eid"))
            title = (row.get("Title") or row.get("title") or "").strip()

            cited_by = row.get("Cited by") or row.get("cited_by")
            try:
                scopus_citations = int(cited_by) if cited_by is not None and str(cited_by).strip().isdigit() else None
            except (ValueError, TypeError):
                scopus_citations = None

            pub_year = None
            raw_year = row.get("Year") or row.get("year")
            if raw_year and str(raw_year).strip().isdigit():
                pub_year = int(str(raw_year).strip())

            rec = {
                "source": "scopus",
                "source_record_id": eid or doi or pmid or title,
                "ScopusEID": eid,
                "DOI": doi,
                "PMID": pmid,
                "Title": title,
                "Authors": (row.get("Authors") or row.get("authors") or "").strip(),
                "Journal": (row.get("Source title") or row.get("source_title") or "").strip(),
                "PublicationYear": pub_year,
                "CitationCount_Scopus": scopus_citations,
                "AuthorKeywords": (row.get("Author Keywords") or "").strip() or None,
                "AffiliationsRaw": (row.get("Affiliations") or "").strip() or None,
                "FunderNames": (row.get("Funding Details") or row.get("Funding Text 1") or "").strip() or None,
                "OpenAccessStatus": (row.get("Open Access") or "").strip() or None,
            }
            records.append(rec)
    return records


def parse_wos_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse a Web of Science CSV or TSV export into standardized records."""
    records = []
    if not file_path.exists():
        raise FileNotFoundError(f"Web of Science export not found: {file_path}")

    # Detect delimiter
    sample = file_path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    delimiter = "\t" if "\t" in sample and sample.count("\t") > sample.count(",") else ","

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            doi = clean_doi(row.get("DOI") or row.get("doi"))
            pmid = clean_pmid(row.get("Pubmed Id") or row.get("PubMed ID") or row.get("PMID"))
            wos_id = clean_wos_ut(row.get("UT (Unique WOS ID)") or row.get("UT") or row.get("wos_id"))
            title = (row.get("Article Title") or row.get("Title") or "").strip()

            times_cited = row.get("Times Cited, WoS Core") or row.get("Times Cited, All Databases") or row.get("Times Cited")
            try:
                wos_citations = int(times_cited) if times_cited is not None and str(times_cited).strip().isdigit() else None
            except (ValueError, TypeError):
                wos_citations = None

            pub_year = None
            raw_year = row.get("Publication Year") or row.get("Year")
            if raw_year and str(raw_year).strip().isdigit():
                pub_year = int(str(raw_year).strip())

            rec = {
                "source": "wos",
                "source_record_id": wos_id or doi or pmid or title,
                "WoSID": wos_id,
                "DOI": doi,
                "PMID": pmid,
                "Title": title,
                "Authors": (row.get("Authors") or row.get("Author Full Names") or "").strip(),
                "Journal": (row.get("Source Title") or row.get("Journal") or "").strip(),
                "PublicationYear": pub_year,
                "CitationCount_WoS": wos_citations,
                "AuthorKeywords": (row.get("Author Keywords") or row.get("Keywords Plus") or "").strip() or None,
                "AffiliationsRaw": (row.get("Addresses") or row.get("Affiliations") or "").strip() or None,
                "FunderNames": (row.get("Funding Orgs") or row.get("Funding Name Preferred") or "").strip() or None,
                "GrantIDs": (row.get("Grant Numbers") or "").strip() or None,
            }
            records.append(rec)
    return records


def parse_ardc_rla_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse ARDC Research Link Australia / Research Data Australia export."""
    records = []
    if not file_path.exists():
        raise FileNotFoundError(f"ARDC export not found: {file_path}")

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = clean_doi(row.get("PublicationDOI") or row.get("DOI") or row.get("doi"))
            activity_id = (row.get("ActivityID") or row.get("Activity ID") or "").strip()
            grant_id = (row.get("GrantID") or row.get("Grant ID") or "").strip()
            title = (row.get("PublicationTitle") or row.get("Title") or "").strip()

            rec = {
                "source": "ardc",
                "source_record_id": activity_id or grant_id or doi or title,
                "ActivityID": activity_id or None,
                "GrantIDs": grant_id or None,
                "DOI": doi,
                "Title": title,
                "FunderNames": (row.get("Funder") or row.get("FundingBody") or "").strip() or None,
                "LeadInstitution": (row.get("LeadInstitution") or "").strip() or None,
                "ResearcherName": (row.get("ResearcherName") or "").strip() or None,
                "ORCID": (row.get("ORCID") or "").strip() or None,
            }
            records.append(rec)
    return records


def match_and_enrich_from_external(
    registry_records: list[dict[str, Any]],
    external_records: list[dict[str, Any]],
    source_label: str = "Scopus",
) -> int:
    """Match external records to registry items by DOI or PMID, merging enriched attributes.
    
    Returns the count of successfully matched registry records.
    """
    doi_map: dict[str, dict[str, Any]] = {}
    pmid_map: dict[str, dict[str, Any]] = {}

    for ext in external_records:
        if ext.get("DOI"):
            doi_map[ext["DOI"]] = ext
        if ext.get("PMID"):
            pmid_map[ext["PMID"]] = ext

    matched_count = 0
    for r in registry_records:
        r_doi = clean_doi(r.get("DOI"))
        r_pmid = clean_pmid(r.get("PMID"))

        matched = None
        if r_doi and r_doi in doi_map:
            matched = doi_map[r_doi]
        elif r_pmid and r_pmid in pmid_map:
            matched = pmid_map[r_pmid]

        if not matched:
            continue

        matched_count += 1

        # Enrich Scopus Citation Count
        if matched.get("CitationCount_Scopus") is not None:
            r["CitationCount_Scopus"] = matched["CitationCount_Scopus"]

        # Enrich WoS Citation Count
        if matched.get("CitationCount_WoS") is not None:
            r["CitationCount_WoS"] = matched["CitationCount_WoS"]

        # Enrich Funders & Grants
        if matched.get("FunderNames"):
            curr = r.get("FunderNames")
            if not curr:
                r["FunderNames"] = matched["FunderNames"]
            elif matched["FunderNames"] not in curr:
                r["FunderNames"] = f"{curr}; {matched['FunderNames']}"

        if matched.get("GrantIDs"):
            curr = r.get("GrantIDs")
            if not curr:
                r["GrantIDs"] = matched["GrantIDs"]
            elif matched["GrantIDs"] not in curr:
                r["GrantIDs"] = f"{curr}; {matched['GrantIDs']}"

        # Enrich Keywords
        if matched.get("AuthorKeywords") and not r.get("AuthorKeywords"):
            r["AuthorKeywords"] = matched["AuthorKeywords"]

        # Enrich Affiliations
        if matched.get("AffiliationsRaw") and not r.get("AffiliationsRaw"):
            r["AffiliationsRaw"] = matched["AffiliationsRaw"]

        # Append source to SourceSet if not already present
        curr_source_set = r.get("SourceSet", "")
        if source_label not in curr_source_set:
            r["SourceSet"] = f"{curr_source_set}; {source_label}" if curr_source_set else source_label

    return matched_count
