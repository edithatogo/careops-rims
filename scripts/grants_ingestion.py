"""Offline-testable RSS/Atom and API-shaped grants ingestion helpers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Iterable
from urllib.parse import urlsplit

try:
    from .grants_registry import normalize_opportunity
except ImportError:  # direct script execution with scripts/ on sys.path
    from grants_registry import normalize_opportunity


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.casefold() for name in names}
    for child in element.iter():
        if child is element:
            continue
        if _local(child.tag) in wanted and (child.text or "").strip():
            return " ".join((child.text or "").split())
    return ""


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_emitted_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("ingestion record must be an object")
    if not isinstance(record.get("Title"), str) or not record["Title"].strip():
        raise ValueError("ingestion record missing title")
    if not _valid_http_url(record.get("URL")):
        raise ValueError("ingestion record requires an HTTP(S) URL")
    if not isinstance(record.get("OpportunityKey"), str) or not record["OpportunityKey"].strip():
        raise ValueError("ingestion record missing OpportunityKey")
    if record.get("RetrievedTimestampStatus") != "valid":
        raise ValueError("ingestion record requires timezone-aware retrieval")
    return record


def _validate_source_identity(value: Any, *, label: str = "feed source") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{label} must not have surrounding whitespace")
    return value


_STRING_INPUT_FIELDS = (
    "Title", "title", "URL", "Link", "link", "SourceID", "ExternalID",
    "Deadline", "ClosingDate", "Description", "Summary", "summary",
    "Funder", "Organization", "Eligibility", "RoundID",
)

_STRICT_INPUT_FIELDS = (
    "URL", "Link", "link", "SourceID", "ExternalID", "RoundID", "SourceRowURL",
)


def _validate_source_record_input(record: Any) -> dict[str, Any]:
    """Reject typed source fields before normalization can stringify them."""
    if not isinstance(record, dict):
        raise ValueError("ingestion source record must be an object")
    for field in _STRING_INPUT_FIELDS:
        if field in record and record[field] is not None and not isinstance(record[field], str):
            raise ValueError(f"ingestion source field {field} must be a string")
    for field in _STRICT_INPUT_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value != value.strip():
            raise ValueError(f"ingestion source field {field} must not have surrounding whitespace")
    return record


def _validate_unique_batch(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [record.get("OpportunityKey", "").strip() for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate OpportunityKey within source batch")
    return records


def parse_feed(xml_payload: str | bytes, *, source: str, retrieved_at: str) -> list[dict[str, Any]]:
    """Parse RSS/Atom entries while retaining raw deadline text for review."""
    source = _validate_source_identity(source)
    root = ET.fromstring(xml_payload)
    entries = [node for node in root.iter() if _local(node.tag) in {"item", "entry"}]
    if not entries:
        raise ValueError("feed contains no RSS items or Atom entries")
    result: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for entry in entries:
        link = _child_text(entry, "link", "url")
        if not link:
            for child in entry:
                if _local(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        source_id = _child_text(entry, "guid", "id", "identifier")
        if source_id:
            if source_id in seen_source_ids:
                raise ValueError(f"duplicate source identity: {source_id}")
            seen_source_ids.add(source_id)
        if not source_id and not link:
            raise ValueError("feed entry missing source identity")
        title = _child_text(entry, "title")
        if not title:
            raise ValueError("feed entry missing title")
        result.append(_validate_emitted_record(normalize_opportunity({
            "Source": source,
            "SourceID": source_id,
            "Title": title,
            "URL": link,
            "Description": _child_text(entry, "description", "summary", "content"),
            "Deadline": _child_text(entry, "deadline", "closingdate", "closing-date"),
            "RetrievedUTC": retrieved_at,
        }, retrieved_at=retrieved_at)))
    return _validate_unique_batch(result)


def ingest_batches(batches: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Ingest independent source batches; one bad source cannot erase others."""
    records: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    for batch in batches:
        if not isinstance(batch, dict):
            raise ValueError("grant source batch must be an object")
        source_value = batch.get("source")
        source = ""
        try:
            source = _validate_source_identity(source_value, label="source")
            if "xml" in batch:
                parsed = parse_feed(batch["xml"], source=source, retrieved_at=batch["retrieved_at"])
            else:
                parsed = _validate_unique_batch([
                    _validate_emitted_record(normalize_opportunity({**_validate_source_record_input(row), "Source": source}, retrieved_at=batch["retrieved_at"]))
                    for row in batch.get("records", [])
                ])
            records.extend(parsed)
            health.append({"source": source, "status": "succeeded", "count": len(parsed)})
        except (ET.ParseError, TypeError, ValueError, KeyError) as exc:
            health.append({"source": source, "status": "failed", "count": 0, "error": str(exc)})
    return {"records": records, "health": health, "accepted": bool(records) and all(item["status"] == "succeeded" for item in health)}
