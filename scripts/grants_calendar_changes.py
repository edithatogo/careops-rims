"""Fail-closed local projection of funding-calendar revisions.

This creates change records only from explicit before/after values.  It does
not write SharePoint, create calendar events, or send notifications.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any
from urllib.parse import urlsplit


def _required_string(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")
    if value != value.strip():
        raise ValueError(f"{field} must not have surrounding whitespace")
    return value


def _optional_date(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date string") from exc
    return value


def _http_url(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("SourceURL must be an HTTP(S) URL")
    if value != value.strip():
        raise ValueError("SourceURL must not have surrounding whitespace")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("SourceURL must be an HTTP(S) URL")
    return value


def change_record(previous: dict[str, Any] | None, current: dict[str, Any], *, observed_utc: str) -> dict[str, Any] | None:
    """Return one revision record, or None when the explicit values are unchanged."""
    if previous is not None and not isinstance(previous, dict):
        raise ValueError("previous calendar row must be an object")
    if not isinstance(current, dict):
        raise ValueError("current calendar row must be an object")
    deadline_key = _required_string(current, "DeadlineKey")
    opportunity_key = _required_string(current, "OpportunityKey")
    revision = _required_string(current, "Revision")
    change_type = "created" if previous is None else "updated"
    previous_revision = None
    previous_date = None
    previous_cancelled = None
    if previous is not None:
        if _required_string(previous, "DeadlineKey") != deadline_key or _required_string(previous, "OpportunityKey") != opportunity_key:
            raise ValueError("previous and current calendar identities must match")
        previous_revision = _required_string(previous, "Revision")
        previous_date = _optional_date(previous.get("CalculatedDate"), "PreviousDate")
        previous_cancelled = previous.get("Cancelled")
        if not isinstance(previous_cancelled, bool):
            raise ValueError("PreviousCancelled must be boolean")
        if previous_revision == revision and previous_date == _optional_date(current.get("CalculatedDate"), "CalculatedDate") and previous_cancelled == current.get("Cancelled"):
            return None
        if current.get("Cancelled") is True and previous_cancelled is False:
            change_type = "cancelled"
        elif current.get("Cancelled") is False and previous_cancelled is True:
            change_type = "reopened"
    cancelled = current.get("Cancelled")
    if not isinstance(cancelled, bool):
        raise ValueError("Cancelled must be boolean")
    calculated_date = _optional_date(current.get("CalculatedDate"), "CalculatedDate")
    if not isinstance(observed_utc, str):
        raise ValueError("ObservedUTC must be an ISO timestamp")
    try:
        observed = dt.datetime.fromisoformat(observed_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("ObservedUTC must be an ISO timestamp") from exc
    if observed.tzinfo is None:
        raise ValueError("ObservedUTC must include a timezone")
    source_url = _http_url(current["SourceURL"]) if current.get("SourceURL") is not None else None
    review_status = _required_string(current, "ReviewStatus")
    basis = "|".join((deadline_key, previous_revision or "", revision, change_type))
    return {
        "ChangeKey": hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32],
        "DeadlineKey": deadline_key,
        "OpportunityKey": opportunity_key,
        "ChangeType": change_type,
        "PreviousRevision": previous_revision,
        "Revision": revision,
        "PreviousDate": previous_date,
        "CalculatedDate": calculated_date,
        "PreviousCancelled": previous_cancelled,
        "Cancelled": cancelled,
        "SourceURL": source_url,
        "ObservedUTC": observed_utc,
        "ReviewStatus": review_status,
    }
