"""Compare fresh model PubMed identities with a DEV registry JSON export.

This tool reads exported rows only; it does not query or write the tenant. The
report contains identifiers and therefore must stay below ignored private/.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def rows(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("complete") is not True:
        raise ValueError(f"{path}: complete=true export envelope required")
    if payload.get("next_links") != []:
        raise ValueError(f"{path}: explicit empty next_links required for a complete export")
    selected = payload.get("rows")
    if not isinstance(selected, list) or not all(isinstance(row, dict) for row in selected):
        raise ValueError(f"{path}: expected rows array of objects")
    if "row_count" in payload and payload["row_count"] != len(selected):
        raise ValueError(f"{path}: declared row_count differs from rows")
    return selected


def value(row, name):
    plain = row.get(name)
    bracketed = row.get(f"[{name}]")
    if plain is not None and bracketed is not None and str(plain).strip() != str(bracketed).strip():
        raise ValueError(f"conflicting {name} and [{name}] values in exported row")
    return plain if plain is not None else bracketed


def identity(row, source):
    raw_key = value(row, "SourceKey")
    raw_pmid = value(row, "PMID")
    if raw_key is not None and str(raw_key).strip():
        key = str(raw_key).strip()
        if not key.startswith("pubmed:"):
            if key.lower().startswith("pubmed:"):
                raise ValueError(f"{source}: noncanonical PubMed SourceKey {key!r}")
            return None
        pmid = key.split(":", 1)[1]
    elif source == "model" and raw_pmid is not None and str(raw_pmid).strip():
        pmid = str(raw_pmid).strip()
    else:
        return None
    if not pmid.isascii() or not pmid.isdecimal() or pmid.startswith("0"):
        raise ValueError(f"{source}: invalid PubMed identity {pmid!r}")
    return f"pubmed:{pmid}"


def key_hash(keys, *, multiplicity=False):
    """Stable digest for a reconciled key set or multiset, independent of row order."""
    values = sorted(keys.elements()) if multiplicity else sorted(keys)
    encoded = json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reconcile(model_rows, registry_rows):
    model_keys = Counter(filter(None, (identity(row, "model") for row in model_rows)))
    registry_keys = Counter(filter(None, (identity(row, "registry") for row in registry_rows)))
    model_pmid_mismatches = []
    for row in model_rows:
        key = identity(row, "model")
        if key is None:
            continue
        raw = value(row, "PMID")
        if raw is not None and str(raw).strip() and str(raw).strip() != key.split(":", 1)[1]:
            model_pmid_mismatches.append(key)
    mismatched_pmid = []
    unkeyed_pmid_rows = []
    for row in registry_rows:
        key = identity(row, "registry")
        if key is None:
            if not str(value(row, "SourceKey") or "").strip() and str(value(row, "PMID") or "").strip():
                unkeyed_pmid_rows.append(str(value(row, "PMID")).strip())
            continue
        raw = value(row, "PMID")
        if str(raw).strip() != key.split(":", 1)[1]:
            mismatched_pmid.append(key)
    report = {
        "model_pubmed_rows": sum(model_keys.values()),
        "registry_pubmed_rows": sum(registry_keys.values()),
        "model_duplicate_keys": sorted(key for key, count in model_keys.items() if count != 1),
        "registry_duplicate_keys": sorted(key for key, count in registry_keys.items() if count != 1),
        "missing_in_registry": sorted(model_keys.keys() - registry_keys.keys()),
        "extra_in_registry": sorted(registry_keys.keys() - model_keys.keys()),
        "model_pmid_mismatches": sorted(set(model_pmid_mismatches)),
        "registry_pmid_mismatches": sorted(set(mismatched_pmid)),
        "registry_unkeyed_pmid_rows": sorted(unkeyed_pmid_rows),
        # Counts alone can conceal substitutions. These digests make the exact
        # selected key sets and duplicate-bearing multisets auditable in receipts.
        "model_key_set_sha256": key_hash(model_keys),
        "registry_key_set_sha256": key_hash(registry_keys),
        "model_key_multiset_sha256": key_hash(model_keys, multiplicity=True),
        "registry_key_multiset_sha256": key_hash(registry_keys, multiplicity=True),
    }
    report["pass"] = bool(model_keys and registry_keys) and not any(report[name] for name in (
        "model_duplicate_keys", "registry_duplicate_keys", "missing_in_registry",
        "extra_in_registry", "model_pmid_mismatches", "registry_pmid_mismatches",
        "registry_unkeyed_pmid_rows"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="fresh model query JSON")
    parser.add_argument("--registry", required=True, type=Path, help="fresh full registry JSON")
    parser.add_argument("--output", required=True, type=Path, help="ignored private/ JSON report")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if not output.is_relative_to((root / "private").resolve()):
        parser.error("report must be written below ignored private/")
    try:
        report = reconcile(rows(args.model), rows(args.registry))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS" if report["pass"] else "FAIL", "model", report["model_pubmed_rows"],
          "registry", report["registry_pubmed_rows"], "report", args.output)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
