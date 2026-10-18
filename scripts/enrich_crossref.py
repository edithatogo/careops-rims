"""Crossref REST API enrichment module for CHHHS Publication Registry.

Queries Crossref API for citation counts, funder acknowledgments, and license details.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
import urllib.parse
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

CROSSREF_BASE_URL = "https://api.crossref.org/works"
DEFAULT_POLITE_EMAIL = os.environ.get("CROSSREF_POLITE_EMAIL", "")
USER_AGENT = f"CHHHS-Research-Registry/1.0 (mailto:{DEFAULT_POLITE_EMAIL})"


def clean_doi(raw_doi: Any) -> str | None:
    """Normalize DOI string by stripping URL prefixes and whitespace."""
    if not raw_doi or not isinstance(raw_doi, str):
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', cleaned, flags=re.I).strip()
    if re.fullmatch(r'10\.\d{4,9}/\S+', cleaned):
        return cleaned
    return None


def fetch_crossref_work_by_doi(doi: str, email: str = DEFAULT_POLITE_EMAIL, timeout: int = 10) -> dict[str, Any] | None:
    """Fetch Crossref metadata for a single DOI."""
    normalized_doi = clean_doi(doi)
    if not normalized_doi:
        return None

    encoded_doi = urllib.parse.quote(normalized_doi)
    url = f"{CROSSREF_BASE_URL}/{encoded_doi}?mailto={urllib.parse.quote(email)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("message")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug("DOI %s not found in Crossref", normalized_doi)
        else:
            logger.warning("HTTP error %d fetching Crossref for DOI %s: %s", e.code, normalized_doi, e.reason)
    except Exception as e:
        logger.warning("Error fetching Crossref for DOI %s: %s", normalized_doi, e)

    return None


def extract_crossref_metrics(raw_message: dict[str, Any] | None) -> dict[str, Any]:
    """Extract standard registry enrichment fields from Crossref message payload."""
    if not raw_message or not isinstance(raw_message, dict):
        return {
            "CitationCount_Crossref": None,
            "Crossref_Funders": None,
            "Crossref_Grants": None,
            "Crossref_License": None,
        }

    citations = raw_message.get("is-referenced-by-count")

    # Funders & Grants
    funders = raw_message.get("funder", [])
    funder_names = []
    grant_ids = []
    for f in funders:
        if isinstance(f, dict):
            name = f.get("name")
            if name and name not in funder_names:
                funder_names.append(name)
            awards = f.get("award", [])
            for aw in awards:
                if aw and aw not in grant_ids:
                    grant_ids.append(str(aw))

    # License
    licenses = raw_message.get("license", [])
    license_urls = [lic.get("URL") for lic in licenses if isinstance(lic, dict) and lic.get("URL")]

    return {
        "CitationCount_Crossref": int(citations) if citations is not None else None,
        "Crossref_Funders": "; ".join(funder_names) if funder_names else None,
        "Crossref_Grants": "; ".join(grant_ids) if grant_ids else None,
        "Crossref_License": "; ".join(license_urls[:3]) if license_urls else None,
    }


def enrich_record_with_crossref(record: dict[str, Any], email: str = DEFAULT_POLITE_EMAIL) -> dict[str, Any]:
    """Enrich a publication dictionary in-place with Crossref metrics."""
    doi = record.get("DOI")
    if not doi:
        return record

    message = fetch_crossref_work_by_doi(doi, email=email)
    if message:
        metrics = extract_crossref_metrics(message)
        if metrics["CitationCount_Crossref"] is not None:
            record["CitationCount_Crossref"] = metrics["CitationCount_Crossref"]
        if metrics["Crossref_Funders"]:
            existing = record.get("FunderNames")
            record["FunderNames"] = f"{existing}; {metrics['Crossref_Funders']}" if existing else metrics["Crossref_Funders"]
        if metrics["Crossref_Grants"]:
            existing = record.get("GrantIDs")
            record["GrantIDs"] = f"{existing}; {metrics['Crossref_Grants']}" if existing else metrics["Crossref_Grants"]
        record["CitationMetricsObservedUTC"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return record
