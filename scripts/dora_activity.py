"""Collect and validate the current Queensland Open Data DoRA activity resource.

This is deliberately separate from the publication-oriented DoRA repository
harvest. A project/activity row is not a publication identity. The collector
keeps the source columns unchanged and writes provenance in its receipt so the
activity registry can be joined to publications or grants without silently
changing meaning.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collect_pubmed import atomic_json, canonical_json

PACKAGE_SHOW = "https://www.data.qld.gov.au/api/3/action/package_show"
DATASTORE_SEARCH = "https://www.data.qld.gov.au/api/3/action/datastore_search"
PACKAGE_NAME = "database-of-research-activity-dora"

# The current published activity resource. The resource selector still
# discovers this from package_show so a future replacement is not hard-coded.
SOURCE_FIELDS = [
    "Project ID",
    "Review Reference",
    "HREC (Ethics) Reference Number",
    "Full Project Title",
    "Short Project Title",
    "Project Description",
    "Clinical Trial (Yes/No)",
    "PI Name",
    "PI Email",
    "Contact Person Name",
    "Contact Person Email",
    "Site Name",
    "Sponsor Name",
    "Start Date",
    "Finish Date",
    "Disease Category",
    "Multi/Single site",
    "DORA Authority (Yes/No)",
    "DORA Consent (Yes/No)",
]
IDENTITY_FIELD = "_id"


def _json_request(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    request = Request(url + "?" + query, headers={"Accept": "application/json"})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("DoRA activity API returned an unsuccessful response")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("DoRA activity API result is not an object")
    return result


def _resource_sort_key(resource: dict[str, Any]) -> str:
    return str(resource.get("last_modified") or resource.get("created") or "")


def select_resource(package: dict[str, Any]) -> dict[str, Any]:
    resources = package.get("resources")
    if not isinstance(resources, list):
        raise ValueError("DoRA package has no resource list")
    candidates = [
        resource for resource in resources
        if isinstance(resource, dict)
        and resource.get("datastore_active") is True
        and str(resource.get("format", "")).upper() == "CSV"
    ]
    if not candidates:
        raise ValueError("DoRA package has no active CSV datastore resource")
    if any(
        not isinstance(resource.get("id"), str) or not resource["id"].strip()
        for resource in candidates
    ):
        raise ValueError("DoRA active CSV datastore resource has an invalid id")
    return max(candidates, key=_resource_sort_key)


def validate_page(result: dict[str, Any], expected_fields: list[str] = SOURCE_FIELDS) -> tuple[list[dict[str, Any]], int]:
    fields = result.get("fields")
    records = result.get("records")
    if not isinstance(fields, list) or not isinstance(records, list):
        raise ValueError("DoRA activity page lacks fields or records")
    field_names = [field.get("id") for field in fields if isinstance(field, dict)]
    if field_names != ["_id", *expected_fields]:
        raise ValueError("DoRA activity schema drift: fields do not match the expected resource")
    total = result.get("total")
    if type(total) is not int or total < 0:
        raise ValueError("DoRA activity total is invalid")
    clean: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict) or set(record) != set(field_names):
            raise ValueError("DoRA activity record fields do not match the resource schema")
        clean.append({name: record.get(name) for name in field_names})
    return clean, total


def validate_records(records: list[dict[str, Any]], expected_count: int) -> None:
    if type(expected_count) is not int or expected_count < 0:
        raise ValueError("DoRA activity expected record count is invalid")
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError("DoRA activity record count does not reconcile")
    keys = []
    for record in records:
        if set(record) != {"_id", *SOURCE_FIELDS}:
            raise ValueError("DoRA activity record has unexpected or missing fields")
        key = record.get(IDENTITY_FIELD)
        if isinstance(key, bool) or not isinstance(key, (int, str)) or not str(key).strip():
            raise ValueError("DoRA activity record has no source _id")
        if isinstance(key, str) and key != key.strip():
            raise ValueError("DoRA activity source _id must not have surrounding whitespace")
        keys.append(str(key).strip())
    if len(keys) != len(set(keys)):
        raise ValueError("DoRA activity source _ids are not unique")


def collect(
    output: Path,
    fetcher: Callable[[str, dict[str, Any]], dict[str, Any]] = _json_request,
    package_name: str = PACKAGE_NAME,
    page_size: int = 1000,
) -> Path:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    package = fetcher(PACKAGE_SHOW, {"id": package_name})
    if package.get("name") != package_name:
        raise ValueError("DoRA package identity mismatch")
    resource = select_resource(package)
    resource_id = resource["id"]
    records: list[dict[str, Any]] = []
    total: int | None = None
    offset = 0
    while True:
        page = fetcher(DATASTORE_SEARCH, {"resource_id": resource_id, "limit": page_size, "offset": offset})
        page_records, page_total = validate_page(page)
        if total is None:
            total = page_total
        elif total != page_total:
            raise ValueError("DoRA activity total changed during traversal")
        records.extend(page_records)
        if not page_records:
            break
        offset += len(page_records)
        if offset >= total:
            break
    validate_records(records, total or 0)
    observed_at = dt.datetime.now(dt.timezone.utc).isoformat()
    source_payload = {
        "package_name": package_name,
        "package_id": package.get("id"),
        "package_title": package.get("title"),
        "dataset_metadata_modified": package.get("metadata_modified"),
        "resource": {key: resource.get(key) for key in (
            "id", "name", "format", "last_modified", "created", "url", "hash", "datastore_active")},
        "api": DATASTORE_SEARCH,
        "fields": ["_id", *SOURCE_FIELDS],
    }
    records_bytes = canonical_json(records).encode("utf-8")
    receipt = {
        "schema_version": "dora-activity-v1",
        "status": "succeeded",
        "source": "data.qld.gov.au",
        "source_payload": source_payload,
        "observed_at": observed_at,
        "expected_count": total or 0,
        "retrieved_count": len(records),
        "records_sha256": hashlib.sha256(records_bytes).hexdigest(),
        "record_id_sha256": hashlib.sha256(canonical_json(sorted(str(r[IDENTITY_FIELD]).strip() for r in records)).encode()).hexdigest(),
        "coverage_status": "latest_active_public_datastore_resource",
        "raw_source_fields_preserved": True,
    }
    output.mkdir(parents=True)
    atomic_json(output / "records.json", records)
    atomic_json(output / "receipt.json", receipt)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args()
    print(collect(args.output, page_size=args.page_size))
