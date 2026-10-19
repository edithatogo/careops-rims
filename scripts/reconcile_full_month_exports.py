"""Fail-closed local oracle for one full/monthly canonical export generation.

Both inputs must contain independently queried keys and complete page chains. This
checks supplied extraction evidence; it does not establish native provenance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

if __package__:
    from .export_publication_register import assemble_paginated_export, export_errors, key_hash
else:
    from export_publication_register import assemble_paginated_export, export_errors, key_hash

SHA256 = re.compile(r'[0-9a-f]{64}')


def reconcile(full_input: dict[str, Any], month_input: dict[str, Any]) -> dict[str, Any]:
    full = assemble_paginated_export(full_input)
    month = assemble_paginated_export(month_input)
    for name, export in (("full", full), ("monthly", month)):
        errors = export_errors(export)
        if errors:
            raise ValueError(f"{name} export contract failed: {'; '.join(errors)}")
    if full["scope"] != {"mode": "all", "reporting_month": None}:
        raise ValueError("Full export must have unfiltered all-publications scope")
    if month["scope"].get("mode") != "month":
        raise ValueError("Monthly export must have month scope")
    for field in ("generation_id", "source_snapshot_id", "data_kind",
                  "query_version", "model_refresh_correlation"):
        if full_input.get(field) != month_input.get(field):
            raise ValueError(f"Full/monthly exports differ in {field}")
    if full_input.get("data_kind") == "live_export":
        for name, envelope in (("full", full_input), ("monthly", month_input)):
            fingerprint = envelope.get("extraction_contract_sha256")
            if not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint):
                raise ValueError(f"Live {name} export requires a canonical extraction_contract_sha256")
        if full_input["extraction_contract_sha256"] != month_input["extraction_contract_sha256"]:
            raise ValueError("Full/monthly exports differ in extraction_contract_sha256")
        for field in ("query_version", "model_refresh_correlation"):
            if not isinstance(full_input.get(field), str) or not full_input[field].strip():
                raise ValueError(f"Live full/monthly exports require {field}")
    elif "extraction_contract_sha256" in full_input or "extraction_contract_sha256" in month_input:
        full_fingerprint = full_input.get("extraction_contract_sha256")
        month_fingerprint = month_input.get("extraction_contract_sha256")
        if (not isinstance(full_fingerprint, str) or not SHA256.fullmatch(full_fingerprint)
                or full_fingerprint != month_fingerprint):
            raise ValueError("Synthetic test-only exports must use the same canonical extraction contract fingerprint")
    period = month["scope"]["reporting_month"]
    expected = {row["CanonicalKey"]: row for row in full["records"] if row["PublicationMonth"] == period}
    actual = {row["CanonicalKey"]: row for row in month["records"]}
    if expected.keys() != actual.keys():
        raise ValueError(
            "Monthly keys differ from the complete full-export month partition: "
            f"missing_count={len(expected.keys() - actual.keys())}, "
            f"unexpected_count={len(actual.keys() - expected.keys())}"
        )
    if any(actual[key] != expected[key] for key in expected):
        raise ValueError("Monthly metadata differs from full export for the same canonical key")
    return {
        "generation_id": full_input["generation_id"],
        "source_snapshot_id": full["source_snapshot_id"],
        "query_version": full_input.get("query_version"),
        "model_refresh_correlation": full_input.get("model_refresh_correlation"),
        "extraction_contract_sha256": full_input.get("extraction_contract_sha256"),
        "reporting_month": period,
        "full_count": len(full["records"]),
        "monthly_count": len(month["records"]),
        "unknown_month_count": sum(row["PublicationMonth"] in (None, "") for row in full["records"]),
        "full_key_sha256": key_hash(full["records"]),
        "monthly_key_sha256": key_hash(month["records"]),
        "native_provenance_verified_by_this_script": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full", type=Path)
    parser.add_argument("monthly", type=Path)
    args = parser.parse_args()
    try:
        full = json.loads(args.full.read_text(encoding="utf-8"))
        month = json.loads(args.monthly.read_text(encoding="utf-8"))
        if not isinstance(full, dict) or not isinstance(month, dict):
            raise ValueError("Each export input must be an object")
        print(json.dumps(reconcile(full, month), indent=2))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Reconciliation failed: {error}\n")


if __name__ == "__main__":
    main()
