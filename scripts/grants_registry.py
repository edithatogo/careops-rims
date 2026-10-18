"""Canonical, review-gated grants and funding opportunities registry.

The module accepts already-collected RSS/Atom or API-shaped dictionaries. It
does not fetch external sites, submit applications, or infer eligibility.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_url(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(value).casefold())


def stable_key(record: dict[str, Any]) -> str:
    source = _text(record.get("Source")) or "unknown"
    identifier = _text(record.get("SourceID") or record.get("ExternalID"))
    if identifier:
        basis = f"{source}:{identifier.casefold()}"
    elif normalize_url(record.get("URL")):
        basis = f"url:{normalize_url(record['URL'])}"
    else:
        basis = f"title:{normalize_title(record.get('Title'))}|funder:{normalize_title(record.get('Funder'))}"
    if record.get('RoundID'):
        basis += '|round:' + _text(record['RoundID'])
    return "GRANT:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _date(value: Any) -> tuple[str | None, str]:
    raw = _text(value)
    if not raw:
        return None, "unknown"
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", raw)
    if not match:
        return None, "unknown"
    year, month, day = match.groups()
    try:
        date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        return None, 'unknown'
    if month and day:
        return f"{year}-{month}-{day}", "day"
    if month:
        return f"{year}-{month}", "month"
    return year, "year"


def _retrieved_utc(value: Any) -> tuple[str, str]:
    """Validate an observation timestamp without silently assuming a timezone."""
    raw = _text(value)
    if not raw:
        return datetime.now(timezone.utc).isoformat(), "generated"
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw, "invalid"
    if parsed.tzinfo is None:
        return raw, "missing_timezone"
    return parsed.astimezone(timezone.utc).isoformat(), "valid"


def _timestamp_sort_key(value: Any) -> datetime:
    candidate = _text(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def normalize_opportunity(record: dict[str, Any], retrieved_at: str | None = None) -> dict[str, Any]:
    """Normalize RSS/Atom/API-shaped records without inventing missing values."""
    if not isinstance(record, dict):
        raise ValueError("opportunity record must be an object")
    string_fields = (
        "Source", "SourceID", "ExternalID", "Title", "title", "URL", "Link", "link",
        "Funder", "Organization", "funder", "RoundID", "Deadline", "ClosingDate", "deadline",
        "Status", "Description", "Summary", "summary", "Eligibility", "Geography", "Contact",
        "CHHHSRelevance", "SourceRowURL", "ReviewStatus", "ReviewNotes", "RetrievedUTC",
    )
    for field in string_fields:
        if field in record and record[field] is not None and not isinstance(record[field], str):
            raise ValueError(f"opportunity field {field} must be a string")
    amount = record.get("Amount")
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (str, int, float))):
        raise ValueError("opportunity field Amount must be scalar text/number")
    record = dict(record)
    record['Title'] = record.get('Title') or record.get('title') or ''
    record['URL'] = record.get('URL') or record.get('Link') or record.get('link') or ''
    record['Funder'] = record.get('Funder') or record.get('Organization') or record.get('funder') or ''
    deadline, precision = _date(record.get("Deadline") or record.get("ClosingDate") or record.get("deadline"))
    retrieved, retrieved_status = _retrieved_utc(retrieved_at or record.get("RetrievedUTC"))
    result = {
        "OpportunityKey": stable_key(record),
        "Title": _text(record.get("Title") or record.get("title")),
        "Funder": _text(record.get("Funder") or record.get("Organization") or record.get("funder")),
        "Source": _text(record.get("Source")) or "unknown",
        "SourceID": _text(record.get("SourceID") or record.get("ExternalID")),
        "RoundID": _text(record.get('RoundID')),
        "URL": normalize_url(record.get("URL") or record.get("Link") or record.get("link")),
        "SourceRowURL": normalize_url(record.get("SourceRowURL")),
        "Description": _text(record.get("Description") or record.get("Summary") or record.get("summary")),
        "Eligibility": _text(record.get("Eligibility")),
        "Geography": _text(record.get("Geography")),
        "Amount": _text(record.get("Amount")),
        "Deadline": deadline,
        "DeadlineRaw": _text(record.get("Deadline") or record.get("ClosingDate") or record.get("deadline")),
        "DeadlinePrecision": precision,
        "Status": _text(record.get("Status")) or "Unknown",
        "Contact": _text(record.get("Contact")),
        "CHHHSRelevance": _text(record.get("CHHHSRelevance")) or "Unknown",
        "ReviewStatus": _text(record.get("ReviewStatus")) or "Needs Review",
        "ReviewNotes": _text(record.get("ReviewNotes")),
        "RetrievedUTC": retrieved,
        "RetrievedTimestampStatus": retrieved_status,
        "EvidenceHash": hashlib.sha256(repr(sorted(record.items())).encode("utf-8")).hexdigest(),
    }
    if not result["Title"] or not result["URL"] or retrieved_status != "valid":
        result["ReviewStatus"] = "Needs Review"
    return result


def merge_observations(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge exact stable keys while retaining source-specific observations."""
    grouped: dict[str, dict[str, Any]] = {}
    for raw in records:
        normalized = normalize_opportunity(raw, raw.get("RetrievedUTC"))
        key = normalized["OpportunityKey"]
        if key not in grouped:
            grouped[key] = {**normalized, "SourceObservations": []}
        elif _timestamp_sort_key(normalized["RetrievedUTC"]) >= _timestamp_sort_key(grouped[key]["RetrievedUTC"]):
            prior = grouped[key]
            preserved_review = prior.get("ReviewStatus") not in (None, "", "Needs Review")
            grouped[key] = {
                **normalized,
                "ReviewStatus": prior.get("ReviewStatus") if preserved_review else normalized["ReviewStatus"],
                "ReviewNotes": prior.get("ReviewNotes") if preserved_review else normalized["ReviewNotes"],
                "SourceObservations": prior["SourceObservations"],
            }
        grouped[key]["SourceObservations"].append({
            "Source": normalized["Source"], "SourceID": normalized["SourceID"],
            "URL": normalized["URL"], "RetrievedUTC": normalized["RetrievedUTC"],
            "EvidenceHash": normalized["EvidenceHash"],
            "Snapshot": dict(normalized),
        })
        if grouped[key]["Title"] == "" and normalized["Title"]:
            grouped[key]["Title"] = normalized["Title"]
    return sorted(grouped.values(), key=lambda item: (item["Deadline"] or "9999", item["Title"].casefold()))


def sharepoint_field_map(record: dict[str, Any]) -> dict[str, Any]:
    """Map the canonical record to stable display names for a future list."""
    return {field: record.get(field) for field in (
        "OpportunityKey", "Title", "Funder", "Source", "SourceID", "RoundID", "URL", "SourceRowURL", "Description",
        "Eligibility", "Geography", "Amount", "Deadline", "DeadlineRaw", "DeadlinePrecision",
        "Status", "Contact", "CHHHSRelevance", "ReviewStatus", "ReviewNotes", "RetrievedUTC",
        "RetrievedTimestampStatus", "EvidenceHash",
    )}
