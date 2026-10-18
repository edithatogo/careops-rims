"""Fail-closed importer for human-reviewed grants source observations.

This is the fallback for authority pages that do not expose a permitted
RSS/Atom/API route. It never treats a discovered HTML row as accepted merely
because it has a title; a reviewer must provide the source identity, row URL,
observation timestamp and explicit ``Reviewed`` status.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

try:
    from .grants_registry import normalize_opportunity
except ImportError:  # direct script execution with scripts/ on sys.path
    from grants_registry import normalize_opportunity


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


_OPTIONAL_STRING_FIELDS = (
    "Funder", "Description", "Geography", "Amount", "Deadline", "Status",
    "Contact", "CHHHSRelevance",
)


def review_errors(row: dict[str, Any], *, expected_source: str | None = None) -> list[str]:
    """Return all admission errors without silently repairing reviewer input."""
    errors: list[str] = []
    if not isinstance(row, dict):
        return ["row_not_object"]
    source_value = row.get("Source")
    source = source_value.strip() if isinstance(source_value, str) else ""
    if source_value is not None and not isinstance(source_value, str):
        errors.append("invalid_Source")
    elif isinstance(source_value, str) and source_value != source_value.strip():
        errors.append("whitespace_Source")
    if expected_source and source != expected_source:
        errors.append("source_mismatch")
    for field in _OPTIONAL_STRING_FIELDS:
        if field in row and row[field] is not None and not isinstance(row[field], str):
            errors.append(f"invalid_{field}")
    for field in ("Source", "Title", "RetrievedUTC", "Eligibility"):
        value = row.get(field)
        if not isinstance(value, str):
            errors.append(f"invalid_{field}")
        elif not value.strip():
            errors.append(f"missing_{field}")
    opportunity_url = row.get("URL")
    row_url = row.get("SourceRowURL")
    if not _valid_http_url(opportunity_url):
        errors.append("invalid_URL")
    if not _valid_http_url(row_url):
        errors.append("invalid_SourceRowURL")
    elif isinstance(opportunity_url, str) and row_url == opportunity_url:
        errors.append("SourceRowURL_not_distinct")
    review_status = row.get("ReviewStatus")
    if not isinstance(review_status, str):
        errors.append("invalid_ReviewStatus")
    elif review_status != review_status.strip():
        errors.append("whitespace_ReviewStatus")
    elif review_status.strip().casefold() != "reviewed":
        errors.append("ReviewStatus_not_Reviewed")
    notes = row.get("ReviewNotes")
    if not isinstance(notes, str):
        errors.append("invalid_ReviewNotes")
    elif not notes.strip():
        errors.append("missing_ReviewNotes")
    source_id = row.get("SourceID", "")
    round_id = row.get("RoundID", "")
    if not isinstance(source_id, str) or not isinstance(round_id, str):
        errors.append("invalid_SourceID_or_RoundID")
    elif not (source_id.strip() or round_id.strip()):
        errors.append("missing_SourceID_or_RoundID")
    else:
        if source_id != source_id.strip():
            errors.append("whitespace_SourceID")
        if round_id != round_id.strip():
            errors.append("whitespace_RoundID")
    return errors


def import_reviewed_rows(
    rows: Iterable[dict[str, Any]],
    *,
    expected_source: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize reviewed rows or reject the complete batch fail-closed."""
    materialized = list(rows)
    failures: list[tuple[int, list[str]]] = []
    result: list[dict[str, Any]] = []
    for index, row in enumerate(materialized):
        if not isinstance(row, dict):
            failures.append((index, ["row_not_object"]))
            continue
        errors = review_errors(row, expected_source=expected_source)
        if errors:
            failures.append((index, errors))
            continue
        normalized = normalize_opportunity(row, retrieved_at=row["RetrievedUTC"])
        normalized["SourceRowURL"] = row["SourceRowURL"]
        if normalized["RetrievedTimestampStatus"] != "valid":
            failures.append((index, ["RetrievedUTC_not_timezone_aware"]))
            continue
        result.append(normalized)
    if failures:
        detail = "; ".join(f"row {index}: {','.join(errors)}" for index, errors in failures)
        raise ValueError(f"reviewed import rejected: {detail}")
    if not result:
        raise ValueError("reviewed import rejected: empty batch")
    keys = [row["OpportunityKey"] for row in result]
    if len(keys) != len(set(keys)):
        raise ValueError("reviewed import rejected: duplicate OpportunityKey")
    return result


def load_reviewed_import(path: str | Path, *, expected_source: str | None = None) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("reviewed import must be a list or an object with rows")
    return import_reviewed_rows(rows, expected_source=expected_source)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source")
    args = parser.parse_args()
    records = load_reviewed_import(args.path, expected_source=args.source)
    print(json.dumps({"accepted": len(records), "records": records}, indent=2))
