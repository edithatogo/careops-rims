"""Fail-closed checks for paged publication batches.

These checks validate a collector/export contract locally. They do not claim
that a Power BI or Power Automate response was obtained from the tenant.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


PROTECTED_MANUAL_FIELDS = frozenset({
    "FirstObservedUTC", "ReviewStatus", "ReviewNotes", "Title", "Authors",
    "Journal", "PublicationYear", "PublicationMonth", "SourceKey",
    "CanonicalKey",
})
OBSERVED_UPDATE_FIELDS = frozenset({
    "LastObservedUTC", "CitationCount_OpenAlex", "OpenAccessStatus", "OAUrl",
    "CitationMetricsObservedUTC",
})


def validate_update_allowlist(
    fields: Iterable[str], *, internal_allowed: Iterable[str] = ()
) -> list[str]:
    """Reject writes outside the narrow observation-only update contract."""
    names = {str(field) for field in fields}
    errors: list[str] = []
    forbidden = names & PROTECTED_MANUAL_FIELDS
    allowed = OBSERVED_UPDATE_FIELDS | {str(field) for field in internal_allowed}
    unknown = names - allowed
    if forbidden:
        errors.append(f"manual fields are protected from update: {sorted(forbidden)}")
    if unknown:
        errors.append(f"update fields are outside the observation allowlist: {sorted(unknown)}")
    return errors


def validate_paged_batch(
    pages: Iterable[Mapping[str, object]],
    *,
    expected_count: int,
    expected_keys: Iterable[str],
    key_field: str = "SourceKey",
) -> list[str]:
    """Validate complete, ordered pages before allowing a batch to be applied."""
    page_list = list(pages)
    expected = [str(key) for key in expected_keys]
    expected_set = set(expected)
    errors: list[str] = []
    if type(expected_count) is not int or expected_count < 0:
        errors.append("expected count must be a non-negative integer")
    if any(not key.strip() for key in expected):
        errors.append(f"independent expected {key_field} set contains a blank key")
    seen: list[str] = []
    previous_cursor: object = None
    for index, page in enumerate(page_list):
        rows = page.get("rows")
        if not isinstance(rows, list):
            errors.append(f"page {index} rows must be a list")
            continue
        if page.get("error") or page.get("partial") is True:
            errors.append(f"page {index} is an error or partial response")
        cursor_before = page.get("cursor_before")
        cursor_after = page.get("cursor_after")
        if index and cursor_before != previous_cursor:
            errors.append(f"page {index} cursor does not continue the previous page")
        keys: list[str] = []
        for row in rows:
            if not isinstance(row, Mapping) or not row.get(key_field):
                errors.append(f"page {index} contains a row without {key_field}")
                continue
            keys.append(str(row[key_field]))
        if len(keys) != len(set(keys)):
            errors.append(f"page {index} contains duplicate {key_field} values")
        seen.extend(keys)
        if rows and cursor_after in (None, ""):
            errors.append(f"page {index} with rows has no continuation cursor")
        if rows and cursor_before is not None and cursor_after == cursor_before:
            errors.append(f"page {index} cursor did not advance")
        previous_cursor = cursor_after
    if len(seen) != expected_count:
        errors.append(f"row count {len(seen)} does not match expected count {expected_count}")
    if len(seen) != len(set(seen)):
        errors.append(f"paged batch contains duplicate {key_field} values")
    if set(seen) != expected_set:
        errors.append(f"paged {key_field} set does not match the independent expected set")
    if len(expected) != len(expected_set):
        errors.append(f"independent expected {key_field} set contains duplicates")
    return errors
