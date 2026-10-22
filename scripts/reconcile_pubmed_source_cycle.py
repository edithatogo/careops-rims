"""Bind a completed current PubMed source cycle to archive and review evidence.

This is a local, read-only reconciliation. It verifies the request-correlated
current source pages and DAX receipt against the committed archive members,
the exact-request retained/archive acceptance, and the existing human-review
packet. It never admits a key or writes to a tenant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = (ROOT / "private/ops").resolve()
sys.path.insert(0, str(ROOT))
from scripts.build_native_commit_package import (
    configured_search_profile, current_validation_query, _query_projection_validation_query,
    _validate_query_projection_proof, validate_pubmed_source_table_aliases,
    validate_source_page_receipt, validate_processing_chain,
)
from scripts.capture_report_bound_source_union import (
    classify_current_source_differences, project_current_pubmed_efetch,
)
from scripts.reconcile_publication_sources import retained_rows
from scripts.verify_retained_canary_metadata_values import (
    SOURCES as METADATA_SOURCES,
    expected as expected_archive_metadata,
    verify as verify_metadata_values,
)

TABLES = ["PubMedPublications", "PubMedMetadataChunks", "PubMedAuthorEvidence",
          "SearchAudit", "PubMedIngestionAudit"]
DECISION_FIELDS = ("affiliation_attribution", "attributed_author", "decision_reason",
                   "evidence_refs", "registry_disposition", "reviewed_at_utc",
                   "reviewer", "source_eligibility")


def private_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PRIVATE):
        raise ValueError("all reconciliation evidence must remain under ignored private/ops")
    return resolved


def load(path: Path) -> tuple[dict, bytes]:
    resolved = private_file(path)
    raw = resolved.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{resolved.name} must contain a JSON object")
    return value, raw


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def key_from_review(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("pubmed:"):
        raise ValueError("review evidence requires canonical pubmed: SourceKey values")
    pmid = value[7:]
    if not pmid.isascii() or not pmid.isdecimal() or pmid.startswith("0"):
        raise ValueError("review evidence contains an invalid PubMed key")
    return pmid


def one_row(receipt: dict) -> dict:
    results = receipt.get("body", {}).get("results")
    tables = results[0].get("tables") if isinstance(results, list) and len(results) == 1 else None
    rows = tables[0].get("rows") if isinstance(tables, list) and len(tables) == 1 else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("current DAX validation must contain exactly one summary row")
    return rows[0]


def verify_current_validation(receipt: dict, generation: dict, extraction: dict) -> dict:
    aliases = validate_pubmed_source_table_aliases(receipt.get("source_table_aliases"))
    search_profile = receipt.get("search_profile")
    if search_profile is not None and search_profile != configured_search_profile():
        raise ValueError("current validation receipt uses a different configured PubMed search profile")
    processing_chain = extraction.get("ProcessingChain")
    query_projection = None
    if isinstance(processing_chain, dict) and processing_chain.get("mode") == "query_projection":
        query_projection = _validate_query_projection_proof(
            extraction.get("QueryProjection"), processing_chain)
        if (receipt.get("mode") != "query_projection"
                or receipt.get("query_outputs_ready") is not True
                or receipt.get("query_projection") != query_projection
                or generation.get("mode") != "query_projection"
                or generation.get("query_outputs_ready") is not True):
            raise ValueError("current validation query-projection proof/mode differs from the source generation")
        query = _query_projection_validation_query(query_projection, search_profile)
    else:
        query = current_validation_query("PubMed", search_profile, aliases)
    if (receipt.get("kind") != "native_current_validation_v1"
            or receipt.get("http") != 200 or receipt.get("refresh_status") != "Completed"
            or receipt.get("query_sha256") != hashlib.sha256(query.encode()).hexdigest()
            or (query_projection is not None and receipt.get("query") != query)
            or (aliases is not None and receipt.get("query") != query)
            or ("query" in receipt and receipt.get("query") != query)
            or receipt.get("request_id") != generation.get("refreshRequestId")
            or receipt.get("model_id") != generation.get("modelId")):
        raise ValueError("current validation receipt is not bound to this completed source cycle")
    if processing_chain is None:
        if "processing_chain" in generation or "processing_chain" in receipt:
            raise ValueError("current validation processing chain is not bound to source-page extraction")
    else:
        if (generation.get("processing_chain") != processing_chain
                or receipt.get("processing_chain") != processing_chain):
            raise ValueError("generation, source pages and current validation processing chains differ")
        validate_processing_chain(processing_chain, generation)
    row = one_row(receipt)
    integer_fields = (
        "[CurrentRows]", "[VerifiedPubMedRecords]", "[DistinctCurrentKeys]",
        "[MetadataRows]", "[DistinctMetadataKeys]", "[MissingMetadataKeys]",
        "[UnexpectedMetadataKeys]", "[MetadataStructureFailures]", "[MetadataEncodingFailures]",
        "[MetadataCharacters]", "[AuthorEvidenceRows]", "[DistinctAuthorEvidenceKeys]",
        "[OrphanAuthorEvidencePMIDs]", "[InvalidAuthorEvidenceIndices]",
        "[AuthorEvidenceCountFailures]", "[AuthorEvidenceNameFailures]",
        "[SearchAuditRows]", "[SearchAuditFailures]", "[AuditRows]",
        "[AuditCheckCount]", "[AuditNullCount]", "[AuditFailures]",
    )
    if any(type(row.get(field)) is not int for field in integer_fields):
        raise ValueError("current validation summary has missing or noninteger counts")
    keys = extraction["_publication_keys"]
    expected_keys = json.dumps(sorted(keys), ensure_ascii=True, separators=(",", ":"))
    projection_audit = extraction.get("QueryProjectionAudit", {})
    expected_search_audit_rows = (len(projection_audit.get("SearchAuditKeys", []))
                                  if processing_chain is not None
                                  and processing_chain.get("mode") == "query_projection" else 1)
    counts = {
        "[CurrentRows]": len(keys), "[VerifiedPubMedRecords]": len(keys),
        "[DistinctCurrentKeys]": len(keys), "[CurrentKeysJSON]": expected_keys,
        "[MetadataRows]": extraction["MetadataChunkCount"],
        "[DistinctMetadataKeys]": len(keys), "[MetadataKeysJSON]": expected_keys,
        "[MetadataCharacters]": extraction["MetadataPayloadCharacters"],
        "[AuthorEvidenceRows]": extraction["AuthorEvidenceRowCount"],
        "[DistinctAuthorEvidenceKeys]": extraction["AuthorEvidenceRowCount"],
        "[SearchAuditRows]": expected_search_audit_rows, "[AuditRows]": row["[AuditCheckCount]"],
    }
    if any(row.get(field) != value for field, value in counts.items()):
        raise ValueError("current-model DAX counts or keys disagree with paged source extraction")
    if any(row[field] != 0 for field in integer_fields if field.endswith("Failures]")
           or field in ("[MissingMetadataKeys]", "[UnexpectedMetadataKeys]",
                        "[OrphanAuthorEvidencePMIDs]", "[InvalidAuthorEvidenceIndices]",
                        "[AuditNullCount]")):
        raise ValueError("current-model DAX reports an ingestion, metadata, author, SearchAudit or audit failure")
    names = json.loads(row.get("[AuditCheckNamesJSON]", "null"))
    failures = json.loads(row.get("[AuditFailureNamesJSON]", "null"))
    if (not isinstance(names, list) or len(names) != row["[AuditCheckCount]"]
            or row["[AuditCheckCount]"] <= 0 or row["[AuditRows]"] <= 0
            or len(set(names)) != len(names) or failures != []):
        raise ValueError("current ingestion-audit names or failures do not reconcile")
    if query_projection is not None:
        audit = extraction.get("QueryProjectionAudit", {})
        if (row.get("[SearchAuditKeysJSON]") != json.dumps(audit.get("SearchAuditKeys"), separators=(",", ":"))
                or row.get("[AuditCheckNamesJSON]") != json.dumps(audit.get("IngestionAuditChecks"), separators=(",", ":"))
                or row.get("[SearchAuditWarnings]") != audit.get("SearchAuditWarnings")
                or row.get("[SearchAuditWarningRows]") != audit.get("SearchAuditWarningRows")):
            raise ValueError("combined query-projection audit differs from bounded native audit pages")
    return {
        "CurrentRows": len(keys), "MetadataChunks": extraction["MetadataChunkCount"],
        "MetadataCharacters": extraction["MetadataPayloadCharacters"],
        "AuthorEvidenceRows": extraction["AuthorEvidenceRowCount"],
        "SearchAuditRows": row["[SearchAuditRows]"],
        "IngestionAuditChecks": row["[AuditCheckCount]"],
        "AllFailureCountsZero": True,
        **({"ProcessingChain": processing_chain} if processing_chain is not None else {}),
    }


def verify_current_archive_metadata(source_pages: dict, archive_dir: Path,
                                    validated_dir: Path, overlap_keys: set[str],
                                    pubmed_efetch: dict | None = None) -> tuple[dict, list[dict]]:
    expected_all = expected_archive_metadata(archive_dir, validated_dir, "PubMed")
    if set(expected_all) != overlap_keys:
        raise ValueError("validated PubMed metadata keys differ from the current/archive overlap")
    _summary_table, _chunk_table, key_name, fields = METADATA_SOURCES["PubMed"]
    source = source_pages.get("sources", {}).get("PubMedPublications", {})
    pages = source.get("pages") if isinstance(source, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ValueError("current source publication pages are missing")
    rows = []
    for page in pages:
        body = page.get("body", {}) if isinstance(page, dict) else {}
        results = body.get("results") if isinstance(body, dict) else None
        tables = results[0].get("tables") if isinstance(results, list) and len(results) == 1 else None
        page_rows = tables[0].get("rows") if isinstance(tables, list) and len(tables) == 1 else None
        if not isinstance(page_rows, list):
            raise ValueError("current source summary page has malformed rows")
        for row in page_rows:
            if not isinstance(row, dict) or not isinstance(row.get(f"[{key_name}]"), str):
                raise ValueError("current source summary row lacks its PMID")
            if row[f"[{key_name}]"] in overlap_keys:
                rows.append({alias: row[alias] for alias in (f"[{key_name}]", *(f"[{field}]" for field in fields)) if alias in row})
    expected = {key: expected_all[key] for key in overlap_keys}
    result, differences = verify_metadata_values(
        {"results": [{"tables": [{"rows": rows}]}]}, expected, "PubMed")
    mismatch_items = [item for item in differences if item.get("kind") == "value_mismatch"]
    current_updates, unresolved = [], mismatch_items
    if mismatch_items and pubmed_efetch:
        changed_keys = {item.get("source_id") for item in mismatch_items}
        official = pubmed_efetch.get("projection")
        if not isinstance(official, dict) or set(official) != changed_keys:
            raise ValueError("saved official EFetch evidence does not cover the exact changed PubMed key set")
        raw_path = private_file(Path(pubmed_efetch.get("raw_path", "")))
        raw = raw_path.read_bytes()
        if (pubmed_efetch.get("kind") != "pubmed_current_archive_date_drift_efetch_v1"
                or pubmed_efetch.get("url") != "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                or hashlib.sha256(raw).hexdigest() != pubmed_efetch.get("response_sha256")
                or project_current_pubmed_efetch(raw) != official
                or pubmed_efetch.get("http") != 200
                or pubmed_efetch.get("requested_count") != len(changed_keys)
                or pubmed_efetch.get("returned_count") != len(changed_keys)
                or pubmed_efetch.get("requested_key_sha256") != hashlib.sha256(
                    "\n".join(sorted(changed_keys)).encode()).hexdigest()):
            raise ValueError("saved official EFetch receipt, raw response, projection or exact-key binding is invalid")
        current_updates, unresolved = classify_current_source_differences(
            {"results": [{"tables": [{"rows": rows}]}]}, mismatch_items, official)
        resolved = {(item["source_id"], item["field"]) for item in current_updates}
        for item in differences:
            if (item.get("source_id"), item.get("field")) in resolved:
                item["raw_kind"] = item["kind"]
                item["kind"] = "current_source_update"
        result["substantive_differences"] = len(unresolved)
        normalized = result["engine_text_normalizations"]
        updates = len(current_updates)
        result["current_source_updates"] = updates
        result["status"] = ("FAIL" if unresolved else
            "PASS_WITH_ENGINE_NORMALIZATION_AND_CURRENT_SOURCE_UPDATES" if normalized and updates else
            "PASS_WITH_CURRENT_SOURCE_UPDATES" if updates else
            "PASS_WITH_ENGINE_NORMALIZATION" if normalized else "PASS")
    result["raw_substantive_differences"] = len(mismatch_items)
    result["source_date_evolution"] = _summarize_source_date_evolution(rows, expected, current_updates,
                                                                         unresolved, pubmed_efetch)
    result["difference_sha256"] = hashlib.sha256(
        json.dumps(differences, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result["scope"] = "selected current-source bibliography/raw-date fields for exact keys shared with the validated committed archive; current-only keys remain separately review-gated; any changed current PubMed value is accepted only when the exact field and key match a saved official EFetch"
    return result, differences


def _canonical_pubmed_date(value: object) -> tuple[str, int | None, int | None] | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value.strip())
    match = re.fullmatch(r"(\d{4})\s+([A-Za-z]{3})\s+(\d{1,2})", text)
    if match:
        year, month_text, day = match.groups()
        months = {name.lower(): index for index, name in enumerate(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
        month = months.get(month_text.lower())
        if month:
            return ("day", int(year), month * 100 + int(day))
    match = re.fullmatch(r"(\d{4})\s+([A-Za-z]{3})", text)
    months = {name.lower(): index for index, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
    if match and match.group(2).lower() in months:
        return ("month", int(match.group(1)), months[match.group(2).lower()])
    if not text:
        return None
    return None


def _summarize_source_date_evolution(rows: list[dict], expected: dict,
                                     updates: list[dict], unresolved: list[dict],
                                     evidence: dict | None) -> dict:
    date_updates = [item for item in updates if item.get("field") in
                    {"PublicationDateRaw", "PublicationDatePrecision", "PublicationYear", "OnlineDateRaw"}]
    if not date_updates:
        return {"status": "NOT_NEEDED", "record_count": 0, "archived_online_date_preserved_count": 0}
    actual = {row.get("[PMID]"): row for row in rows}
    official = evidence.get("projection", {}) if isinstance(evidence, dict) else {}
    date_ids = {item.get("source_id") for item in date_updates}
    unresolved_date_ids = {item.get("source_id") for item in unresolved
                           if item.get("field") in {"PublicationDateRaw", "PublicationDatePrecision",
                                                     "PublicationYear", "OnlineDateRaw"}}
    all_date_ids = date_ids | unresolved_date_ids
    preserved = 0
    for key in date_ids:
        if key in unresolved_date_ids:
            continue
        current, archive, pubmed = actual.get(key, {}), expected.get(key, {}), official.get(key, {})
        if (current.get("[OnlineDateRaw]") == pubmed.get("OnlineDateRaw")
                and type(current.get("[PublicationYear]")) is int
                and current.get("[PublicationYear]") == pubmed.get("PublicationYear")
                and current.get("[PublicationYear]") == archive.get("PublicationYear")
                and _canonical_pubmed_date(archive.get("PublicationDateRaw"))
                    == _canonical_pubmed_date(pubmed.get("OnlineDateRaw"))):
            preserved += 1
    return {"status": "CORROBORATED" if preserved == len(all_date_ids) else "INCOMPLETE_CORROBORATION",
            "record_count": len(all_date_ids),
            "archived_online_date_preserved_count": preserved,
            "updated_fields": sorted({item.get("field") for item in date_updates})}


def verify_review_reconciliation(current_only: set[str], archive_bytes: bytes,
                                 worklist: dict, worklist_path: Path, worklist_bytes: bytes,
                                 packet: dict, registry: dict, registry_path: Path,
                                 registry_bytes: bytes) -> dict:
    if (worklist.get("kind") != "isolated_pubmed_current_only_review_worklist_v1"
            or worklist.get("archive_export_sha256") != hashlib.sha256(archive_bytes).hexdigest()
            or worklist.get("current_only_count") != len(current_only)):
        raise ValueError("current-only review worklist is not bound to this archive and candidate count")
    worklist_keys = {key_from_review(item.get("source_id")) for item in worklist.get("items", [])}
    if worklist_keys != current_only:
        raise ValueError("refreshed source current-only keys disagree with the review worklist")

    if (packet.get("kind") != "pubmed_current_only_human_decision_packet_v1"
            or packet.get("status") != "AWAITING_HUMAN_REVIEW"
            or packet.get("source_refresh_request_id") != worklist.get("source_refresh_request_id")):
        raise ValueError("current-only decision packet lost its upstream review binding or pending state")
    packet_counts = packet.get("counts", {})
    packet_keys = set()
    packet_by_key = {}
    for item in packet.get("items", []):
        key = key_from_review(item.get("source_key"))
        if key_from_review(item.get("source_id")) != key or item.get("admission") != "NOT_ADMITTED":
            raise ValueError("human decision packet contains a mismatched or admitted candidate")
        decisions = item.get("human_decision")
        if (not isinstance(decisions, dict) or set(decisions) != set(DECISION_FIELDS)
                or any(value not in (None, "", []) for value in decisions.values())):
            raise ValueError("candidate has a human decision; preserve the decision gate for review")
        packet_keys.add(key)
        packet_by_key[key] = item
    if packet_keys != current_only or packet_counts.get("candidates") != len(current_only) or packet_counts.get("admitted") != 0:
        raise ValueError("current-only decision packet does not cover the exact refreshed candidate set")

    registry_items = registry.get("items", [])
    if not isinstance(registry_items, list):
        raise ValueError("registry readback items must be an array")
    registry_by_key = {}
    for item in registry_items:
        key = key_from_review(item.get("source_key"))
        if key in registry_by_key or type(item.get("registry_match")) is not bool:
            raise ValueError("registry readback contains duplicate candidates or an unknown match state")
        registry_by_key[key] = item
    registry_keys = set(registry_by_key)
    exact_matches = sum(item["registry_match"] for item in registry_by_key.values())
    registry_absent = len(registry_by_key) - exact_matches
    if (registry.get("kind") != "pubmed_candidate_exact_registry_identity_readback_v1"
            or registry.get("read_only") is not True or registry.get("mutated_tenant") is not False
            or registry_keys != current_only
            or registry.get("summary", {}).get("matched_by_exact_source_key") != exact_matches
            or registry.get("summary", {}).get("unmatched") != registry_absent
            or packet_counts.get("exact_existing_registry_matches") != exact_matches
            or packet_counts.get("registry_absent") != registry_absent):
        raise ValueError("exact-key registry readback does not match the pending candidate set")
    for key, registry_item in registry_by_key.items():
        candidate = packet_by_key[key]
        if (candidate.get("registry_exact_sourcekey_match") is not registry_item["registry_match"]
                or candidate.get("registry_canonical_key") != registry_item.get("registry_canonical_key")):
            raise ValueError("human review packet registry state differs from the exact-key readback")

    # Recheck every SHA-256 input binding and tie the worklist and registry
    # entries to the exact files passed to this reconciliation.
    packet_inputs = packet.get("inputs", {})
    for name, ref in packet_inputs.items():
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", ""))):
            raise ValueError("human decision packet input binding is malformed")
        evidence_path = private_file(ROOT / ref["path"])
        if hashlib.sha256(evidence_path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("human decision packet input hash drifted")
    expected_bindings = {
        "worklist": (worklist_path.resolve(), hashlib.sha256(worklist_bytes).hexdigest()),
        "exact_registry_identity": (registry_path.resolve(), hashlib.sha256(registry_bytes).hexdigest()),
    }
    for name, (expected_path, expected_hash) in expected_bindings.items():
        ref = packet_inputs.get(name, {})
        if (not isinstance(ref, dict) or not isinstance(ref.get("path"), str)
                or (ROOT / ref["path"]).resolve() != expected_path
                or ref.get("sha256") != expected_hash):
            raise ValueError(f"decision packet is not bound to the supplied {name} receipt")

    return {
        "candidate_count": len(current_only),
        "candidate_keyset_sha256": digest(sorted(current_only)),
        "worklist_keyset_sha256": digest(sorted(worklist_keys)),
        "packet_keyset_sha256": digest(sorted(packet_keys)),
        "registry_keyset_sha256": digest(sorted(registry_keys)),
        "candidate_keyset_matches_worklist_and_packet": True,
        "candidate_keys_admitted": 0,
        "human_review_decisions_present": False,
        "exact_registry_matches": exact_matches,
        "registry_absent_candidates": registry_absent,
        "prior_review_refresh_request_id": worklist.get("source_refresh_request_id"),
    }


def reconcile(inputs: dict[str, Path]) -> dict:
    automated = inputs.get("automated") is True
    source_pages, source_bytes = load(inputs["source_pages"])
    generation, generation_bytes = load(inputs["generation"])
    current_validation, validation_bytes = load(inputs["current_validation"])
    archive, archive_bytes = load(inputs["archive"])
    retained, retained_bytes = load(inputs["retained_acceptance"])
    if not automated:
        worklist, worklist_bytes = load(inputs["worklist"])
        packet, packet_bytes = load(inputs["decision_packet"])
        registry, registry_bytes = load(inputs["registry_readback"])
    pubmed_efetch = None
    pubmed_efetch_bytes = None
    if inputs.get("pubmed_efetch_receipt"):
        pubmed_efetch, pubmed_efetch_bytes = load(inputs["pubmed_efetch_receipt"])

    if (generation.get("refreshStatus") != "Completed" or generation.get("refreshComplete") is not True
            or generation.get("extractionComplete") is not True):
        raise ValueError("completed source generation receipt required")
    extraction = validate_source_page_receipt(source_pages, generation)
    processing_chain = extraction.get("ProcessingChain")
    if archive.get("kind") != "committed_archive_source_members_v1" or archive.get("complete") is not True or archive.get("next_links") != []:
        raise ValueError("complete committed archive source-member receipt required")
    members = retained_rows(archive)
    archive_pubmed = set()
    archive_dora = set()
    for member in members:
        source, source_id = member.get("Source"), member.get("SourceID")
        if source == "PubMed":
            if not isinstance(source_id, str) or not source_id.isascii() or not source_id.isdecimal() or source_id.startswith("0"):
                raise ValueError("committed archive contains an invalid PubMed identity")
            archive_pubmed.add(source_id)
        elif source == "DORA":
            if not isinstance(source_id, str) or not source_id.startswith("DORA:") or not source_id[5:]:
                raise ValueError("committed archive contains an invalid DoRA identity")
            archive_dora.add(source_id)
        else:
            raise ValueError("committed archive contains an unsupported source")
    if len(archive_pubmed) + len(archive_dora) != len(members):
        raise ValueError("committed archive contains duplicate source identities")

    current = set(extraction["_publication_keys"])
    current_only = current - archive_pubmed
    archive_only = archive_pubmed - current
    if archive_only and not automated:
        raise ValueError("the refreshed current PubMed source is missing committed archive keys")
    if not automated:
        current_metadata, current_metadata_differences = verify_current_archive_metadata(
            source_pages, inputs["archive_dir"], inputs["validated_dir"], current & archive_pubmed,
            pubmed_efetch)

    validation_summary = verify_current_validation(current_validation, generation, extraction)
    validation_aliases = validate_pubmed_source_table_aliases(
        current_validation.get("source_table_aliases"))
    if validation_aliases != extraction.get("_source_table_aliases"):
        raise ValueError("source-page and current-validation receipts use different physical table contracts")
    if (inputs.get("source_table_aliases") is not None
            and validate_pubmed_source_table_aliases(inputs["source_table_aliases"]) != validation_aliases):
        raise ValueError("explicit source table aliases disagree with native validation receipt")
    request_id = generation["refreshRequestId"]
    model_id = generation["modelId"]
    if (retained.get("status") not in ("PASS", "PASS_WITH_ENGINE_NORMALIZATION")
            or retained.get("refresh_status") != "Completed"
            or retained.get("target_scope") != "isolated"
            or retained.get("binding", {}).get("request_id") != request_id
            or retained.get("binding", {}).get("dataset_id") != model_id
            or retained.get("requested_refresh_tables") != TABLES):
        raise ValueError("retained/archive acceptance is not correlated to this exact completed refresh")
    key_result = retained.get("key_parity", {})
    field_result = retained.get("field_integrity", {})
    key_counts = key_result.get("counts", {})
    field_counts = field_result.get("counts", {})
    if (key_result.get("status") != "PASS" or field_result.get("status") != "PASS"
            or key_counts.get("archive_rows") != len(members)
            or key_counts.get("model_rows") != len(members)
            or key_counts.get("model_pubmed") != len(archive_pubmed)
            or key_counts.get("model_dora") != len(archive_dora)
            or any(key_counts.get(name) != 0 for name in ("invalid_rows", "duplicate_keys", "missing_keys", "extra_keys"))
            or field_counts.get("rows_with_field_issues") != 0
            or field_counts.get("missing_archive_members") != 0):
        raise ValueError("retained/archive key parity or field integrity did not pass")
    metadata = retained.get("metadata_values", {})
    for source, expected_rows in (("PubMed", len(archive_pubmed)), ("DORA", len(archive_dora))):
        result = metadata.get(source, {})
        if (result.get("status") not in ("PASS", "PASS_WITH_ENGINE_NORMALIZATION")
                or result.get("expected_rows") != expected_rows or result.get("model_rows") != expected_rows
                or result.get("substantive_differences") != 0
                or result.get("differences") != result.get("engine_text_normalizations")):
            raise ValueError(f"validated archive {source} metadata comparison has substantive differences")
    fixtures = retained.get("native_fixture_validation", {})
    fixture_counts = fixtures.get("counts", {})
    if (fixtures.get("status") != "PASS" or type(fixture_counts.get("expected")) is not int
            or fixture_counts["expected"] <= 0
            or fixture_counts.get("returned") != fixture_counts["expected"]
            or fixture_counts.get("passed") != fixture_counts["expected"]):
        raise ValueError("native retention fixture acceptance did not pass all expected cases")

    if automated:
        from scripts.publication_retained_cycle import prepare
        from scripts.publication_policy import load_policy
        state, checked = prepare(source_pages, generation, current_validation)
        return {
            "kind": "pubmed_automated_source_cycle_reconciliation_v1",
            "status": "PASS_POLICY_READY", "policy": load_policy(),
            "refresh_request_id": request_id, "model_id": model_id,
            "input_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in (
                ("source_pages", source_bytes), ("generation", generation_bytes),
                ("current_validation", validation_bytes), ("archive", archive_bytes),
                ("retained_acceptance", retained_bytes))},
            "current_pubmed_keys": len(current), "committed_archive_pubmed_keys": len(archive_pubmed),
            "current_archive_overlap": len(current & archive_pubmed),
            "new_source_keys_automatically_eligible": len(current_only),
            "archive_keys_absent_from_current_retained": sorted(archive_only),
            "next_retained_pubmed_keys": sorted(current | archive_pubmed),
            "retained_dora_keys_unchanged": len(archive_dora),
            "automatic_policy_outcomes": [state["versions"][index] for index in state["latest"].values()],
            "retained_archive_rows": len(members), "native_fixture_cases": fixture_counts["passed"],
            "source_validation": checked, "current_validation": validation_summary,
            **({"processing_chain": processing_chain} if processing_chain is not None else {}),
            "manual_record_approval_required": False, "registry_written": False,
            "native_retention_committed": False,
            "scope": "Validated automatic source-cycle preparation; preserve historical versions and distinct source identities; native commit/replay remains separate",
        }

    review = verify_review_reconciliation(current_only, archive_bytes, worklist,
                                          inputs["worklist"], worklist_bytes,
                                          packet, registry, inputs["registry_readback"],
                                          registry_bytes)

    return {
        "kind": "pubmed_current_cycle_archive_review_reconciliation_v1",
        "status": "PASS_REVIEW_REQUIRED" if current_only or current_metadata["substantive_differences"] else "PASS",
        "review_required_reasons": [reason for reason, applies in (
            ("CURRENT_ONLY_PUBMED_KEYS", bool(current_only)),
            ("CURRENT_SOURCE_ARCHIVE_METADATA_DIFFERENCES", bool(current_metadata["substantive_differences"])),
        ) if applies],
        "refresh_request_id": request_id,
        "model_id": model_id,
        "generation": extraction["Generation"],
        "source_page_receipt_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "generation_receipt_sha256": hashlib.sha256(generation_bytes).hexdigest(),
        "current_validation_receipt_sha256": hashlib.sha256(validation_bytes).hexdigest(),
        "retained_acceptance_receipt_sha256": hashlib.sha256(retained_bytes).hexdigest(),
        "archive_source_member_receipt_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "validated_archive_metadata_receipt_sha256": hashlib.sha256((inputs["validated_dir"] / "validated-receipt.json").read_bytes()).hexdigest(),
        "pubmed_efetch_receipt_sha256": hashlib.sha256(pubmed_efetch_bytes).hexdigest() if pubmed_efetch_bytes else None,
        "worklist_sha256": hashlib.sha256(worklist_bytes).hexdigest(),
        "decision_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "registry_readback_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "current_pubmed_keys": len(current),
        "committed_archive_pubmed_keys": len(archive_pubmed),
        "current_archive_overlap": len(current & archive_pubmed),
        "current_only_candidates": review["candidate_count"],
        "current_only_keyset_sha256": review["candidate_keyset_sha256"],
        "archive_keys_missing_from_current": len(archive_only),
        "current_source_archive_metadata": current_metadata,
        "current_source_archive_metadata_differences": current_metadata_differences,
        "current_source_archive_metadata_substantive_differences": current_metadata["substantive_differences"],
        "candidate_keyset_matches_worklist_and_packet": review["candidate_keyset_matches_worklist_and_packet"],
        "candidate_keys_admitted": review["candidate_keys_admitted"],
        "human_review_decisions_present": review["human_review_decisions_present"],
        "exact_registry_matches": review["exact_registry_matches"],
        "registry_absent_candidates": review["registry_absent_candidates"],
        "prior_review_refresh_request_id": review["prior_review_refresh_request_id"],
        "retained_archive_rows": len(members),
        "retained_key_parity": "PASS",
        "retained_field_integrity": "PASS",
        "validated_archive_metadata_substantive_differences": 0,
        "engine_text_normalizations": sum(metadata[s].get("engine_text_normalizations", 0) for s in ("PubMed", "DORA")),
        "native_fixture_cases": fixture_counts["passed"],
        "current_validation": validation_summary,
        **({"processing_chain": processing_chain} if processing_chain is not None else {}),
        "scope": "isolated report-unbound canary; no registry admission or tenant mutation; candidate source eligibility, affiliation and registry disposition remain human review",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-pages", "generation", "current-validation", "archive",
                 "archive-dir", "validated-dir",
                 "retained-acceptance", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    for name in ("worklist", "decision-packet", "registry-readback"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--legacy-human-review", action="store_true", help="Historical evidence replay only; routine intake is automatic")
    parser.add_argument("--pubmed-efetch-receipt", type=Path)
    args = parser.parse_args()
    inputs = {name.replace("-", "_"): private_file(getattr(args, name.replace("-", "_")))
              for name in ("source-pages", "generation", "current-validation", "archive",
                           "archive-dir", "validated-dir",
                           "retained-acceptance")}
    inputs["automated"] = not args.legacy_human_review
    if args.legacy_human_review:
        for name in ("worklist", "decision_packet", "registry_readback"):
            if getattr(args, name) is None:
                parser.error("Legacy replay requires worklist, decision packet and registry readback")
            inputs[name] = private_file(getattr(args, name))
    if args.pubmed_efetch_receipt:
        inputs["pubmed_efetch_receipt"] = private_file(args.pubmed_efetch_receipt)
    output = private_file(args.output)
    if output.exists():
        parser.error("output already exists; preserve and reconcile the existing receipt")
    try:
        result = reconcile(inputs)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if inputs["automated"]:
        print(json.dumps({k: result[k] for k in ("status", "current_pubmed_keys", "new_source_keys_automatically_eligible", "manual_record_approval_required", "native_retention_committed")}, indent=2))
        return 0
    print(json.dumps({k: result[k] for k in (
        "status", "current_pubmed_keys", "committed_archive_pubmed_keys",
        "current_archive_overlap", "current_only_candidates", "retained_archive_rows",
        "review_required_reasons", "current_source_archive_metadata_substantive_differences",
        "retained_key_parity", "retained_field_integrity",
        "validated_archive_metadata_substantive_differences", "native_fixture_cases",
        "current_source_archive_metadata",
        "exact_registry_matches", "registry_absent_candidates", "candidate_keyset_matches_worklist_and_packet",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
