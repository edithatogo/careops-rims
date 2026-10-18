"""Read-only, review-queue adapter for Queensland Health QGIP catalogue rows.

The QGIP dataset is an annual catalogue of assistance programs, not a live
opportunity feed. This adapter emits only explicitly open grant candidates,
keeps them in ``Needs Review``, and never writes to the accepted registry.
"""
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any, Callable

try:
    from scripts.grants_sources import DEFAULT_CATALOGUE, require_enabled_source
except ImportError:
    from grants_sources import DEFAULT_CATALOGUE, require_enabled_source

API_BASE = "https://www.data.qld.gov.au/api/3/action/"
RESOURCE_ID = "00000000-0000-4000-8000-0429f8720d4e"
PACKAGE_ID = "00000000-0000-4000-8000-3f8e83191b18"
INDEX_RESOURCE_ID = "00000000-0000-4000-8000-aecd9827bec5"
PACKAGE_NAME = "qh-queensland-government-investment-portal-qgip"
SOURCE_ID = "queensland-health-qgip-review-candidates-api"
PAGE_SIZE = 100
MAX_PAGES = 10
MAX_RESPONSE_BYTES = 2_000_000
CLASSIFICATION_SCHEMA_FIELDS = (
    "Service ID",
    "Status",
    "Assistance type1",
    "Assistance type2",
    "Assistance type3",
)


def _get_json(action: str, params: dict[str, Any], opener: Callable[..., Any],
              *, retained_responses: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    url = API_BASE + action + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "CHHHS-RIMS-qgip/0.1"}, method="GET"
    )
    with opener(request, timeout=20) as response:
        if int(response.getcode() or 0) != 200:
            raise ValueError(f"Queensland CKAN API returned HTTP {response.getcode()}")
        if "json" not in str(response.headers.get("Content-Type", "")).casefold():
            raise ValueError("Queensland CKAN response is not JSON")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Queensland CKAN response exceeds byte limit")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("result"), dict):
        raise ValueError("Queensland CKAN response is not a successful result object")
    if retained_responses is not None:
        # Preserve the complete successful HTTP body before selecting result,
        # rows or candidates. Hashes alone cannot recover omitted source fields.
        retained_responses.append({
            "request_url": url, "method": "GET", "status": 200,
            "content_type": str(response.headers.get("Content-Type", "")),
            "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "body_bytes": len(raw), "body_sha256": hashlib.sha256(raw).hexdigest(),
            "body_base64": base64.b64encode(raw).decode("ascii"),
        })
    return payload["result"]


def _aware(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("retrieved_at must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware ISO-8601")
    return parsed.astimezone(dt.timezone.utc)


def _source_date(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("QGIP resource last_modified is missing")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("QGIP resource last_modified is invalid") from exc
    # CKAN stores datetimes in UTC and can serialize last_modified without a
    # timezone suffix. Retain this interpretation explicitly in the receipt.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _is_grant(row: dict[str, Any]) -> bool:
    # Assistance slots are categorical; substring matching admits unrelated
    # terms such as "guarantee". Match a complete normalized value only.
    return any(isinstance(row.get(f"Assistance type{i}"), str)
               and row[f"Assistance type{i}"].strip().casefold() == "grant"
               for i in range(1, 4))


def validate_catalogue_pointer(index_result: dict[str, Any]) -> None:
    """Require the live Grants Finder index to map Queensland Health to QGIP."""
    if not isinstance(index_result, dict) or index_result.get("total_was_estimated") is not False:
        raise ValueError("Grants Finder index must provide an exact row count")
    records = index_result.get("records")
    total = index_result.get("total")
    if (not isinstance(total, int) or isinstance(total, bool) or not isinstance(records, list)
            or total != len(records)):
        raise ValueError("Grants Finder index page must contain its exact complete row set")
    qh_rows = [row for row in records if isinstance(row, dict) and row.get("Agency") == "QH"]
    if len(qh_rows) != 1 or qh_rows[0].get("Resource") != RESOURCE_ID:
        raise ValueError("Grants Finder Queensland Health resource mapping changed")


def _catalogue_pointer(index_result: dict[str, Any]) -> tuple[str, str]:
    """Return the validated agency-to-resource pointer from the exact index page."""
    validate_catalogue_pointer(index_result)
    row = next(row for row in index_result["records"]
               if isinstance(row, dict) and row.get("Agency") == "QH")
    return row["Agency"], row["Resource"]


def _package_pointer(package: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    """Validate the requested CKAN slug and its package/resource membership."""
    resources = package.get("resources")
    if (package.get("id") != PACKAGE_ID or package.get("name") != PACKAGE_NAME
            or package.get("license_id") != "CC-BY-3.0" or not isinstance(resources, list)):
        raise ValueError("Queensland Health QGIP package mapping changed")
    if any(not isinstance(resource, dict) or not isinstance(resource.get("id"), str)
           or not resource["id"].strip() for resource in resources):
        raise ValueError("Queensland Health QGIP package resource mapping is incomplete")
    resource_ids = tuple(sorted(resource["id"] for resource in resources))
    if resource_ids.count(RESOURCE_ID) != 1:
        raise ValueError("Queensland Health QGIP package resource mapping changed")
    return package["id"], package["name"], package["license_id"], resource_ids


def validate_catalogue_schema(info: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Require the expected source field; CKAN field metadata is not an ID contract."""
    fields = info.get("fields") if isinstance(info, dict) else None
    if not isinstance(fields, list) or not fields:
        raise ValueError("QGIP datastore schema is missing")
    schema: list[tuple[str, str]] = []
    for field in fields:
        if (not isinstance(field, dict) or not isinstance(field.get("id"), str)
                or not field["id"].strip() or not isinstance(field.get("type"), str)):
            raise ValueError("QGIP datastore schema has an invalid field")
        schema.append((field["id"], field["type"]))
    if len(set(name for name, _ in schema)) != len(schema):
        raise ValueError("QGIP datastore schema has duplicate fields")
    for field_id in CLASSIFICATION_SCHEMA_FIELDS:
        if schema.count((field_id, "text")) != 1:
            raise ValueError(f"QGIP datastore classification field is missing or changed: {field_id}")
    return tuple(schema)


def _candidate(row: dict[str, Any], *, retrieved_at: str, source_updated: dt.datetime,
               observed: dt.datetime) -> dict[str, Any]:
    source_id = row.get("Service ID")
    if (not isinstance(source_id, str) or not source_id
            or source_id != source_id.strip()):
        raise ValueError("QGIP Service ID must be non-empty unpadded text")
    title_parts = [row.get("Program title"), row.get("Sub-program title")]
    if any(value is not None and not isinstance(value, str) for value in title_parts):
        raise ValueError("QGIP titles must be text or null")
    title = " — ".join(value.strip() for value in title_parts if value and value.strip())
    if not title:
        raise ValueError("QGIP candidate title is missing")
    website = row.get("Website")
    if website is not None and not isinstance(website, str):
        raise ValueError("QGIP Website must be text or null")
    purpose = row.get("Purpose")
    if purpose is not None and not isinstance(purpose, str):
        raise ValueError("QGIP Purpose must be text or null")
    eligibility = row.get("Eligibility")
    if eligibility is not None and not isinstance(eligibility, str):
        raise ValueError("QGIP Eligibility must be text or null")
    close_date = row.get("Closing date (date format)")
    close_text = row.get("Closing date (text)")
    if any(value is not None and not isinstance(value, str)
           for value in (close_date, close_text)):
        raise ValueError("QGIP closing date must be text or null")
    # Validate both source fields before fallback. Using ``or`` first would
    # silently hide malformed falsey values (False, 0, or []) in either field.
    close_raw = close_date if isinstance(close_date, str) and close_date.strip() else close_text
    evidence = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    age_days = (observed - source_updated).days
    return {
        "RecordKind": "OpportunityCandidate",
        "Source": "qld-qgip",
        "SourceID": source_id,
        "Title": title,
        "Funder": "Queensland Health",
        "URL": website.strip() if website else "",
        # A dated catalogue status does not prove current availability.
        "Status": "Needs Review",
        "SourceStatus": row.get("Status"),
        "ClosingDateSource": close_raw.strip() if close_raw else None,
        "Purpose": purpose.strip() if purpose else "",
        "EligibilitySource": eligibility.strip() if eligibility else "",
        "ReviewStatus": "Needs Review",
        "ReviewNotes": "",
        "IdentityStatus": "CandidateUnproven",
        "FreshnessStatus": "Needs Review",
        "SourceUpdatedUTC": source_updated.isoformat().replace("+00:00", "Z"),
        "SourceAgeDays": age_days,
        "RetrievedUTC": retrieved_at,
        "EvidenceHash": hashlib.sha256(evidence).hexdigest(),
        # Reviewers can distinguish a CKAN row-ordinal rebuild from a change
        # to the programme itself without discarding the complete raw hash.
        "BusinessEvidenceHash": hashlib.sha256(json.dumps(
            {key: value for key, value in row.items() if key != "_id"},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }


def build_review_queue(*, package: dict[str, Any], resource: dict[str, Any], pages: list[dict[str, Any]],
                       retrieved_at: str) -> dict[str, Any]:
    """Validate a complete snapshot and return candidate rows plus diagnostics."""
    observed = _aware(retrieved_at)
    if package.get("id") != PACKAGE_ID or package.get("license_id") != "CC-BY-3.0":
        raise ValueError("QGIP package identity or expected licence does not match")
    if resource.get("id") != RESOURCE_ID or resource.get("package_id") != PACKAGE_ID:
        raise ValueError("QGIP resource is outside the verified package")
    updated = _source_date(resource.get("last_modified"))
    timestamp_basis = ("ckan_utc_naive" if dt.datetime.fromisoformat(
        resource["last_modified"].replace("Z", "+00:00")).tzinfo is None
        else "explicit_offset")
    if updated > observed:
        raise ValueError("QGIP resource update is later than snapshot retrieval")
    try:
        total = pages[0]["total"]
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("QGIP first page must provide an exact total") from exc
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError("QGIP first page must provide an exact integer total")
    if pages[0].get("total_was_estimated") is not False:
        raise ValueError("QGIP first page total must be explicitly exact")
    if total < 0 or len(pages) != max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) or len(pages) > MAX_PAGES:
        raise ValueError("QGIP snapshot page count does not cover the exact total")
    rows: list[dict[str, Any]] = []
    for page_number, page in enumerate(pages):
        if (page.get("total") != total or page.get("total_was_estimated") is not False
                or page.get("offset") != page_number * PAGE_SIZE):
            raise ValueError("QGIP snapshot has inconsistent total or page offset")
        records = page.get("records")
        if not isinstance(records, list):
            raise ValueError("QGIP page records must be a list")
        expected = min(PAGE_SIZE, max(0, total - page_number * PAGE_SIZE))
        if len(records) != expected:
            raise ValueError("QGIP page is incomplete")
        if any(not isinstance(record, dict) for record in records):
            raise ValueError("QGIP row must be an object")
        rows.extend(records)
    if len(rows) != total:
        raise ValueError("QGIP snapshot row count differs from exact total")
    ids = [row.get("Service ID") for row in rows]
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("QGIP snapshot contains missing Service ID")
    if any(value != value.strip() for value in ids):
        raise ValueError("QGIP snapshot contains padded Service ID")
    if len(set(ids)) != len(ids):
        raise ValueError("QGIP snapshot contains duplicate Service ID")
    # Digests support comparison; the complete unfiltered source is retained
    # separately below, before the secondary candidate-only projection.
    source_row_hashes = {
        row["Service ID"]: hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for row in rows
    }
    # CKAN's _id is a datastore row ordinal, not a program identity. Keep the
    # raw hashes above for complete-read integrity, but compare source content
    # separately so an ordinal-only rebuild is not reported as a program edit.
    business_row_hashes = {
        row["Service ID"]: hashlib.sha256(
            json.dumps({key: value for key, value in row.items() if key != "_id"},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for row in rows
    }
    candidates: list[dict[str, Any]] = []
    for row in rows:
        status = row.get("Status")
        if status is not None and not isinstance(status, str):
            raise ValueError("QGIP Status must be text or null")
        if isinstance(status, str) and status.strip().casefold() == "open" and _is_grant(row):
            candidates.append(_candidate(row, retrieved_at=retrieved_at, source_updated=updated, observed=observed))
    snapshot_material = {
        "resource_id": RESOURCE_ID,
        "package_id": PACKAGE_ID,
        "source_updated_utc": updated.isoformat().replace("+00:00", "Z"),
        "source_total": total,
        "rows": rows,
    }
    snapshot_bytes = json.dumps(snapshot_material, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")
    return {
        "source": "qld-qgip",
        "package_id": PACKAGE_ID,
        "resource_id": RESOURCE_ID,
        "record_kind": "review_candidates_only",
        "accepted": False,
        "retrieved_utc": observed.isoformat().replace("+00:00", "Z"),
        "source_total": total,
        "source_updated_utc": updated.isoformat().replace("+00:00", "Z"),
        "source_timestamp_basis": timestamp_basis,
        "source_age_days": (observed - updated).days,
        "snapshot_complete": True,
        "snapshot_hash": hashlib.sha256(snapshot_bytes).hexdigest(),
        "source_row_hashes": source_row_hashes,
        "business_row_hashes": business_row_hashes,
        "raw_source": copy.deepcopy({"package": package, "resource": resource,
                                      "pages": pages}),
        "records": candidates,
    }


def compare_snapshots(prior: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare complete snapshots without overstating Service ID semantics.

    Same-calendar-day equality is only a repeated digest check. A later-date
    comparison can establish that observed rows persisted or changed between
    observations, but it still cannot prove that Service ID is immutable or
    that the source publishes authoritative lifecycle events.
    """
    for label, snapshot in (("prior", prior), ("current", current)):
        if (not isinstance(snapshot, dict) or snapshot.get("source") != "qld-qgip"
                or snapshot.get("package_id") != PACKAGE_ID
                or snapshot.get("resource_id") != RESOURCE_ID
                or snapshot.get("snapshot_complete") is not True
                or snapshot.get("accepted") is not False):
            raise ValueError(f"{label} QGIP snapshot is incomplete or outside the verified source")
        hashes = snapshot.get("source_row_hashes")
        if (not isinstance(hashes, dict)
                or any(not isinstance(key, str) or not key or key != key.strip()
                       or not isinstance(value, str) or len(value) != 64
                       or any(character not in "0123456789abcdef" for character in value)
                       for key, value in hashes.items())):
            raise ValueError(f"{label} QGIP snapshot lacks valid per-Service-ID hashes")
        snapshot_hash = snapshot.get("snapshot_hash")
        if (not isinstance(snapshot_hash, str) or len(snapshot_hash) != 64
                or any(character not in "0123456789abcdef" for character in snapshot_hash)):
            raise ValueError(f"{label} QGIP snapshot lacks a valid complete-snapshot digest")
        source_total = snapshot.get("source_total")
        if (not isinstance(source_total, int) or isinstance(source_total, bool)
                or source_total != len(hashes)):
            raise ValueError(f"{label} QGIP snapshot row count differs from per-Service-ID hashes")
        business_hashes = snapshot.get("business_row_hashes")
        if (not isinstance(business_hashes, dict) or set(business_hashes) != set(hashes)
                or any(not isinstance(value, str) or len(value) != 64
                       or any(character not in "0123456789abcdef" for character in value)
                       for value in business_hashes.values())):
            raise ValueError(f"{label} QGIP snapshot lacks valid business row hashes")
        if not isinstance(snapshot.get("retrieved_utc"), str):
            raise ValueError(f"{label} QGIP snapshot lacks its retrieval timestamp")
        if not isinstance(snapshot.get("source_updated_utc"), str):
            raise ValueError(f"{label} QGIP snapshot lacks its source update timestamp")
        candidates = snapshot.get("records")
        if not isinstance(candidates, list):
            raise ValueError(f"{label} QGIP snapshot lacks its review candidate rows")
        candidate_ids: set[str] = set()
        for candidate in candidates:
            if (not isinstance(candidate, dict)
                    or candidate.get("RecordKind") != "OpportunityCandidate"
                    or candidate.get("Source") != "qld-qgip"
                    or candidate.get("ReviewStatus") != "Needs Review"
                    or candidate.get("Status") != "Needs Review"):
                raise ValueError(f"{label} QGIP review candidate has invalid boundary fields")
            source_id = candidate.get("SourceID")
            if (not isinstance(source_id, str) or not source_id.strip()
                    or source_id != source_id.strip() or source_id in candidate_ids
                    or source_id not in hashes):
                raise ValueError(f"{label} QGIP review candidate has invalid source identity")
            # Earlier complete receipts carried only EvidenceHash; preserve
            # their comparability while validating the new business hash when
            # it is present on a candidate.
            if (candidate.get("EvidenceHash") != hashes[source_id]
                    or ("BusinessEvidenceHash" in candidate
                        and candidate["BusinessEvidenceHash"] != business_hashes[source_id])):
                raise ValueError(f"{label} QGIP review candidate differs from source-row evidence")
            candidate_ids.add(source_id)
    prior_at = _aware(prior["retrieved_utc"])
    current_at = _aware(current["retrieved_utc"])
    if current_at <= prior_at:
        raise ValueError("current QGIP snapshot must be later than prior snapshot")
    prior_updated = _aware(prior["source_updated_utc"])
    current_updated = _aware(current["source_updated_utc"])
    if prior_updated > prior_at or current_updated > current_at:
        raise ValueError("QGIP source update is later than snapshot retrieval")
    if current_updated < prior_updated:
        raise ValueError("QGIP source update regressed between snapshots")

    prior_hashes = prior["source_row_hashes"]
    current_hashes = current["source_row_hashes"]
    prior_business = prior["business_row_hashes"]
    current_business = current["business_row_hashes"]
    prior_ids, current_ids = set(prior_hashes), set(current_hashes)
    added = sorted(current_ids - prior_ids)
    removed = sorted(prior_ids - current_ids)
    changed = sorted(key for key in prior_ids & current_ids
                     if prior_hashes[key] != current_hashes[key])
    business_changed = sorted(key for key in prior_ids & current_ids
                              if prior_business[key] != current_business[key])
    ordinal_only_changed = sorted(set(changed) - set(business_changed))
    prior_candidates = {row["SourceID"] for row in prior["records"]}
    current_candidates = {row["SourceID"] for row in current["records"]}
    same_day = prior_at.date() == current_at.date()
    # CKAN can return the same rows in a different page/order or rebuild its
    # internal _id ordinal. Use per-Service-ID business hashes plus source
    # timestamp for content equivalence; preserve the raw digest separately.
    # Service IDs remain observation labels, not certified identity.
    ordered_digest_equal = prior["snapshot_hash"] == current["snapshot_hash"]
    # Receipts may encode the same UTC instant as Z or with an explicit
    # offset. Compare parsed instants rather than their serialization.
    digest_equal = prior_business == current_business and prior_updated == current_updated
    metadata_only_change = (prior_business == current_business and
                            prior_updated != current_updated)
    # A business-row delta with no corresponding resource update is a useful
    # review signal, but cannot be promoted to an authoritative change event.
    unannounced_content_change = (prior_business != current_business and
                                  prior_updated == current_updated)
    if same_day:
        classification = "same_day_digest_equal" if digest_equal else "same_day_content_difference"
        evidence = "same_day_metadata_change_only" if metadata_only_change else "same_day_repeatability_only"
    else:
        classification = "later_date_digest_equal" if digest_equal else "later_date_content_difference"
        evidence = ("no_change_detected_across_dates" if digest_equal else
                    "source_metadata_changed_across_dates" if metadata_only_change else
                    "source_content_changed_across_dates")
    return {
        "source": "qld-qgip",
        "comparison": classification,
        "temporal_evidence": evidence,
        "prior_retrieved_utc": prior_at.isoformat().replace("+00:00", "Z"),
        "current_retrieved_utc": current_at.isoformat().replace("+00:00", "Z"),
        "prior_snapshot_hash": prior.get("snapshot_hash"),
        "current_snapshot_hash": current.get("snapshot_hash"),
        "ordered_snapshot_digest_equal": ordered_digest_equal,
        "raw_row_hashes_equal": prior_hashes == current_hashes,
        "added_service_ids": added,
        "removed_service_ids": removed,
        "changed_service_ids": business_changed,
        "raw_changed_service_ids": changed,
        "business_changed_service_ids": business_changed,
        "ckan_ordinal_only_changed_service_ids": ordinal_only_changed,
        "content_changed_without_source_update": unannounced_content_change,
        "review_candidates_entered": sorted(current_candidates - prior_candidates),
        "review_candidates_exited": sorted(prior_candidates - current_candidates),
        "review_candidates_business_changed": sorted(
            prior_candidates & current_candidates & set(business_changed)),
        "review_candidates_unchanged": sorted(
            (prior_candidates & current_candidates) - set(business_changed)),
        "observed_absence_is_tombstone": False,
        "service_id_identity_proven": False,
        "authoritative_lifecycle_semantics_proven": False,
        "canonical_admission": False,
    }


def fetch_review_queue(*, retrieved_at: str | None = None,
                       opener: Callable[..., Any] = urllib.request.urlopen,
                       catalogue_path: str | Path = DEFAULT_CATALOGUE) -> dict[str, Any]:
    """Fetch an exact bounded CKAN snapshot; perform no registry writes."""
    require_enabled_source(catalogue_path, SOURCE_ID)
    observed_text = retrieved_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    retained_responses: list[dict[str, Any]] = []

    def get(action: str, params: dict[str, Any]) -> dict[str, Any]:
        return _get_json(action, params, opener, retained_responses=retained_responses)

    index = get("datastore_search", {
        "resource_id": INDEX_RESOURCE_ID, "limit": 100, "offset": 0,
    })
    catalogue_pointer = _catalogue_pointer(index)
    package = get("package_show", {"id": PACKAGE_NAME})
    package_pointer = _package_pointer(package)
    resource = get("resource_show", {"id": RESOURCE_ID})
    schema = validate_catalogue_schema(get("datastore_info", {"id": RESOURCE_ID}))
    if package.get("id") != PACKAGE_ID:
        raise ValueError("Queensland Health QGIP package mapping changed")
    def read_pages() -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        first = get("datastore_search", {"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": 0})
        total = first.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError("QGIP API did not provide an exact integer total")
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if page_count > MAX_PAGES:
            raise ValueError("QGIP snapshot exceeds configured page bound")
        pages.append(first)
        for page_number in range(1, page_count):
            page = get("datastore_search", {
                "resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": page_number * PAGE_SIZE,
            })
            pages.append(page)
        return pages

    first_snapshot = build_review_queue(package=package, resource=resource,
                                        pages=read_pages(), retrieved_at=observed_text)
    second_snapshot = build_review_queue(package=package, resource=resource,
                                         pages=read_pages(), retrieved_at=observed_text)
    # Exact totals and unique IDs alone can miss a same-count replacement
    # while CKAN's offset pages are read. Order may vary; compare full row
    # content by observed Service ID, without treating it as immutable identity.
    if first_snapshot["source_row_hashes"] != second_snapshot["source_row_hashes"]:
        raise ValueError("QGIP source rows changed between complete page reads")
    resource_after = get("resource_show", {"id": RESOURCE_ID})
    drift_fields = ("id", "package_id", "last_modified", "hash")
    if any(resource.get(field) != resource_after.get(field) for field in drift_fields):
        raise ValueError("QGIP resource changed during snapshot read")
    schema_after = validate_catalogue_schema(get("datastore_info", {"id": RESOURCE_ID}))
    if schema_after != schema:
        raise ValueError("QGIP datastore schema changed during snapshot read")
    package_after = get("package_show", {"id": PACKAGE_NAME})
    if _package_pointer(package_after) != package_pointer:
        raise ValueError("QGIP package changed during snapshot read")
    index_after = get("datastore_search", {
        "resource_id": INDEX_RESOURCE_ID, "limit": 100, "offset": 0,
    })
    if _catalogue_pointer(index_after) != catalogue_pointer:
        raise ValueError("Grants Finder catalogue pointer changed during snapshot read")
    second_snapshot["raw_source"]["http_responses"] = retained_responses
    return second_snapshot


def main(argv: list[str] | None = None,
         *, fetcher: Callable[[], dict[str, Any]] = fetch_review_queue) -> int:
    """Run the adapter only when the caller explicitly opts into live reads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch", action="store_true",
        help="perform the bounded, read-only CKAN snapshot request",
    )
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE,
                        help="source catalogue used to enforce the QGIP enabled switch")
    parser.add_argument("--output", type=Path, help="retain full snapshot in a new private/ops file")
    args = parser.parse_args(argv)
    if not args.fetch:
        parser.print_help()
        return 0
    try:
        require_enabled_source(args.catalogue, SOURCE_ID)
    except ValueError:
        parser.error("QGIP source is missing or disabled in the source catalogue")
    destination = None
    if args.output is not None:
        destination = args.output.resolve()
        private_root = Path(__file__).resolve().parents[1] / "private/ops"
        if not destination.is_relative_to(private_root.resolve()):
            parser.error("Full source output must remain in private/ops")
        if destination.exists() or not destination.parent.is_dir():
            parser.error("Output must be a new file in an existing private/ops directory")
    # Reserve exclusively before any source request; never overwrite retained evidence.
    descriptor = (os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                  if destination is not None else None)
    try:
        payload = (fetcher(catalogue_path=args.catalogue) if fetcher is fetch_review_queue
                   else fetcher())
        if descriptor is not None:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = None
                json.dump(payload, stream, indent=2, ensure_ascii=False)
        total = payload.get("source_total")
        summary = {"snapshot_complete": payload.get("snapshot_complete") is True,
                   "source_total": total if type(total) is int else None,
                   "candidate_count": len(payload.get("records", [])),
                   "snapshot_saved": destination is not None}
        print(json.dumps(summary))
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
