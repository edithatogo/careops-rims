"""Read-only adapter for the ARC NCGP public grants JSON API.

The endpoint contains awarded/project records, not an open-opportunity
calendar. Keep its output typed as ``Award`` so it can enrich relationship
review without entering the opportunity upsert path.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
from typing import Any, Callable
from urllib.parse import urlsplit

API_BASE = "https://dataportal.arc.gov.au/NCGP/API/grants"
MAX_PAGE_SIZE = 1000


def _request_url(page_number: int, page_size: int) -> str:
    if page_number < 1 or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError("page_number must be positive and page_size must be 1..1000")
    return API_BASE + "?" + urllib.parse.urlencode(
        {"page[number]": page_number, "page[size]": page_size}
    )


def _text(value: Any, *, field: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"ARC API {field} must be a string")
    return value.strip()


def _strict_text(value: Any, *, field: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"ARC API {field} must be a string")
    if value != value.strip():
        raise ValueError(f"ARC API {field} must not have surrounding whitespace")
    return value


def _amount(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("ARC API current-funding-amount must be scalar")
    return str(value).strip()


def _valid_http_url(value: str) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _read_json(url: str, opener: Callable[..., Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "CHHHS-RIMS-grants-arc/0.1"},
        method="GET",
    )
    with opener(request, timeout=20) as response:
        if int(response.getcode() or 0) != 200:
            raise ValueError(f"ARC API returned HTTP {response.getcode()}")
        content_type = str(response.headers.get("Content-Type", ""))
        if "json" not in content_type.casefold():
            raise ValueError("ARC API response is not JSON")
        payload = json.loads(response.read(2_000_001))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("ARC API payload must contain a data list")
    return payload


def parse_award_page(payload: dict[str, Any], *, retrieved_at: str) -> list[dict[str, Any]]:
    """Convert one API page to typed award observations without opportunity promotion."""
    if not retrieved_at or dt.datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    records: list[dict[str, Any]] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise ValueError("ARC API data item must be an object")
        attrs = item.get("attributes")
        if not isinstance(attrs, dict):
            raise ValueError("ARC API item must contain attributes")
        source_value = attrs.get("code") if attrs.get("code") not in (None, "") else item.get("id")
        source_id = _strict_text(source_value, field="award code/id")
        if not source_id:
            raise ValueError("ARC API award is missing code/id")
        links = item.get("links", {})
        if not isinstance(links, dict):
            raise ValueError("ARC API award links must be an object")
        link = _strict_text(links.get("self"), field="evidence URL")
        if not _valid_http_url(link):
            raise ValueError("ARC API award is missing an evidence URL")
        summary = _text(attrs.get("grant-summary"), field="grant-summary")
        scheme = _text(attrs.get("scheme-name"), field="scheme-name")
        amount = _amount(attrs.get("current-funding-amount"))
        status = _text(attrs.get("grant-status"), field="grant-status", default="Unknown") or "Unknown"
        records.append({
            "RecordKind": "Award",
            "Source": "arc",
            "SourceID": source_id,
            "Title": summary or scheme,
            "Funder": "Australian Research Council",
            "URL": link,
            "Description": summary,
            "Amount": amount,
            "Status": status,
            "RetrievedUTC": retrieved_at,
            "EvidenceHash": "",
        })
    return records


def fetch_award_page(*, page_number: int = 1, page_size: int = 1000,
                     retrieved_at: str | None = None,
                     opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    """Fetch one bounded ARC page and return typed awards plus pagination metadata."""
    observed = retrieved_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    url = _request_url(page_number, page_size)
    payload = _read_json(url, opener)
    return {
        "source": "arc",
        "record_kind": "awards_only",
        "api_url": url,
        "meta": payload.get("meta", {}),
        "records": parse_award_page(payload, retrieved_at=observed),
    }


if __name__ == "__main__":
    print(json.dumps(fetch_award_page(page_size=1), indent=2))
