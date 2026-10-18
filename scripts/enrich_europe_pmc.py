"""Europe PMC API enrichment module for CHHHS Publication Registry.

Queries Europe PMC REST API (EBI) for grant funding, author ORCID identifiers,
PMCID, open-access full-text links, and preprints using polite, keyless access.
Zero API key or token required.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

EUROPE_PMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_USER_AGENT = "CHHHS-Research-Registry/1.0 (mailto:{{POLITE_EMAIL}})"


def clean_doi(raw_doi: Any) -> str | None:
    """Normalize DOI string."""
    if not raw_doi or not isinstance(raw_doi, str):
        return None
    cleaned = raw_doi.strip()
    cleaned = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', cleaned, flags=re.I).strip()
    if re.fullmatch(r'10\.\d{4,9}/\S+', cleaned):
        return cleaned
    return None


def clean_pmid(raw_pmid: Any) -> str | None:
    """Normalize PMID string."""
    if not raw_pmid:
        return None
    p = str(raw_pmid).strip()
    if p.isdigit() and int(p) > 0:
        return p
    return None


def build_europe_pmc_query(pmid: str | None = None, doi: str | None = None) -> str | None:
    """Construct Europe PMC search query from PMID or DOI."""
    c_pmid = clean_pmid(pmid)
    c_doi = clean_doi(doi)
    if c_pmid:
        return f"EXT_ID:{c_pmid} AND SRC:MED"
    if c_doi:
        return f'DOI:"{c_doi}"'
    return None


def fetch_europe_pmc_work(
    pmid: str | None = None,
    doi: str | None = None,
    timeout: int = 10,
) -> dict[str, Any] | None:
    """Fetch publication record from Europe PMC REST API."""
    query = build_europe_pmc_query(pmid=pmid, doi=doi)
    if not query:
        return None

    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": "1",
    }
    url = f"{EUROPE_PMC_BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("resultList", {}).get("result", [])
                if results:
                    return results[0]
    except urllib.error.HTTPError as e:
        logger.warning("HTTP error %d fetching Europe PMC for %s / %s: %s", e.code, pmid, doi, e.reason)
    except Exception as e:
        logger.warning("Error fetching Europe PMC for %s / %s: %s", pmid, doi, e)

    return None


def fetch_europe_pmc_batch(
    dois: list[str],
    timeout: int = 15,
) -> dict[str, dict[str, Any]]:
    """Fetch publication records for a batch of DOIs (up to 25 per request)."""
    cleaned_dois = [clean_doi(d) for d in dois if clean_doi(d)]
    if not cleaned_dois:
        return {}

    query = " OR ".join(f'DOI:"{d}"' for d in cleaned_dois)
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": str(len(cleaned_dois)),
    }
    url = f"{EUROPE_PMC_BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        },
    )

    results_by_doi: dict[str, dict[str, Any]] = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                for item in data.get("resultList", {}).get("result", []):
                    item_doi = clean_doi(item.get("doi"))
                    if item_doi:
                        results_by_doi[item_doi] = extract_europe_pmc_metrics(item)
    except urllib.error.HTTPError as e:
        logger.warning("HTTP error %d fetching Europe PMC batch: %s", e.code, e.reason)
    except Exception as e:
        logger.warning("Error fetching Europe PMC batch: %s", e)

    return results_by_doi


def extract_europe_pmc_metrics(raw_data: dict[str, Any] | None) -> dict[str, Any]:
    """Extract standard registry enrichment fields from raw Europe PMC result payload."""
    if not raw_data or not isinstance(raw_data, dict):
        return {
            "PMCID": None,
            "AuthorORCIDs": None,
            "EuropePMC_Funders": None,
            "EuropePMC_GrantIDs": None,
            "EuropePMC_OpenAccess": None,
            "EuropePMC_FullTextURL": None,
            "EuropePMC_CitedByCount": None,
        }

    pmcid = raw_data.get("pmcid")
    is_oa = raw_data.get("isOpenAccess") == "Y"

    # Extract author ORCIDs
    author_list = raw_data.get("authorList", {}).get("author", [])
    orcids = []
    for auth in author_list:
        if isinstance(auth, dict):
            auth_id = auth.get("authorId")
            if isinstance(auth_id, dict) and auth_id.get("type", "").upper() == "ORCID":
                val = auth_id.get("value")
                if val and val not in orcids:
                    orcids.append(val)

    # Extract Grants & Funders
    grants = raw_data.get("grantsList", {}).get("grant", [])
    funders = []
    grant_ids = []
    for g in grants:
        if isinstance(g, dict):
            agency = g.get("agency")
            if agency and agency not in funders:
                funders.append(agency)
            gid = g.get("grantId")
            if gid and gid not in grant_ids:
                grant_ids.append(gid)

    # Extract full text URL
    full_text_urls = raw_data.get("fullTextUrlList", {}).get("fullTextUrl", [])
    pdf_url = None
    html_url = None
    for ft in full_text_urls:
        if isinstance(ft, dict):
            doc_style = ft.get("documentStyle", "").lower()
            u = ft.get("url")
            if doc_style == "pdf" and not pdf_url:
                pdf_url = u
            elif doc_style == "html" and not html_url:
                html_url = u

    full_url = pdf_url or html_url

    # Citation count
    cited_by = raw_data.get("citedByCount")

    return {
        "PMCID": pmcid,
        "AuthorORCIDs": "; ".join(orcids) if orcids else None,
        "EuropePMC_Funders": "; ".join(funders) if funders else None,
        "EuropePMC_GrantIDs": "; ".join(grant_ids) if grant_ids else None,
        "EuropePMC_OpenAccess": "Open Access" if is_oa else None,
        "EuropePMC_FullTextURL": full_url,
        "EuropePMC_CitedByCount": int(cited_by) if cited_by is not None else None,
    }
