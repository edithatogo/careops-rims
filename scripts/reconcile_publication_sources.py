"""Reconcile committed publication source identities with the registry.

Automatic policy is the default: preserve distinct source identities and require
complete key parity without routine human decisions. --membership explicitly
selects the historical reviewed-disposition comparison; it does not establish
that a review occurred. Neither route proves native or operational acceptance.
"""

import argparse
import datetime
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

if __package__:
    from scripts.reconcile_pubmed_registry_keys import key_hash, rows, value
else:
    from reconcile_pubmed_registry_keys import key_hash, rows, value


def _key(row):
    raw = value(row, "SourceKey")
    return str(raw).strip() if raw is not None else ""


def _namespace(key):
    if key.startswith("pubmed:"):
        digits = key[7:]
        if digits and digits.isascii() and digits.isdecimal() and not digits.startswith("0"):
            return "pubmed"
    elif key.startswith("dora:") and key[5:].strip() == key[5:] and key[5:]:
        return "dora"
    raise ValueError(f"noncanonical or unsupported SourceKey {key!r}")


def membership_rows(payload):
    if not isinstance(payload, dict) or payload.get("kind") != "reviewed_archive_member_dispositions_v2":
        raise ValueError("explicit reviewed archive member dispositions v2 kind required")
    provenance = payload.get("review_provenance")
    if not isinstance(provenance, dict) or not all(
        isinstance(provenance.get(name), str) and provenance[name].strip()
        for name in ("reviewer", "reviewed_at_utc", "evidence_ref", "retained_export_sha256")
    ):
        raise ValueError("review provenance and retained export digest required")
    try:
        reviewed_at = datetime.datetime.fromisoformat(provenance["reviewed_at_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at_utc must be an ISO timestamp") from exc
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() != datetime.timedelta(0):
        raise ValueError("reviewed_at_utc must use UTC")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["retained_export_sha256"]):
        raise ValueError("retained_export_sha256 must be a lowercase SHA-256 digest")
    if payload.get("complete") is not True or payload.get("next_links") != []:
        raise ValueError("complete membership with next_links=[] required")
    selected = payload.get("rows")
    if not isinstance(selected, list) or not selected or not all(isinstance(row, dict) for row in selected):
        raise ValueError("nonempty membership rows required")
    if payload.get("row_count") != len(selected):
        raise ValueError("membership row_count must equal rows length")
    return selected


def retained_rows(payload):
    """Accept only a complete, explicitly identified committed archive export."""
    if not isinstance(payload, dict) or payload.get("kind") != "committed_archive_source_members_v1":
        raise ValueError("committed archive source member export kind required")
    if payload.get("complete") is not True or payload.get("next_links") != []:
        raise ValueError("complete retained export with next_links=[] required")
    selected = payload.get("rows")
    if not isinstance(selected, list) or not selected or not all(isinstance(row, dict) for row in selected):
        raise ValueError("nonempty retained export rows required")
    if payload.get("row_count") != len(selected):
        raise ValueError("retained export row_count must equal rows length")
    return selected


def _member_identity(row):
    source, source_id = row.get("Source"), row.get("SourceID")
    if source not in ("PubMed", "DORA") or not isinstance(source_id, str) or not source_id.strip() or source_id != source_id.strip():
        raise ValueError("source member requires valid Source and untrimmed SourceID")
    if source == "DORA" and (not source_id.startswith("DORA:") or not source_id[5:]):
        raise ValueError("DORA member SourceID must retain DORA: identity")
    if source == "PubMed" and (not source_id.isascii() or not source_id.isdecimal() or source_id.startswith("0")):
        raise ValueError("PubMed member SourceID must be a canonical PMID")
    return source, source_id


def _direct_source_key(source, source_id):
    """Translate only the stored source identity, without URL inference."""
    return f"pubmed:{source_id}" if source == "PubMed" else f"dora:{source_id[5:]}"


def reconcile(members, registry_rows, retained_source_rows):
    if not members or not registry_rows or not retained_source_rows:
        raise ValueError("nonempty membership, registry and retained exports required")
    admitted = Counter()
    excluded = []
    registry = Counter()
    blank_registry_rows = 0
    seen_members = set()
    for row in members:
        source, source_id = _member_identity(row)
        if (source, source_id) in seen_members:
            raise ValueError("duplicate retained source member")
        seen_members.add((source, source_id))
        if row.get("ReviewStatus") != "Reviewed" or not isinstance(row.get("ReviewEvidenceRef"), str) or not row["ReviewEvidenceRef"].strip():
            raise ValueError("each disposition requires Reviewed status and evidence reference")
        disposition = row.get("Disposition")
        if disposition == "admitted":
            key = row.get("CanonicalSourceKey")
            if not isinstance(key, str) or not key or key != key.strip():
                raise ValueError("admitted member requires canonical CanonicalSourceKey")
            if "DispositionReason" in row:
                raise ValueError("admitted member must not carry DispositionReason")
            _namespace(key)
            admitted[key] += 1
        elif disposition == "not_admitted":
            if "CanonicalSourceKey" in row:
                raise ValueError("not_admitted member must not carry CanonicalSourceKey")
            reason = row.get("DispositionReason")
            if not isinstance(reason, str) or not reason.strip() or reason != reason.strip():
                raise ValueError("not_admitted member requires a nonblank DispositionReason")
            excluded.append((source, source_id))
        else:
            raise ValueError("each member requires admitted or not_admitted Disposition")
    archive_members = set()
    for row in retained_source_rows:
        identity = _member_identity(row)
        if identity in archive_members:
            raise ValueError("duplicate retained archive source member")
        archive_members.add(identity)
    for row in registry_rows:
        key = _key(row)
        if not key:
            blank_registry_rows += 1
            continue
        _namespace(key)
        registry[key] += 1
    excluded_direct_keys_in_registry = sorted(
        (source, source_id, _direct_source_key(source, source_id))
        for source, source_id in excluded
        if _direct_source_key(source, source_id) in registry
    )
    by_namespace = {}
    for name in ("pubmed", "dora"):
        left = {key for key in admitted if _namespace(key) == name}
        right = {key for key in registry if _namespace(key) == name}
        by_namespace[name] = {
            "admitted_member_rows": sum(count for key, count in admitted.items() if key in left),
            "registry_rows": sum(count for key, count in registry.items() if key in right),
            "missing_in_registry": sorted(left - right),
            "registry_not_in_committed_archive": sorted(right - left),
        }
    report = {
        "disposition_rows": len(members),
        "archive_source_rows": len(retained_source_rows),
        "unreviewed_archive_members": sorted(archive_members - seen_members),
        "review_members_absent_from_archive": sorted(seen_members - archive_members),
        "admitted_member_rows": sum(admitted.values()),
        "not_admitted_member_rows": len(excluded),
        "not_admitted_members": sorted(excluded),
        "not_admitted_direct_keys_in_registry": excluded_direct_keys_in_registry,
        "admitted_canonical_keys": len(admitted),
        "registry_rows": sum(registry.values()),
        "blank_registry_rows": blank_registry_rows,
        "admitted_multi_member_keys": sorted(key for key, count in admitted.items() if count > 1),
        "registry_duplicate_keys": sorted(key for key, count in registry.items() if count != 1),
        "admitted_key_set_sha256": key_hash(admitted),
        "registry_key_set_sha256": key_hash(registry),
        "admitted_key_multiset_sha256": key_hash(admitted, multiplicity=True),
        "registry_key_multiset_sha256": key_hash(registry, multiplicity=True),
        "by_namespace": by_namespace,
    }
    report["archive_disposition_coverage_pass"] = (
        not report["unreviewed_archive_members"]
        and not report["review_members_absent_from_archive"]
    )
    report["committed_archive_to_registry_pass"] = (
        report["archive_disposition_coverage_pass"]
        and not report["registry_duplicate_keys"]
        and not report["not_admitted_direct_keys_in_registry"]
        and all(not section["missing_in_registry"]
                for section in by_namespace.values())
    )
    report["registry_not_in_committed_archive_requires_provenance"] = any(
        section["registry_not_in_committed_archive"] for section in by_namespace.values()
    )
    report["pass"] = report["committed_archive_to_registry_pass"]
    report["status"] = (
        "FAIL" if not report["pass"] else
        "PASS_ARCHIVE_SUBSET_ONLY" if report["registry_not_in_committed_archive_requires_provenance"] else
        "PASS_ARCHIVE_TO_REGISTRY"
    )
    return report


def reconcile_automatic(registry_rows, retained_source_rows):
    """Check complete source-key parity without alias inference or human overlays."""
    if __package__:
        from scripts.publication_policy import load_policy
    else:
        # CLI execution already uses the repository's scripts import convention.
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from scripts.publication_policy import load_policy
    policy = load_policy()
    if not retained_source_rows:
        raise ValueError("nonempty retained export required")
    expected = Counter()
    for row in retained_source_rows:
        source, source_id = _member_identity(row)
        expected[_direct_source_key(source, source_id)] += 1
    if any(count != 1 for count in expected.values()):
        raise ValueError("duplicate retained archive source member")
    registry = Counter()
    blanks = 0
    for row in registry_rows:
        raw = value(row, "SourceKey")
        if raw is None or raw == "":
            blanks += 1
            continue
        if not isinstance(raw, str) or raw != raw.strip():
            raise ValueError("registry SourceKey must be unpadded canonical text")
        _namespace(raw)
        registry[raw] += 1
    report = {
        "policy_version": policy["version"],
        "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
        "comparison_mode": "automatic-source-identity",
        "manual_record_approval_required": False,
        "identity_merge_method": "source-identity-only",
        "archive_source_rows": len(retained_source_rows),
        "registry_rows": sum(registry.values()),
        "blank_registry_rows": blanks,
        "missing_in_registry": sorted(expected.keys() - registry.keys()),
        "registry_not_in_committed_archive": sorted(registry.keys() - expected.keys()),
        "registry_duplicate_keys": sorted(key for key, count in registry.items() if count != 1),
        "expected_key_set_sha256": key_hash(expected),
        "registry_key_set_sha256": key_hash(registry),
        "native_acceptance": False,
    }
    report["pass"] = not any(report[name] for name in (
        "blank_registry_rows", "missing_in_registry",
        "registry_not_in_committed_archive", "registry_duplicate_keys"))
    report["status"] = "PASS_AUTOMATIC_SOURCE_KEY_PARITY" if report["pass"] else "FAIL"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--membership", type=Path, help="Explicit historical reviewed-disposition mode; omitted for automatic policy")
    parser.add_argument("--retained", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    private = (Path(__file__).resolve().parent.parent / "private").resolve()
    if not args.output.resolve().is_relative_to(private):
        parser.error("report must be written below ignored private/")
    try:
        retained_bytes = args.retained.read_bytes()
        digest = hashlib.sha256(retained_bytes).hexdigest()
        archived = retained_rows(json.loads(retained_bytes))
        registry = rows(args.registry)
        if args.membership is None:
            report = reconcile_automatic(registry, archived)
        else:
            membership_payload = json.loads(args.membership.read_text(encoding="utf-8"))
            members = membership_rows(membership_payload)
            if membership_payload["review_provenance"]["retained_export_sha256"] != digest:
                raise ValueError("review provenance retained export digest differs from input bytes")
            report = reconcile(members, registry, archived)
        report["retained_export_sha256"] = digest
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["status"], "archive", report["archive_source_rows"],
          "registry", report["registry_rows"], "report", args.output)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
