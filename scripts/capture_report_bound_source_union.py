"""Accept the completed current-plus-retained source refresh in the bound DEV model.

Checks exact split-query PubMed keys, archive and prior-consumer key coverage,
source identity/link fields, selected values for validated archive metadata,
official evidence for current-only PubMed rows, report binding and exact
36-part definition/request correlation. Read-only; does not approve registry
admission, affiliation decisions, report rendering or archive promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.capture_retained_canary_acceptance import (
    _call, _fabric_definition, _latest_request, _token_for, definition_digest,
)
from scripts.reconcile_publication_sources import retained_rows
from scripts.verify_retained_canary_keys import model_rows
from scripts.verify_retained_canary_metadata_values import (
    _date_parts, expected as expected_metadata, query as metadata_query,
    verify as verify_metadata,
)

PRIVATE = (Path(__file__).resolve().parents[1] / "private/ops").resolve()
POWERBI = "https://api.powerbi.com/v1.0/myorg"
SOURCE_QUERY = '''EVALUATE
UNION(
    SELECTCOLUMNS('PubMedPublications', "Source", "PubMed", "SourceID", 'PubMedPublications'[PMID]),
    SELECTCOLUMNS('DoraPublications', "Source", "DORA", "SourceID", 'DoraPublications'[DORAKey])
)'''
METADATA_QUERY = '''EVALUATE DISTINCT(SELECTCOLUMNS('PubMedMetadataChunks', "PMID", 'PubMedMetadataChunks'[PMID]))'''
CONSUMER_QUERY = '''EVALUATE SELECTCOLUMNS('Publication', "CanonicalKey", 'Publication'[CanonicalKey], "PMID", 'Publication'[PMID], "DORAURL", 'Publication'[DORAURL], "SourceSet", 'Publication'[SourceSet], "AttributionStatus", 'Publication'[AttributionStatus], "FacilityMatchCount", 'Publication'[FacilityMatchCount])'''
FIELD_QUERY = '''EVALUATE
UNION(
    SELECTCOLUMNS('PubMedPublications', "Source", "PubMed", "SourceID", 'PubMedPublications'[PMID], "Title", COALESCE('PubMedPublications'[Title], ""), "SourceURL", COALESCE('PubMedPublications'[PubMedURL], ""), "CoverageStatus", ""),
    SELECTCOLUMNS('DoraPublications', "Source", "DORA", "SourceID", 'DoraPublications'[DORAKey], "Title", COALESCE('DoraPublications'[Title], ""), "SourceURL", COALESCE('DoraPublications'[DORAURL], ""), "CoverageStatus", COALESCE('DoraPublications'[CoverageStatus], ""))
)'''
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def private(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(PRIVATE):
        raise ValueError("private/ops path required")
    return path


def rows(payload: dict) -> list[dict]:
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1 or results[0].get("error"):
        raise ValueError("one successful query result required")
    tables = results[0].get("tables")
    if not isinstance(tables, list) or len(tables) != 1 or tables[0].get("error"):
        raise ValueError("one successful query table required")
    value = tables[0].get("rows")
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError("complete query rows required")
    return value


def evaluate_sources(source: list[dict], metadata: list[dict], consumer: list[dict],
                     archive: list[dict], prior: list[dict], official: set[str],
                     expected_pubmed: set[str] | None = None) -> tuple[dict, dict]:
    observed = {"PubMed": [], "DORA": []}
    for row in source:
        if set(row) != {"[Source]", "[SourceID]"} or row["[Source]"] not in observed:
            raise ValueError("unexpected canonical source row")
        value = row["[SourceID]"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("blank canonical source key")
        observed[row["[Source]"]].append(value)
    archived = {"PubMed": set(), "DORA": set()}
    for row in archive:
        archived[row["Source"]].add(row["SourceID"])
    model_pubmed, model_dora = set(observed["PubMed"]), set(observed["DORA"])
    metadata_ids = [row.get("[PMID]") for row in metadata]
    if any(set(row) != {"[PMID]"} or not isinstance(row["[PMID]"], str) or not row["[PMID]"].strip() for row in metadata):
        raise ValueError("invalid metadata PMID query row")
    old_keys = [row.get("[CanonicalKey]") for row in prior]
    new_keys = [row.get("[CanonicalKey]") for row in consumer]
    if any(not isinstance(key, str) or not key.strip() for key in old_keys + new_keys):
        raise ValueError("blank report consumer identity")
    extra = model_pubmed - archived["PubMed"]
    differences = {
        "missing_archive_pubmed": sorted(archived["PubMed"] - model_pubmed),
        "missing_archive_dora": sorted(archived["DORA"] - model_dora),
        "extra_dora": sorted(model_dora - archived["DORA"]),
        "current_only_pubmed": sorted(extra),
        "current_only_without_official_evidence": sorted(extra - official),
        "missing_prior_consumer_keys": sorted(set(old_keys) - set(new_keys)),
        "gained_consumer_keys": sorted(set(new_keys) - set(old_keys)),
        "metadata_without_summary": sorted(set(metadata_ids) - model_pubmed),
        "summary_without_metadata": sorted(model_pubmed - set(metadata_ids)),
    }
    if expected_pubmed is not None:
        differences["split_union_key_mismatch"] = sorted(model_pubmed ^ expected_pubmed)
    duplicate_counts = {
        "pubmed": len(observed["PubMed"]) - len(model_pubmed),
        "dora": len(observed["DORA"]) - len(model_dora),
        "metadata": len(metadata_ids) - len(set(metadata_ids)),
        "consumer": len(new_keys) - len(set(new_keys)),
    }
    pass_checks = all(not value for key, value in differences.items()
                      if key not in {"current_only_pubmed", "gained_consumer_keys"}) and all(value == 0 for value in duplicate_counts.values())
    receipt = {
        "kind": "report_bound_current_retained_source_union_acceptance_v2",
        "status": "PASS" if pass_checks else "FAIL",
        "counts": {"archive_pubmed": len(archived["PubMed"]), "archive_dora": len(archived["DORA"]),
                   "model_pubmed": len(observed["PubMed"]), "model_dora": len(observed["DORA"]),
                   "current_only_pubmed": len(extra), "official_evidence_ids": len(official),
                   "metadata_keys": len(metadata_ids), "old_consumer_keys": len(old_keys), "new_consumer_keys": len(new_keys)},
        "duplicate_counts": duplicate_counts,
        "difference_counts": {key: len(value) for key, value in differences.items()},
        "scope": "DEV model source and consumer identity nonloss only; no registry admission, complete metadata value parity, report rendering, staging commit or release",
    }
    return receipt, differences


def evaluate_consumer_additions(prior: list[dict], consumer: list[dict],
                                source: list[dict], official: set[str]) -> tuple[dict, dict]:
    """Require every newly appearing canonical consumer to remain review-only."""
    old_keys = [row.get("[CanonicalKey]") for row in prior]
    current_keys = [row.get("[CanonicalKey]") for row in consumer]
    if any(not isinstance(key, str) or not key.strip() for key in old_keys + current_keys):
        raise ValueError("blank consumer identity in gain-side reconciliation")
    if len(current_keys) != len(set(current_keys)):
        raise ValueError("duplicate current canonical consumer identity")
    source_pairs = {(row.get("[Source]"), row.get("[SourceID]")) for row in source}
    rows_by_key = {row["[CanonicalKey]"]: row for row in consumer}
    gained = sorted(set(current_keys) - set(old_keys))
    issues = []
    for canonical in gained:
        row = rows_by_key[canonical]
        if canonical.startswith("PMID:"):
            source_name, source_id = "PubMed", canonical.removeprefix("PMID:")
            if row.get("[PMID]") != source_id or source_id not in official:
                issues.append({"canonical_key": canonical, "issue": "gained PubMed consumer lacks exact official evidence"})
        elif canonical.startswith("DORA:"):
            source_name, source_id = "DORA", canonical
            if row.get("[DORAURL]") != canonical.removeprefix("DORA:"):
                issues.append({"canonical_key": canonical, "issue": "gained DoRA consumer identity mismatch"})
        else:
            issues.append({"canonical_key": canonical, "issue": "gained consumer has an unsupported canonical identity"})
            continue
        if (source_name, source_id) not in source_pairs:
            issues.append({"canonical_key": canonical, "issue": "gained consumer is absent from current source rows"})
        status = row.get("[AttributionStatus]")
        if not isinstance(status, str) or not any(
                marker in status.casefold() for marker in ("review", "not manually verified", "unverified")):
            issues.append({"canonical_key": canonical, "issue": "gained consumer is not explicitly review-only"})
        count = row.get("[FacilityMatchCount]")
        if count is not None and (not isinstance(count, (int, float)) or count < 0):
            issues.append({"canonical_key": canonical, "issue": "invalid facility match count"})
    receipt = {"kind": "report_bound_consumer_gain_review_v1",
               "status": "PASS" if not issues else "FAIL",
               "prior_consumer_count": len(set(old_keys)),
               "current_consumer_count": len(set(current_keys)),
               "gained_consumer_count": len(gained),
               "gained_review_only_count": len(gained) - len({x["canonical_key"] for x in issues}),
               "issue_count": len(issues)}
    return receipt, {"gained_consumer_keys": gained, "issues": issues}


def split_pubmed_keys(payload: dict) -> set[str]:
    """Parse a saved successful PMID-only ExecuteQueries response strictly."""
    if not isinstance(payload, dict) or payload.get("http") != 200:
        raise ValueError("saved split-query key readback must have HTTP 200")
    body = payload.get("body")
    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list) or len(results) != 1 or results[0].get("error"):
        raise ValueError("one successful saved split-query result required")
    tables = results[0].get("tables")
    if not isinstance(tables, list) or len(tables) != 1 or tables[0].get("error"):
        raise ValueError("one successful saved split-query table required")
    values = tables[0].get("rows")
    if not isinstance(values, list) or not all(
            isinstance(row, dict) and set(row) == {"[PMID]"}
            and isinstance(row["[PMID]"], str) and row["[PMID]"].isascii()
            and row["[PMID]"].isdecimal() and not row["[PMID]"].startswith("0")
            for row in values):
        raise ValueError("saved split-query rows require canonical PMID values")
    keys = [row["[PMID]"] for row in values]
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("saved split-query PMID keys are empty or duplicated")
    return set(keys)


def evaluate_fields(payload: dict, expected_keys: set[tuple[str, str]]) -> tuple[dict, dict]:
    """Check report-bound source identity and source-link fields without inferring attribution."""
    field_names = {"[Source]", "[SourceID]", "[Title]", "[SourceURL]", "[CoverageStatus]"}
    observed: set[tuple[str, str]] = set()
    issues = []
    field_rows = rows_from_payload(payload)
    for row in field_rows:
        if set(row) != field_names:
            raise ValueError("report-bound field rows require exactly five aliases")
        try:
            identity = (row["[Source]"], row["[SourceID]"])
            source, source_id = identity
            if source not in {"PubMed", "DORA"} or not isinstance(source_id, str):
                raise ValueError("source identity is malformed")
            if source == "PubMed" and (not source_id.isascii() or not source_id.isdecimal() or source_id.startswith("0")):
                raise ValueError("PubMed PMID is noncanonical")
            if source == "DORA" and (not source_id.startswith("DORA:") or not source_id[5:]):
                raise ValueError("DORA key is noncanonical")
        except (ValueError, TypeError) as exc:
            issues.append({"identity": row.get("[SourceID]"), "issue": str(exc)})
            continue
        if identity in observed:
            issues.append({"identity": identity, "issue": "duplicate source identity"})
        observed.add(identity)
        title, source_url, coverage = row["[Title]"], row["[SourceURL]"], row["[CoverageStatus]"]
        if not isinstance(title, str) or not title.strip():
            issues.append({"identity": identity, "issue": "blank title"})
        if not isinstance(source_url, str) or not source_url:
            issues.append({"identity": identity, "issue": "blank source URL"})
        elif source == "PubMed":
            parsed = urlparse(source_url)
            if (parsed.scheme != "https" or parsed.hostname not in {"pubmed.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"}
                    or parsed.path.rstrip("/") not in {f"/{source_id}", f"/pubmed/{source_id}"}
                    or parsed.query or parsed.fragment):
                issues.append({"identity": identity, "issue": "PubMed URL does not identify the PMID on an official host"})
        elif source_url != source_id[5:]:
            issues.append({"identity": identity, "issue": "DORA URL differs from its DORA key"})
        if not isinstance(coverage, str) or (source == "PubMed" and coverage != "") or (source == "DORA" and coverage != "Accepted retained source observation"):
            issues.append({"identity": identity, "issue": "unexpected source coverage value"})
    missing, extra = expected_keys - observed, observed - expected_keys
    receipt = {"kind": "report_bound_source_field_integrity_v1",
               "status": "PASS" if len(field_rows) == len(expected_keys) and not missing and not extra and not issues else "FAIL",
               "row_count": len(field_rows), "expected_key_count": len(expected_keys),
               "missing_key_count": len(missing), "extra_key_count": len(extra),
               "issue_count": len(issues),
               "scope": "report-bound source IDs, nonblank titles, official/identity-matched links and source coverage; no affiliation adjudication"}
    return receipt, {"missing": sorted(missing), "extra": sorted(extra), "issues": issues}


def rows_from_payload(payload: dict) -> list[dict]:
    """Strict generic ExecuteQueries row envelope used for multi-field queries."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("successful ExecuteQueries body required")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1 or results[0].get("error"):
        raise ValueError("one successful ExecuteQueries result required")
    tables = results[0].get("tables")
    if not isinstance(tables, list) or len(tables) != 1 or tables[0].get("error"):
        raise ValueError("one successful ExecuteQueries table required")
    values = tables[0].get("rows")
    if not isinstance(values, list) or not all(isinstance(row, dict) for row in values):
        raise ValueError("complete ExecuteQueries row list required")
    return values


def archive_metadata_parity(payload: dict, source: str, archive_dir: Path,
                             validated_dir: Path) -> tuple[dict, dict, list[str]]:
    """Compare selected live source fields for committed archive identities."""
    result_rows = rows_from_payload(payload)
    key = "[PMID]" if source == "PubMed" else "[DORAKey]"
    actual_keys = [row.get(key) for row in result_rows]
    if any(not isinstance(value, str) or not value for value in actual_keys) or len(actual_keys) != len(set(actual_keys)):
        raise ValueError(f"{source} metadata readback has blank or duplicate keys")
    wanted = expected_metadata(archive_dir, validated_dir, source)
    archive_rows = [row for row in result_rows if row[key] in wanted]
    filtered = {"results": [{"tables": [{"rows": archive_rows}]}]}
    receipt, differences = verify_metadata(filtered, wanted, source)
    extra_keys = sorted(set(actual_keys) - set(wanted))
    receipt.update({"live_model_rows": len(result_rows), "archive_rows_compared": len(archive_rows),
                    "nonarchive_current_rows": len(extra_keys),
                    "scope": "selected source metadata values for validated committed archive identities; current-only PubMed values rely on official EFetch evidence and are separately key-correlated"})
    return receipt, differences, extra_keys


def _xml_text(node: ET.Element | None) -> str:
    return "" if node is None else "".join(node.itertext())


def _ncbi_date(node: ET.Element | None) -> str:
    if node is None:
        return ""
    medline = node.findtext("MedlineDate")
    if medline:
        return medline.strip()
    return " ".join(value.strip() for name in ("Year", "Month", "Day")
                     if (value := node.findtext(name)))


def _electronic_date(node: ET.Element | None) -> str:
    if node is None:
        return ""
    year, month, day = tuple((node.findtext(name) or "").strip()
                             for name in ("Year", "Month", "Day"))
    month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    if month.isdigit() and 1 <= int(month) <= 12:
        month = month_names[int(month) - 1]
    if day.isdigit():
        day = str(int(day))
    return " ".join(value for value in (year, month, day) if value)


def project_current_pubmed_efetch(xml_bytes: bytes) -> dict[str, dict]:
    """Project official current EFetch fields used by the model's PubMed table."""
    root = ET.fromstring(xml_bytes)
    if root.tag != "PubmedArticleSet" or root.findall("./PubmedBookArticle"):
        raise ValueError("official EFetch response has an unsupported article shape")
    result = {}
    for article in root.findall("./PubmedArticle"):
        citation = article.find("./MedlineCitation")
        record = article.find("./MedlineCitation/Article")
        journal = None if record is None else record.find("./Journal")
        if citation is None or record is None:
            raise ValueError("official EFetch response omitted required article structure")
        pmid = citation.findtext("./PMID")
        if not pmid or pmid in result:
            raise ValueError("official EFetch returned a blank or duplicate PMID")
        author_names = []
        for author in record.findall("./AuthorList/Author"):
            collective = _xml_text(author.find("./CollectiveName"))
            if collective:
                name = collective
            else:
                first = author.findtext("./ForeName") or author.findtext("./Initials") or ""
                last = author.findtext("./LastName") or ""
                suffix = author.findtext("./Suffix") or ""
                name = " ".join(part for part in (first.strip(), last.strip(), suffix.strip()) if part)
            if name:
                author_names.append(name)
        issue_raw = _ncbi_date(None if journal is None else journal.find("./JournalIssue/PubDate"))
        precision, year = _date_parts(issue_raw)
        if year is not None and year < 1900 and precision in ("day", "month"):
            precision = "outside-model-range"
        online_dates = [d for d in record.findall("./ArticleDate")
                        if d.attrib.get("DateType", "").casefold() == "electronic"]
        online_raw = _electronic_date(online_dates[0]) if online_dates else ""
        result[pmid] = {
            "Title": _xml_text(record.find("./ArticleTitle")),
            "Journal": _xml_text(None if journal is None else journal.find("./Title")),
            "Authors": "; ".join(author_names),
            "Abstract": "\n".join(_xml_text(node) for node in record.findall("./Abstract/AbstractText")),
            "PublicationDateRaw": issue_raw,
            "PublicationDatePrecision": precision,
            "PublicationYear": year,
            "OnlineDateRaw": online_raw,
        }
    if not result:
        raise ValueError("official EFetch response contained no PubMed articles")
    return result


def fetch_current_pubmed_efetch(identities: set[str]) -> tuple[bytes, dict]:
    """Fetch one bounded, exact-key NCBI EFetch response for changed archive rows."""
    if not identities or any(not key.isascii() or not key.isdigit() for key in identities):
        raise ValueError("changed PubMed identities must be positive numeric PMIDs")
    if len(identities) > 5000:
        raise ValueError("too many changed PMIDs for one bounded EFetch request")
    encoded = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(sorted(identities)), "retmode": "xml"}).encode()
    request = urllib.request.Request(NCBI_EFETCH, data=encoded, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "CHHHS RIMS source reconciliation",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        status = response.status
        url = response.geturl()
        date_header = response.headers.get("Date")
    if status != 200:
        raise ValueError(f"NCBI EFetch returned HTTP {status}")
    projected = project_current_pubmed_efetch(raw)
    if set(projected) != identities:
        raise ValueError("NCBI EFetch PMID set does not exactly match changed archived identities")
    receipt = {"http": status, "url": url, "response_date": date_header,
               "captured_utc": datetime.now(timezone.utc).isoformat(),
               "requested_count": len(identities), "returned_count": len(projected),
               "requested_key_sha256": hashlib.sha256("\n".join(sorted(identities)).encode()).hexdigest(),
               "response_sha256": hashlib.sha256(raw).hexdigest()}
    return raw, receipt


def classify_current_source_differences(payload: dict, differences: list[dict],
                                       official: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Resolve archive mismatches only when the model equals current NCBI data."""
    model_rows = rows_from_payload(payload)
    actual_by_key = {row.get("[PMID]"): row for row in model_rows}
    changed_keys = {item.get("source_id") for item in differences
                    if item.get("kind") == "value_mismatch"}
    if not changed_keys <= set(official):
        raise ValueError("current-source readback omits one or more changed PubMed keys")
    accepted, unresolved = [], []
    for item in differences:
        if item.get("kind") != "value_mismatch":
            continue
        identity, field = item.get("source_id"), item.get("field")
        if (identity not in actual_by_key or field not in official.get(identity, {})):
            unresolved.append(item)
            continue
        actual = actual_by_key[identity].get(f"[{field}]")
        expected = official[identity][field]
        exact = actual == expected
        normal = (field in {"Title", "Journal", "Authors", "Abstract"}
                  and isinstance(actual, str) and isinstance(expected, str)
                  and actual.rstrip(" ").casefold() == expected.rstrip(" ").casefold())
        if exact or normal:
            kind = "current_source_update" if exact else "current_source_update_with_engine_normalization"
            accepted.append({**item, "kind": kind})
        else:
            unresolved.append(item)
    return accepted, unresolved


def reconcile_pubmed_archive_metadata(payload: dict, archive_dir: Path,
                                       validated_dir: Path, raw_xml_path: Path,
                                       receipt_path: Path, *, fetcher=None):
    """Permit archived-value drift only when a fresh official source confirms it."""
    parity, differences, extra_keys = archive_metadata_parity(
        payload, "PubMed", archive_dir, validated_dir)
    mismatches = [item for item in differences if item.get("kind") == "value_mismatch"]
    changed_keys = {item["source_id"] for item in mismatches}
    if not changed_keys:
        return parity, differences, extra_keys
    raw, fetch_receipt = (fetcher or fetch_current_pubmed_efetch)(changed_keys)
    # Persist exact source response before evaluating it; private raw evidence
    # remains available if XML parsing or a subsequent assertion fails.
    raw_xml_path.write_bytes(raw)
    official = project_current_pubmed_efetch(raw)
    if set(official) != changed_keys:
        raise ValueError("saved official EFetch did not cover the exact changed PMID set")
    accepted, unresolved = classify_current_source_differences(payload, differences, official)
    # Preserve non-substantive archive-vs-model normalizations while replacing
    # only those differences that have exact current-source evidence.
    resolved_ids = {(item["source_id"], item["field"]) for item in accepted}
    output = [item for item in differences
              if (item.get("source_id"), item.get("field")) not in resolved_ids]
    output.extend(accepted)
    counts = {kind: sum(item.get("kind") == kind for item in output)
              for kind in ("engine_text_normalization", "current_source_update",
                           "current_source_update_with_engine_normalization", "value_mismatch")}
    parity["current_source_updates"] = counts["current_source_update"] + counts["current_source_update_with_engine_normalization"]
    parity["substantive_differences"] = counts["value_mismatch"]
    parity["status"] = ("FAIL" if unresolved else
        "PASS_WITH_ENGINE_NORMALIZATION_AND_CURRENT_SOURCE_UPDATES"
        if counts["engine_text_normalization"] and parity["current_source_updates"] else
        "PASS_WITH_CURRENT_SOURCE_UPDATES" if parity["current_source_updates"] else
        "PASS_WITH_ENGINE_NORMALIZATION" if counts["engine_text_normalization"] else "PASS")
    fetch_receipt.update({"changed_keys": sorted(changed_keys),
                          "changed_key_count": len(changed_keys),
                          "unresolved_mismatch_count": len(unresolved)})
    receipt_path.write_text(json.dumps(fetch_receipt, indent=2) + "\n")
    return parity, output, extra_keys


def metadata_key_batches(identities: set[str], expected_rows: dict,
                        max_estimated_chars: int = 150_000) -> list[list[str]]:
    """Bound DAX response sizes using validated row widths before querying."""
    if max_estimated_chars < 10_000:
        raise ValueError("metadata batch budget is too small")
    batches: list[list[str]] = []
    current: list[str] = []
    estimated = 0
    fallback_encoded_size = max((len(json.dumps(value, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8"))
                                 for value in expected_rows.values()), default=10_000)
    fallback_encoded_size = max(fallback_encoded_size, 10_000)
    for identity in sorted(identities):
        if not isinstance(identity, str) or not identity:
            raise ValueError("metadata batch identities must be nonblank strings")
        row = expected_rows.get(identity)
        encoded_size = (len(json.dumps(row, ensure_ascii=False,
                                       separators=(",", ":")).encode("utf-8"))
                        if row is not None else fallback_encoded_size)
        # Allow 3x JSON escaping/serialization overhead plus the source key and aliases.
        row_estimate = encoded_size * 3 + len(identity.encode("utf-8")) * 3 + 512
        if current and estimated + row_estimate > max_estimated_chars:
            batches.append(current)
            current, estimated = [], 0
        if row_estimate > max_estimated_chars:
            raise ValueError("one metadata record exceeds the safe DAX response budget")
        current.append(identity)
        estimated += row_estimate
    if current:
        batches.append(current)
    if set(identity for batch in batches for identity in batch) != identities:
        raise ValueError("metadata batch planning lost source identities")
    return batches


def read_metadata_batches(prefix: Path, url: str, token: str, source: str,
                          table: str, identities: set[str],
                          expected_rows: dict) -> tuple[tuple[int, dict], list[dict]]:
    """Save and reconcile every bounded metadata query before returning its rows."""
    batches = metadata_key_batches(identities, expected_rows)
    paths = [Path(f"{prefix}-{source.lower()}-metadata-batch-{i:03d}.json")
             for i in range(1, len(batches) + 1)]
    if any(path.exists() for path in paths):
        raise ValueError("metadata batch evidence path already exists; choose a fresh prefix")
    all_rows: list[dict] = []
    receipts = []
    key_name = "[PMID]" if source == "PubMed" else "[DORAKey]"
    for index, (keys, raw_path) in enumerate(zip(batches, paths), start=1):
        http, payload = _call(url, token, metadata_query(source, table, tuple(keys)))
        raw = {"http": http, "requested_identity_count": len(keys), "body": payload}
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
        if http != 200:
            raise ValueError(f"{source} metadata batch {index} did not return HTTP 200; raw response preserved")
        batch_rows = rows_from_payload(payload)
        returned = [row.get(key_name) for row in batch_rows]
        if (any(not isinstance(key, str) or not key for key in returned)
                or len(returned) != len(set(returned)) or set(returned) != set(keys)):
            raise ValueError(f"{source} metadata batch {index} omitted, duplicated, or added identities; raw response preserved")
        all_rows.extend(batch_rows)
        receipts.append({"batch": index, "requested_rows": len(keys),
                         "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                         "path": str(raw_path)})
    if len(all_rows) != len(identities) or {row[key_name] for row in all_rows} != identities:
        raise ValueError(f"{source} metadata batches did not reconcile to all requested identities")
    return (200, {"results": [{"tables": [{"rows": all_rows}]}]}), receipts


def main(token_provider=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace_id", "model_id", "report_id", "request_id", "definition", "archive", "prior_consumer", "official_efetch", "split_keys", "preflight_receipt", "archive_dir", "validated_dir", "prefix"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    a = parser.parse_args()
    if not callable(token_provider):
        parser.error("Run main(token_provider=...) through the already-qualified VS Code wrapper; this entry point performs no automatic authentication")
    prefix = private(a.prefix)
    receipt_path = Path(str(prefix) + "-receipt.json")
    output_paths = [Path(str(prefix) + suffix) for suffix in (
        "-receipt.json", "-source.json", "-metadata.json", "-consumer.json",
        "-fields.json", "-pubmed-metadata-values.json", "-dora-metadata-values.json",
        "-pubmed-current-source-updates.xml", "-pubmed-current-source-updates.json",
        "-consumer-gains.json", "-consumer-gain-differences.json",
        "-differences.json", "-field-differences.json", "-archive-metadata-differences.json")]
    if any(path.exists() for path in output_paths):
        raise ValueError("one or more acceptance evidence outputs already exist; choose a fresh prefix")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    expected = json.loads(private(a.definition).read_text())
    archive_bytes = private(a.archive).read_bytes()
    archive = retained_rows(json.loads(archive_bytes))
    old_payload = json.loads(private(a.prior_consumer).read_text())
    prior = rows(old_payload)
    xml_bytes = private(a.official_efetch).read_bytes()
    official = {node.text for node in ET.fromstring(xml_bytes).findall(".//PubmedArticle/MedlineCitation/PMID") if node.text}
    if not official:
        raise ValueError("official PubMed XML yielded no PMID evidence")
    split_path = private(a.split_keys)
    preflight_path = private(a.preflight_receipt)
    split_bytes = split_path.read_bytes()
    preflight = json.loads(preflight_path.read_bytes())
    split_evidence = preflight.get("evidence_files", {}).get("split-keys", {})
    if (Path(split_evidence.get("path", "")).resolve() != split_path
            or split_evidence.get("sha256") != hashlib.sha256(split_bytes).hexdigest()):
        raise ValueError("split-query keys are not the exact keys fingerprinted by the preflight")
    expected_pubmed = split_pubmed_keys(json.loads(split_bytes))
    archive_pubmed = {row["SourceID"] for row in archive if row["Source"] == "PubMed"}
    archive_dora = {row["SourceID"] for row in archive if row["Source"] == "DORA"}
    if not archive_pubmed <= expected_pubmed:
        raise ValueError("saved split-query key set omits committed archive PubMed identities")
    expected_field_keys = ({("PubMed", key) for key in expected_pubmed}
                           | {("DORA", key) for key in archive_dora})
    archive_dir, validated_dir = private(a.archive_dir), private(a.validated_dir)
    expected_archive_metadata = {
        "PubMed": expected_metadata(archive_dir, validated_dir, "PubMed"),
        "DORA": expected_metadata(archive_dir, validated_dir, "DORA"),
    }
    powerbi = _token_for("https://analysis.windows.net/powerbi/api", token_provider)
    fabric = _token_for("https://api.fabric.microsoft.com", token_provider)
    binding_http, binding = _call(f"{POWERBI}/reports/{a.report_id}", powerbi)
    if binding_http != 200 or binding.get("datasetId") != a.model_id:
        raise ValueError("report binding drifted")
    history_url = f"{POWERBI}/datasets/{a.model_id}/refreshes?$top=1"
    history_http, before = _call(history_url, powerbi)
    detail_http, detail = _call(f"{POWERBI}/datasets/{a.model_id}/refreshes/{a.request_id}", powerbi)
    if history_http != 200 or detail_http != 200 or _latest_request(before) != a.request_id or detail.get("status") != "Completed":
        raise ValueError("exact refresh is not latest Completed")
    model_before = _fabric_definition(a.workspace_id, a.model_id, fabric)
    digest = definition_digest(model_before, expected, 36)
    url = f"{POWERBI}/datasets/{a.model_id}/executeQueries"
    responses = {"source": _call(url, powerbi, SOURCE_QUERY),
                 "metadata": _call(url, powerbi, METADATA_QUERY),
                 "consumer": _call(url, powerbi, CONSUMER_QUERY),
                 "fields": _call(url, powerbi, FIELD_QUERY)}
    responses["pubmed-metadata-values"], pubmed_batch_receipts = read_metadata_batches(
        prefix, url, powerbi, "PubMed", "PubMedPublications", expected_pubmed,
        expected_archive_metadata["PubMed"])
    responses["dora-metadata-values"], dora_batch_receipts = read_metadata_batches(
        prefix, url, powerbi, "DORA", "DoraPublications", archive_dora,
        expected_archive_metadata["DORA"])
    after_http, after = _call(history_url, powerbi)
    model_after = _fabric_definition(a.workspace_id, a.model_id, fabric)
    if after_http != 200 or _latest_request(after) != a.request_id or definition_digest(model_after, expected, 36) != digest:
        raise ValueError("refresh or definition changed across DAX reads")
    for name, (http, body) in responses.items():
        Path(str(prefix) + f"-{name}.json").write_text(json.dumps({"http": http, "body": body}, indent=2) + "\n")
    if any(http != 200 for http, _ in responses.values()):
        raise ValueError("source query failed; raw responses preserved")
    source = model_rows(responses["source"][1])
    metadata = rows(responses["metadata"][1])
    consumer = rows(responses["consumer"][1])
    field_receipt, field_differences = evaluate_fields(responses["fields"][1], expected_field_keys)
    receipt, differences = evaluate_sources(source, metadata, consumer, archive, prior, official, expected_pubmed)
    consumer_gain_receipt, consumer_gain_differences = evaluate_consumer_additions(
        prior, consumer, source, official)
    archive_metadata = {}
    archive_metadata_differences = {}
    extra_metadata_keys = {}
    for source_name, response_name in (("PubMed", "pubmed-metadata-values"), ("DORA", "dora-metadata-values")):
        if source_name == "PubMed":
            parity, mismatches, extras = reconcile_pubmed_archive_metadata(
                responses[response_name][1], archive_dir, validated_dir,
                Path(str(prefix) + "-pubmed-current-source-updates.xml"),
                Path(str(prefix) + "-pubmed-current-source-updates.json"))
        else:
            parity, mismatches, extras = archive_metadata_parity(
                responses[response_name][1], source_name, archive_dir, validated_dir)
        archive_metadata[source_name] = parity
        archive_metadata_differences[source_name] = mismatches
        extra_metadata_keys[source_name] = extras
    expected_current_only = sorted(expected_pubmed - archive_pubmed)
    metadata_extra_pass = (extra_metadata_keys["PubMed"] == expected_current_only
                           and extra_metadata_keys["DORA"] == [])
    receipt["field_integrity"] = field_receipt
    receipt["consumer_gains"] = consumer_gain_receipt
    receipt["archive_metadata_values"] = archive_metadata
    receipt["archive_metadata_current_only_keys"] = extra_metadata_keys
    receipt["scope"] = "one exact report-bound DEV refresh: source union and prior-consumer keys, selected source fields, selected validated-archive metadata values, exact report/model binding and 36-part definition; no registry admission or report rendering"
    receipt["status"] = ("PASS" if receipt["status"] == "PASS"
                         and field_receipt["status"] == "PASS"
                         and consumer_gain_receipt["status"] == "PASS"
                         and metadata_extra_pass
                         and all(item["status"] in {"PASS", "PASS_WITH_ENGINE_NORMALIZATION",
                                                     "PASS_WITH_CURRENT_SOURCE_UPDATES",
                                                     "PASS_WITH_ENGINE_NORMALIZATION_AND_CURRENT_SOURCE_UPDATES"}
                                 for item in archive_metadata.values()) else "FAIL")
    receipt.update({"captured_utc": datetime.now(timezone.utc).isoformat(), "request_id": a.request_id,
                    "exact_definition_sha256": digest, "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
                    "prior_consumer_sha256": hashlib.sha256(private(a.prior_consumer).read_bytes()).hexdigest(),
                    "official_efetch_sha256": hashlib.sha256(xml_bytes).hexdigest(),
                    "split_keys_sha256": hashlib.sha256(split_bytes).hexdigest(),
                    "preflight_receipt_sha256": hashlib.sha256(preflight_path.read_bytes()).hexdigest(),
                    "metadata_query_batches": {"PubMed": pubmed_batch_receipts,
                                               "DORA": dora_batch_receipts}})
    Path(str(prefix) + "-differences.json").write_text(json.dumps(differences, indent=2) + "\n")
    Path(str(prefix) + "-field-differences.json").write_text(json.dumps(field_differences, indent=2) + "\n")
    Path(str(prefix) + "-consumer-gains.json").write_text(json.dumps(consumer_gain_receipt, indent=2) + "\n")
    Path(str(prefix) + "-consumer-gain-differences.json").write_text(json.dumps(consumer_gain_differences, indent=2) + "\n")
    Path(str(prefix) + "-archive-metadata-differences.json").write_text(json.dumps(archive_metadata_differences, indent=2) + "\n")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "counts": receipt["counts"], "difference_counts": receipt["difference_counts"]}))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
