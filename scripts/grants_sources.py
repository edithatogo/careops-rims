"""Validate the reviewed, source-only grants catalogue.

The catalogue records proposed intake routes and evidence state. It never
claims that a page is a working feed merely because an official URL exists.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REQUIRED_SOURCE_IDS = {
    "nhmrc", "mrff", "arc", "queensland-health", "emf-queensland",
    "advance-queensland", "fnqhf",
}
ALLOWED_INTAKE = {"rss", "atom", "api", "reviewed_import", "manual_review"}
ALLOWED_HEALTH = {"unverified", "research_only", "reviewed_import", "verified_sample"}
CATALOGUE_TIMEZONE = ZoneInfo("Australia/Brisbane")
OPTIONAL_TEXT_FIELDS = ("record_kind", "sample_fixture")


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _has_surrounding_whitespace(value: Any) -> bool:
    return isinstance(value, str) and value != value.strip()


def load_catalogue(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("grants source catalogue must be a list")
    seen: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("each source catalogue row must be an object")
        raw_source_id = row.get("source_id")
        if not isinstance(raw_source_id, str):
            raise ValueError("source_id must be a non-empty string")
        source_id = raw_source_id.strip()
        if not source_id or source_id in seen:
            raise ValueError(f"duplicate or missing source_id: {source_id!r}")
        if source_id != raw_source_id:
            raise ValueError(f"source {source_id!r} must not have surrounding whitespace")
        seen.add(source_id)
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            raise ValueError(f"source {source_id!r} needs title and authority_url")
        if _has_surrounding_whitespace(row.get("authority_url")):
            raise ValueError(f"source {source_id!r} authority_url must not have surrounding whitespace")
        if not _valid_http_url(row.get("authority_url")):
            raise ValueError(f"source {source_id!r} needs a valid authority_url")
        if row.get("intake") not in ALLOWED_INTAKE:
            raise ValueError(f"source {source_id!r} has unsupported intake")
        if row.get("health_status") not in ALLOWED_HEALTH:
            raise ValueError(f"source {source_id!r} has unsupported health_status")
        for field in OPTIONAL_TEXT_FIELDS:
            value = row.get(field)
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
            ):
                raise ValueError(f"source {source_id!r} {field} must be a non-empty string or null")
        if "api_url" in row and row.get("api_url") is not None and not isinstance(row.get("api_url"), str):
            raise ValueError(f"source {source_id!r} api_url must be a string or null")
        if "api_url" in row and _has_surrounding_whitespace(row.get("api_url")):
            raise ValueError(f"source {source_id!r} api_url must not have surrounding whitespace")
        if row.get("intake") == "api":
            if not _valid_http_url(row.get("api_url")):
                raise ValueError(f"source {source_id!r} with api intake needs a valid api_url")
        for field in ("eligibility_scope", "format", "access", "coverage", "last_verified"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"source {source_id!r} needs {field}")
        try:
            verified = date.fromisoformat(row["last_verified"])
        except ValueError:
            raise ValueError(f"source {source_id!r} has an invalid last_verified date") from None
        if verified > datetime.now(CATALOGUE_TIMEZONE).date():
            raise ValueError(f"source {source_id!r} has a future last_verified date")
    missing = REQUIRED_SOURCE_IDS - seen
    if missing:
        raise ValueError(f"required sources missing: {sorted(missing)}")
    return payload


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("catalogue", type=Path)
    args = parser.parse_args()
    rows = load_catalogue(args.catalogue)
    print(f"validated {len(rows)} grant source catalogue rows")
