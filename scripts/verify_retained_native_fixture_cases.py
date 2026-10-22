"""Validate the exact isolated native fixture suite from native DAX output."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FILES = (
    ROOT / "tests/native/retained-summary-cases.m",
    ROOT / "tests/native/retained-parser-cases.m",
    ROOT / "tests/native/retention-cases.m",
    ROOT / "tests/native/committed-history-cases.m",
)
EXPECTED_COUNTS = (10, 8, 11, 16)
QUERY = '''EVALUATE
SELECTCOLUMNS('RetentionValidation',
    "Check", 'RetentionValidation'[Check],
    "Passed", 'RetentionValidation'[Passed])'''


def expected_checks() -> list[str]:
    """Read check names from the same M table definitions deployed to the model."""
    labels: list[str] = []
    for path, expected_count in zip(FIXTURE_FILES, EXPECTED_COUNTS, strict=True):
        source = path.read_text(encoding="utf-8")
        try:
            match = re.search(r"(?m)^\s*(?:Tests|Result|Results)=#table", source)
            if match is None:
                raise ValueError("fixture test table marker missing")
            table = source[match.end():]
            end = re.search(r"\nin (?:Tests|Result|Results)\s*$", table)
            if end is None:
                raise ValueError("fixture test table terminator missing")
            table = table[:end.start()]
        except IndexError as exc:
            raise ValueError(f"fixture test table not found in {path.name}") from exc
        except ValueError as exc:
            raise ValueError(f"fixture test table not found in {path.name}") from exc
        source_labels = re.findall(r'(?m)^\s*\{"([^"\n]+)"\s*,', table)
        if len(source_labels) != expected_count or len(set(source_labels)) != expected_count:
            raise ValueError(f"expected {expected_count} unique fixture checks in {path.name}")
        labels.extend(source_labels)
    if len(labels) != sum(EXPECTED_COUNTS) or len(set(labels)) != len(labels):
        raise ValueError("fixture check names must be unique across all M fixture tables")
    return labels


def model_rows(payload: object) -> list[dict]:
    """Require one complete ExecuteQueries table with exact aliases and booleans."""
    if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("results"), list) or len(payload["results"]) != 1:
        raise ValueError("one successful ExecuteQueries result required")
    result = payload["results"][0]
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("tables"), list) or len(result["tables"]) != 1:
        raise ValueError("one successful ExecuteQueries table required")
    table = result["tables"][0]
    if not isinstance(table, dict) or table.get("error") or not isinstance(table.get("rows"), list):
        raise ValueError("complete ExecuteQueries rows required")
    rows = table["rows"]
    if any(not isinstance(row, dict) or set(row) != {"[Check]", "[Passed]"}
           or not isinstance(row["[Check]"], str) or not isinstance(row["[Passed]"], bool)
           for row in rows):
        raise ValueError("fixture rows require exact Check text and boolean Passed aliases")
    return rows


def verify(rows: list[dict]) -> tuple[dict, dict]:
    """Require exact one-to-one check coverage and every native result to pass."""
    expected = expected_checks()
    observed: dict[str, list[bool]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"[Check]", "[Passed]"}:
            raise ValueError("fixture row aliases changed")
        label, passed = row["[Check]"], row["[Passed]"]
        if not isinstance(label, str) or not isinstance(passed, bool):
            raise ValueError("fixture labels and outcomes must be text and booleans")
        observed.setdefault(label, []).append(passed)
    missing = sorted(set(expected) - set(observed))
    extra = sorted(set(observed) - set(expected))
    duplicate = sorted(label for label, values in observed.items() if len(values) != 1)
    failed = sorted(label for label, values in observed.items() if any(value is False for value in values))
    differences = {"missing": missing, "extra": extra, "duplicate": duplicate, "failed": failed}
    receipt = {
        "kind": "retained_native_fixture_case_acceptance_v1",
        "status": "PASS" if len(rows) == len(expected) and not any(differences.values()) else "FAIL",
        "counts": {"expected": len(expected), "returned": len(rows), "passed": sum(row.get("[Passed]") is True for row in rows)},
        "fixtures": [str(path.relative_to(ROOT)) for path in FIXTURE_FILES],
        "query_scope": "RetentionValidation results only; must be correlated by caller to the isolated candidate definition and completed refresh request",
        # Passing the prepared fixture table is narrower than T11-H02. In
        # particular, the current M fixtures assert that some inputs error,
        # but do not prove that a previously accepted result remains available
        # after each rejected/partial input.
        "h02_last_good_recovery": last_good_recovery_coverage(expected),
    }
    return receipt, differences


def last_good_recovery_coverage(
    labels: list[str] | None = None,
    candidate_assertions: dict[str, str] | None = None,
) -> dict:
    """Report H02 recovery gaps without treating labels or M expressions as proof.

    This stays NOT_PROVEN until the assertions are executed and correlated to
    the exact isolated model/refresh readback. A name such as "preserves
    last-good" can still be backed by a weak ``HasError`` assertion.
    """
    present = set(expected_checks() if labels is None else labels)
    required = {
        "failed_source_preserves_last_good": "Failed source preserves last-good output",
        "incomplete_page_preserves_last_good": "Incomplete page preserves last-good output",
        "malformed_manifest_preserves_last_good": "Malformed manifest preserves last-good output",
    }
    missing = [key for key, label in required.items() if label not in present]
    return {
        "status": "NOT_PROVEN_PENDING_NATIVE_READBACK",
        "required_assertions": required,
        "missing_assertions": missing,
        "candidate_assertion_bodies": {
            key: (candidate_assertions or {}).get(label)
            for key, label in required.items()
            if label in present
        },
        "scope": "local fixture coverage audit; does not establish native M execution, model persistence, or H02 acceptance",
    }
