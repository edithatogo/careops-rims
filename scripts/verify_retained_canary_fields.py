"""Check field integrity on every processed retained-canary row.

Run ``--print-query`` against the isolated model after a terminal successful
refresh. This complements exact key parity; it does not compare full metadata
with the retained files or authorize registry admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

try:
    from scripts.reconcile_publication_sources import _member_identity, retained_rows
except ModuleNotFoundError:
    from reconcile_publication_sources import _member_identity, retained_rows


QUERY = '''EVALUATE
UNION(
    SELECTCOLUMNS('RetainedPubMedPublications', "Source", "PubMed", "SourceID", COALESCE('RetainedPubMedPublications'[PMID], ""), "Title", COALESCE('RetainedPubMedPublications'[Title], ""), "SourceURL", COALESCE('RetainedPubMedPublications'[PubMedURL], ""), "CoverageStatus", ""),
    SELECTCOLUMNS('RetainedDoraPublications', "Source", "DORA", "SourceID", COALESCE('RetainedDoraPublications'[DORAKey], ""), "Title", COALESCE('RetainedDoraPublications'[Title], ""), "SourceURL", COALESCE('RetainedDoraPublications'[DORAURL], ""), "CoverageStatus", COALESCE('RetainedDoraPublications'[CoverageStatus], ""))
)'''
FIELDS = {"[Source]", "[SourceID]", "[Title]", "[SourceURL]", "[CoverageStatus]"}


def model_rows(payload: object) -> list[dict]:
    # Keep the same strict ExecuteQueries envelope as the key verifier.
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("results"), list) or len(payload["results"]) != 1:
        raise ValueError("one successful ExecuteQueries result required")
    result = payload["results"][0]
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("tables"), list) or len(result["tables"]) != 1:
        raise ValueError("one successful ExecuteQueries table required")
    table = result["tables"][0]
    if not isinstance(table, dict) or table.get("error") or not isinstance(table.get("rows"), list):
        raise ValueError("complete ExecuteQueries rows required")
    rows = table["rows"]
    if not all(isinstance(row, dict) and set(row) == FIELDS for row in rows):
        raise ValueError("model rows require exactly five bracketed field aliases")
    return rows


def verify(model: list[dict], archive: list[dict]) -> tuple[dict, dict]:
    expected = {_member_identity(row) for row in archive}
    if len(expected) != len(archive) or len(archive) != 1970:
        raise ValueError("complete unique 1,970-member archive required")
    expected_counts = {source: sum(member[0] == source for member in expected) for source in ("PubMed", "DORA")}
    if expected_counts != {"PubMed": 1261, "DORA": 709}:
        raise ValueError("committed archive source split must be 1,261 PubMed and 709 DORA")
    observed: set[tuple[str, str]] = set()
    issues: list[dict] = []
    observed_counts = {"PubMed": 0, "DORA": 0}
    for row in model:
        source, source_id = _member_identity({"Source": row["[Source]"], "SourceID": row["[SourceID]"]})
        observed_counts[source] += 1
        identity = source, source_id
        errors = []
        if identity in observed:
            errors.append("duplicate_identity")
        observed.add(identity)
        if identity not in expected:
            errors.append("not_in_committed_archive")
        title = row["[Title]"]
        if not isinstance(title, str) or not title.strip():
            errors.append("missing_title")
        url = row["[SourceURL]"]
        if not isinstance(url, str) or not url.strip():
            errors.append("missing_source_url")
        elif source == "DORA" and url != source_id[5:]:
            errors.append("dora_url_identity_mismatch")
        elif source == "PubMed":
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in {"pubmed.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"}:
                errors.append("pubmed_url_not_official_https")
            else:
                expected_path = f"/{source_id}" if parsed.hostname == "pubmed.ncbi.nlm.nih.gov" else f"/pubmed/{source_id}"
                if parsed.path.rstrip("/") != expected_path or parsed.query or parsed.fragment:
                    errors.append("pubmed_url_identity_mismatch")
        coverage = row["[CoverageStatus]"]
        if source == "DORA" and coverage != "Accepted retained source observation":
            errors.append("dora_coverage_status_mismatch")
        if source == "PubMed" and coverage != "":
            errors.append("pubmed_unexpected_coverage_status")
        if errors:
            issues.append({"source": source, "source_id": source_id, "errors": errors})
    missing = sorted(expected - observed)
    receipt = {
        "kind": "retained_canary_field_integrity_v1",
        "status": "PASS" if len(model) == 1970 and observed_counts == expected_counts and not issues and not missing else "FAIL",
        "counts": {"model_rows": len(model), "archive_rows": len(archive), "model_pubmed": observed_counts["PubMed"], "model_dora": observed_counts["DORA"], "rows_with_field_issues": len(issues), "missing_archive_members": len(missing)},
        "scope": "isolated processed field integrity only; full source metadata parity, report-bound model, registry admission and refresh acceptance remain separate",
    }
    return receipt, {"issues": issues, "missing": missing}


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
        parser.error("detailed field differences must stay under ignored private/")
    paths = [p.resolve() for p in (args.model, args.archive, args.output, args.differences) if p]
    if len(paths) != len(set(paths)):
        parser.error("input and output paths must be distinct")
    model_bytes, archive_bytes = args.model.read_bytes(), args.archive.read_bytes()
    receipt, differences = verify(model_rows(json.loads(model_bytes)), retained_rows(json.loads(archive_bytes)))
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
