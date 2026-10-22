"""Compare an isolated canary's processed retained keys with committed members.

Run the DAX query printed by ``--print-query`` via Power BI ExecuteQueries on
the isolated model, save the complete JSON response privately, then verify it.
This is a read-only data gate; it does not admit publications into the registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from scripts.reconcile_publication_sources import _member_identity, retained_rows
except ModuleNotFoundError:
    from reconcile_publication_sources import _member_identity, retained_rows


QUERY = '''EVALUATE
UNION(
    SELECTCOLUMNS('RetainedPubMedPublications', "Source", "PubMed", "SourceID", 'RetainedPubMedPublications'[PMID]),
    SELECTCOLUMNS('RetainedDoraPublications', "Source", "DORA", "SourceID", 'RetainedDoraPublications'[DORAKey])
)'''


def model_rows(payload: object) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("results"), list) or len(payload["results"]) != 1:
        raise ValueError("one successful ExecuteQueries result required")
    result = payload["results"][0]
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("tables"), list) or len(result["tables"]) != 1:
        raise ValueError("one successful ExecuteQueries table required")
    table = result["tables"][0]
    if not isinstance(table, dict) or table.get("error") or not isinstance(table.get("rows"), list):
        raise ValueError("complete ExecuteQueries rows required")
    rows = table["rows"]
    if not all(isinstance(row, dict) and set(row) == {"[Source]", "[SourceID]"} for row in rows):
        raise ValueError("model rows require exactly bracketed Source and SourceID aliases")
    return rows


def verify(model: list[dict], archive: list[dict]) -> tuple[dict, dict]:
    expected = set()
    for row in archive:
        identity = _member_identity(row)
        if identity in expected:
            raise ValueError("duplicate committed archive member")
        expected.add(identity)
    observed = set()
    duplicate = set()
    invalid = 0
    counts = {"PubMed": 0, "DORA": 0}
    for row in model:
        try:
            identity = _member_identity({"Source": row["[Source]"], "SourceID": row["[SourceID]"]})
            if identity[0] == "PubMed" and int(identity[1]) <= 0:
                raise ValueError("PubMed source ID must be positive")
        except ValueError:
            invalid += 1
            continue
        counts[identity[0]] += 1
        if identity in observed:
            duplicate.add(identity)
        observed.add(identity)
    missing, extra = expected - observed, observed - expected
    receipt = {
        "kind": "retained_canary_model_key_parity_v1",
        "status": "PASS" if len(model) == 1970 and len(expected) == 1970 and counts == {"PubMed": 1261, "DORA": 709} and not (invalid or duplicate or missing or extra) else "FAIL",
        "counts": {"model_rows": len(model), "archive_rows": len(archive), "model_pubmed": counts["PubMed"], "model_dora": counts["DORA"], "invalid_rows": invalid, "duplicate_keys": len(duplicate), "missing_keys": len(missing), "extra_keys": len(extra)},
        "scope": "isolated canary processed rows only; not report-bound model, registry admission, or refresh-history acceptance",
    }
    differences = {"duplicate": sorted(duplicate), "missing": sorted(missing), "extra": sorted(extra)}
    return receipt, differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-query", action="store_true")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--differences", type=Path)
    args = parser.parse_args()
    if args.print_query:
        print(QUERY)
        return 0
    if not args.model or not args.archive:
        parser.error("--model and --archive are required")
    private = (Path(__file__).resolve().parents[1] / "private").resolve()
    if args.differences and not args.differences.resolve().is_relative_to(private):
        parser.error("detailed key differences must stay under ignored private/")
    paths = [p.resolve() for p in (args.model, args.archive, args.output, args.differences) if p]
    if len(paths) != len(set(paths)):
        parser.error("input and output paths must be distinct")
    model_bytes, archive_bytes = args.model.read_bytes(), args.archive.read_bytes()
    archive = retained_rows(json.loads(archive_bytes))
    receipt, differences = verify(model_rows(json.loads(model_bytes)), archive)
    receipt["inputs"] = {"model_sha256": hashlib.sha256(model_bytes).hexdigest(), "archive_sha256": hashlib.sha256(archive_bytes).hexdigest()}
    rendered = json.dumps(receipt, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    if args.differences:
        args.differences.write_text(json.dumps(differences, indent=2) + "\n")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
