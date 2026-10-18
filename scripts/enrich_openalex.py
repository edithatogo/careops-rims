"""OpenAlex API enrichment module for CHHHS Publication Registry.

Queries OpenAlex REST API for work metadata, citation counts, open access status,
grants/funders, and keywords using polite pool headers.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import sys
import subprocess
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
import urllib.error

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_utils import ROOT, save_json

logger = logging.getLogger(__name__)

OPENALEX_BASE_URL = "https://api.openalex.org/works"
DEFAULT_POLITE_EMAIL = os.environ.get("OPENALEX_POLITE_EMAIL", "")
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


@dataclass(frozen=True)
class OpenAlexObservation:
    status: str
    payload: dict[str, Any] | None = None
    attempts: int = 0
    http_status: int | None = None
    raw_body: bytes | None = None


def _api_key() -> str | None:
    """Use an explicit environment key, then the macOS Keychain; never log it."""
    key = os.environ.get("OPENALEX_API_KEY")
    if key is not None:
        return key.strip() or None
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["/usr/bin/security", "find-generic-password", "-s",
                 "chhhs-rims.openalex", "-a", "rims", "-w"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer credential to a redirected resource.
        return None


def _open_request(request, timeout):
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _retry_delay(value: str | None, attempt: int) -> float | None:
    if not value:
        return float(2 ** (attempt - 1))
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    # Long/quota waits stop this pass instead of sleeping or retrying too early.
    return max(0.0, seconds) if 0 <= seconds <= 8 else None


def _request_observation(url: str, timeout: int) -> OpenAlexObservation:
    headers = {"Accept": "application/json", "User-Agent": "CHHHS-Research-Registry/1.0"}
    key = _api_key()
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(1, 4):
        try:
            with _open_request(request, timeout=timeout) as response:
                if response.status != 200:
                    return OpenAlexObservation("http_error", attempts=attempt, http_status=response.status)
                # A bounded response avoids unbounded memory consumption.
                body = response.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024:
                    return OpenAlexObservation("response_too_large", attempts=attempt)
                data = json.loads(body.decode("utf-8"))
                if not isinstance(data, dict):
                    return OpenAlexObservation("invalid_response", attempts=attempt)
                return OpenAlexObservation("success", data, attempt, 200, body)
        except urllib.error.HTTPError as error:
            code = error.code
            delay = _retry_delay(error.headers.get("Retry-After") if error.headers else None, attempt)
            error.close()
            if code == 404:
                return OpenAlexObservation("not_found", attempts=attempt, http_status=code)
            if code in (401, 403):
                return OpenAlexObservation("access_denied", attempts=attempt, http_status=code)
            if code not in (429, 500, 502, 503, 504):
                return OpenAlexObservation("http_error", attempts=attempt, http_status=code)
            status = "rate_limited" if code == 429 else "unavailable"
            if attempt == 3 or delay is None:
                return OpenAlexObservation(status, attempts=attempt, http_status=code)
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 3:
                return OpenAlexObservation("unavailable", attempts=attempt)
            delay = float(2 ** (attempt - 1))
        except (ValueError, UnicodeError):
            return OpenAlexObservation("invalid_response", attempts=attempt, raw_body=body)
        time.sleep(delay)
    raise AssertionError("Unreachable retry state")


def fetch_openalex_observation(doi: str, timeout: int = 10) -> OpenAlexObservation:
    """Return complete metadata or a distinct safe failure; never fabricate zero."""
    normalized = clean_doi(doi)
    if not normalized:
        return OpenAlexObservation("invalid_identifier")
    encoded = urllib.parse.quote("https://doi.org/" + normalized, safe="")
    observation = _request_observation(f"{OPENALEX_BASE_URL}/{encoded}", timeout)
    if observation.status == "success":
        returned = clean_doi(observation.payload.get("doi"))
        if not returned or returned.casefold() != normalized.casefold():
            return OpenAlexObservation("identity_mismatch", attempts=observation.attempts, http_status=200, raw_body=observation.raw_body)
    return observation


def fetch_openalex_work_by_doi(doi: str, email: str = DEFAULT_POLITE_EMAIL, timeout: int = 10) -> dict[str, Any] | None:
    """Compatibility wrapper; use observation API when failure status is required."""
    observation = fetch_openalex_observation(doi, timeout)
    if observation.status not in ("success", "not_found", "invalid_identifier"):
        logger.warning("OpenAlex result: %s (attempts=%d)", observation.status, observation.attempts)
    return observation.payload


def fetch_openalex_batch(dois: list[str], email: str = DEFAULT_POLITE_EMAIL, timeout: int = 15) -> dict[str, dict[str, Any]]:
    """Preserve the legacy mapping interface; reject partial or foreign batches."""
    cleaned = [clean_doi(d) for d in dois]
    if not cleaned or any(d is None for d in cleaned) or len(cleaned) > 50:
        return {}
    requested = {d.casefold() for d in cleaned}
    filter_value = "|".join("https://doi.org/" + d for d in cleaned)
    observation = _request_observation(f"{OPENALEX_BASE_URL}?" + urllib.parse.urlencode(
        {"filter": "doi:" + filter_value, "per_page": 50}), timeout)
    if observation.status != "success":
        logger.warning("OpenAlex batch result: %s", observation.status)
        return {}
    data = observation.payload
    rows = data.get("results")
    meta = data.get("meta", {})
    if not isinstance(rows, list) or not isinstance(meta, dict) or len(rows) > 50 or meta.get("count", len(rows)) != len(rows):
        logger.warning("OpenAlex batch result: incomplete_response")
        return {}
    result = {}
    try:
        for item in rows:
            doi = clean_doi(item.get("doi")) if isinstance(item, dict) else None
            if not doi or doi.casefold() not in requested or doi.casefold() in result:
                raise ValueError("identity")
            result[doi.casefold()] = extract_openalex_metrics(item)
    except (ValueError, TypeError, AttributeError):
        logger.warning("OpenAlex batch result: invalid_response")
        return {}
    return {d: result[d.casefold()] for d in cleaned if d.casefold() in result}


def extract_openalex_metrics(raw_data: dict[str, Any] | None) -> dict[str, Any]:
    """Extract standard registry enrichment fields from raw OpenAlex payload."""
    if not raw_data or not isinstance(raw_data, dict):
        return {
            "OpenAlexID": None,
            "CitationCount_OpenAlex": None,
            "OpenAccessStatus": None,
            "OAUrl": None,
            "FunderNames": None,
            "GrantIDs": None,
            "MeSHHeadings": None,
            "AuthorKeywords": None,
            "AffiliationsRaw": None,
            "AffiliationHierarchy": None,
        }

    oa_id = raw_data.get("id")
    citations = raw_data.get("cited_by_count")

    oa_info = raw_data.get("open_access", {})
    oa_status = oa_info.get("oa_status")
    if oa_status:
        oa_status = oa_status.capitalize()
    oa_url = oa_info.get("oa_url")

    # Grants & Funders
    grants = raw_data.get("grants", [])
    funder_names = []
    grant_ids = []
    for g in grants:
        if isinstance(g, dict):
            fn = g.get("funder_display_name") or g.get("funder")
            if fn and fn not in funder_names:
                funder_names.append(fn)
            gid = g.get("award_id")
            if gid and gid not in grant_ids:
                grant_ids.append(gid)

    # MeSH
    mesh = raw_data.get("mesh", [])
    mesh_headings = [m.get("descriptor_name") for m in mesh if isinstance(m, dict) and m.get("descriptor_name")]

    # Keywords
    keywords = raw_data.get("keywords", [])
    kw_list = [k.get("keyword") for k in keywords if isinstance(k, dict) and k.get("keyword")]

    # Affiliations
    authorships = raw_data.get("authorships", [])
    raw_affils = []
    hierarchies = []
    for auth in authorships:
        if isinstance(auth, dict):
            for inst in auth.get("institutions", []):
                dn = inst.get("display_name")
                if dn and dn not in raw_affils:
                    raw_affils.append(dn)
                ror = inst.get("ror")
                country = inst.get("country_code")
                if dn:
                    hierarchies.append(f"{dn} [ROR: {ror or 'N/A'}, Country: {country or 'N/A'}]")

    # Field of Research / Topic
    primary_topic = raw_data.get("primary_topic") or {}
    field_name = (primary_topic.get("field") or {}).get("display_name")
    topic_name = primary_topic.get("display_name")
    for_val = field_name or topic_name

    return {
        "OpenAlexID": oa_id,
        "CitationCount_OpenAlex": int(citations) if citations is not None else None,
        "OpenAccessStatus": oa_status,
        "OAUrl": oa_url,
        "FunderNames": "; ".join(funder_names) if funder_names else None,
        "GrantIDs": "; ".join(grant_ids) if grant_ids else None,
        "MeSHHeadings": "; ".join(mesh_headings[:15]) if mesh_headings else None,
        "AuthorKeywords": "; ".join(kw_list[:10]) if kw_list else None,
        "AffiliationsRaw": "; ".join(raw_affils) if raw_affils else None,
        "AffiliationHierarchy": "; ".join(hierarchies[:5]) if hierarchies else None,
        "FieldOfResearch": for_val,
    }


def enrich_record_with_openalex(record: dict[str, Any], email: str = DEFAULT_POLITE_EMAIL) -> dict[str, Any]:
    """Enrich a publication dictionary in-place with OpenAlex metrics."""
    doi = record.get("DOI")
    if not doi:
        return record

    observation = fetch_openalex_observation(doi)
    record["OpenAlexAttemptStatus"] = observation.status
    if observation.status == "success":
        try:
            metrics = extract_openalex_metrics(observation.payload)
        except (ValueError, TypeError, AttributeError):
            record["OpenAlexAttemptStatus"] = "invalid_response"
            return record
        for k, v in metrics.items():
            if v is not None:
                record[k] = v
        record["CitationMetricsObservedUTC"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return record
