"""Render a source-preserving DoRA activity registry for RIMS ingestion."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from collect_pubmed import canonical_json
from dora_activity import IDENTITY_FIELD, SOURCE_FIELDS, validate_records
from export_publication_register import safe_cell

PROVENANCE_FIELDS = [
    "DORAActivityKey",
    "DORARecordID",
    "DORAResourceID",
    "DORAResourceName",
    "DORAResourceLastModified",
    "DORAObservedUTC",
    "DORASourceURL",
]
EXPORT_FIELDS = PROVENANCE_FIELDS + SOURCE_FIELDS


def _required_scalar_text(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"DoRA activity {label} must be a non-empty string")
    return value.strip()


def _required_http_url(value: Any, label: str) -> str:
    text = _required_scalar_text(value, label)
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"DoRA activity {label} must be an HTTP(S) URL")
    return text


def _required_timestamp(value: Any) -> str:
    text = _required_scalar_text(value, "observation time")
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("DoRA activity observation time must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("DoRA activity observation time must include a timezone")
    return text


def _verify_optional_hash(envelope: dict[str, Any], field: str, expected: str) -> None:
    supplied = envelope.get(field)
    if supplied is None:
        return
    if not isinstance(supplied, str) or supplied != expected:
        raise ValueError(f"DoRA activity {field} does not match the records")


def activity_key(resource_id: str, record: dict[str, Any]) -> str:
    resource_id = _required_scalar_text(resource_id, "resource id")
    source_id = record.get(IDENTITY_FIELD)
    if isinstance(source_id, bool) or not isinstance(source_id, (int, str)) or not str(source_id).strip():
        raise ValueError("source _id is required for a DORA activity key")
    record_id = str(source_id).strip()
    return f"dora-activity:{resource_id}:{record_id}"


def build_rows(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    if envelope.get("schema_version") != "dora-activity-v1":
        raise ValueError("Unexpected DoRA activity receipt schema")
    source_payload = envelope.get("source_payload")
    if not isinstance(source_payload, dict):
        raise ValueError("DoRA activity source provenance is required")
    resource = source_payload.get("resource")
    if not isinstance(resource, dict):
        raise ValueError("DoRA activity resource provenance is required")
    records = envelope.get("records")
    if not isinstance(records, list):
        raise ValueError("DoRA activity records are required")
    expected_count = envelope.get("expected_count")
    retrieved_count = envelope.get("retrieved_count")
    if type(expected_count) is not int or expected_count < 0:
        raise ValueError("DoRA activity expected count is invalid")
    if type(retrieved_count) is not int or retrieved_count < 0:
        raise ValueError("DoRA activity retrieved count is invalid")
    if expected_count != retrieved_count:
        raise ValueError("DoRA activity expected and retrieved counts do not reconcile")
    validate_records(records, retrieved_count)
    records_bytes = canonical_json(records).encode("utf-8")
    _verify_optional_hash(envelope, "records_sha256", hashlib.sha256(records_bytes).hexdigest())
    record_id_bytes = canonical_json(sorted(str(record[IDENTITY_FIELD]).strip() for record in records)).encode("utf-8")
    _verify_optional_hash(envelope, "record_id_sha256", hashlib.sha256(record_id_bytes).hexdigest())
    resource_id = _required_scalar_text(resource.get("id"), "resource id")
    resource_url = _required_http_url(resource.get("url"), "resource URL")
    observed_at = _required_timestamp(envelope.get("observed_at"))
    rows = []
    for record in records:
        row = {name: record.get(name) for name in SOURCE_FIELDS}
        row.update({
            "DORAActivityKey": activity_key(resource_id, record),
            "DORARecordID": record.get("_id"),
            "DORAResourceID": resource_id,
            "DORAResourceName": resource.get("name"),
            "DORAResourceLastModified": resource.get("last_modified"),
            "DORAObservedUTC": observed_at,
            "DORASourceURL": resource_url,
        })
        rows.append(row)
    return rows


def export_envelope(envelope: dict[str, Any], output: Path) -> Path:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    rows = build_rows(envelope)
    output.mkdir(parents=True)
    with (output / "dora-activity-registry.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        writer.writerows({name: safe_cell(row.get(name)) for name in EXPORT_FIELDS} for row in rows)
    (output / "dora-activity-registry.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def export(envelope_path: Path, output: Path) -> Path:
    return export_envelope(json.loads(envelope_path.read_text(encoding="utf-8")), output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envelope", type=Path, help="Collector output containing receipt.json and records.json")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receipt = json.loads((args.envelope / "receipt.json").read_text(encoding="utf-8"))
    receipt["records"] = json.loads((args.envelope / "records.json").read_text(encoding="utf-8"))
    print(export_envelope(receipt, args.output))
