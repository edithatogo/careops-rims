"""Fail-closed local operational checks for a future grants ingestion run."""
from __future__ import annotations

from typing import Any, Iterable


def reconcile_registry_keys(
    emitted_records: Iterable[dict[str, Any]],
    registry_rows: Iterable[dict[str, Any]],
    prior_records=None,
):
    """Compare one emitted cycle with its registry readback by exact key set.

    This is a local reconciliation contract for a future native flow. It does
    not write the registry and preserves the prior accepted batch whenever the
    readback is malformed, duplicated or not an exact key-set match.
    """
    emitted = list(emitted_records)
    registry = list(registry_rows)
    errors: list[str] = []
    if any(not isinstance(row, dict) for row in emitted):
        errors.append('invalid_emitted_record_object')
    if any(not isinstance(row, dict) for row in registry):
        errors.append('invalid_registry_row_object')
    safe_emitted = [row if isinstance(row, dict) else {} for row in emitted]
    safe_registry = [row if isinstance(row, dict) else {} for row in registry]
    emitted_keys = [row.get('OpportunityKey') for row in safe_emitted]
    registry_keys = [row.get('OpportunityKey') for row in safe_registry]
    for values, invalid_error, missing_error, duplicate_error in (
        (emitted_keys, 'invalid_emitted_key', 'missing_emitted_key', 'duplicate_emitted_key'),
        (registry_keys, 'invalid_registry_key', 'missing_registry_key', 'duplicate_registry_key'),
    ):
        if any(not isinstance(key, str) for key in values):
            errors.append(invalid_error)
        if any(isinstance(key, str) and not key.strip() for key in values):
            errors.append(missing_error)
        if any(isinstance(key, str) and key != key.strip() for key in values):
            errors.append('whitespace_emitted_key' if values is emitted_keys else 'whitespace_registry_key')
        comparable = [key.strip() for key in values if isinstance(key, str) and key.strip()]
        if len(comparable) != len(set(comparable)):
            errors.append(duplicate_error)
    emitted_set = {key.strip() for key in emitted_keys if isinstance(key, str) and key.strip()}
    registry_set = {key.strip() for key in registry_keys if isinstance(key, str) and key.strip()}
    if emitted_set - registry_set:
        errors.append('registry_missing_emitted_keys')
    if registry_set - emitted_set:
        errors.append('registry_has_unexpected_keys')
    accepted = not errors
    return {
        'status': 'reconciled' if accepted else 'rejected',
        'errors': errors,
        'records': emitted if accepted else list(prior_records or []),
        'preserved_prior': bool(errors and prior_records),
    }


def reconcile_registry_records(
    emitted_records: Iterable[dict[str, Any]],
    registry_rows: Iterable[dict[str, Any]],
    fields: Iterable[str],
    prior_records=None,
):
    """Reconcile exact keys and selected field values from registry readback.

    Key equality alone can hide a partial SharePoint update. This companion
    contract checks an explicit field allowlist and preserves the prior
    accepted batch if any value is missing or differs.
    """
    if isinstance(fields, (str, bytes)):
        raise ValueError('reconciliation fields must be a collection, not a string')
    selected_fields = [field.strip() if isinstance(field, str) else field for field in fields]
    if (
        not selected_fields
        or any(not isinstance(field, str) or not field.strip() for field in selected_fields)
        or len(selected_fields) != len(set(selected_fields))
    ):
        raise ValueError('reconciliation fields must be unique, non-empty strings')
    emitted = list(emitted_records)
    registry = list(registry_rows)
    key_result = reconcile_registry_keys(emitted, registry)
    if key_result['status'] != 'reconciled':
        return {**key_result, 'records': list(prior_records or []), 'preserved_prior': bool(prior_records)}
    registry_by_key = {row['OpportunityKey'].strip(): row for row in registry}
    errors: list[str] = []
    for emitted_row in emitted:
        key = emitted_row['OpportunityKey'].strip()
        actual = registry_by_key[key]
        for field in selected_fields:
            if field not in emitted_row:
                errors.append(f'missing_emitted_field:{key}:{field}')
            elif field not in actual:
                errors.append(f'missing_registry_field:{key}:{field}')
            elif actual[field] != emitted_row[field]:
                errors.append(f'field_mismatch:{key}:{field}')
    accepted = not errors
    return {
        'status': 'reconciled' if accepted else 'rejected',
        'errors': errors,
        'records': emitted if accepted else list(prior_records or []),
        'preserved_prior': bool(errors and prior_records),
    }


def evaluate_run(records: Iterable[dict[str, Any]], health: Iterable[dict[str, Any]], prior_records=None):
    records = list(records)
    health = list(health)
    invalid_record_objects = any(not isinstance(row, dict) for row in records)
    invalid_health_objects = any(not isinstance(item, dict) for item in health)
    safe_records = [row if isinstance(row, dict) else {} for row in records]
    safe_health = [item if isinstance(item, dict) else {} for item in health]
    keys = [row.get('OpportunityKey') for row in safe_records]
    record_source_values = [row.get('Source').strip() if isinstance(row.get('Source'), str) else '' for row in safe_records]
    record_sources = {
        source for source in record_source_values if source
    }
    health_source_values = [item.get('source').strip() if isinstance(item.get('source'), str) else '' for item in safe_health]
    health_sources = {
        source for source in health_source_values if source
    }
    health_counts = {}
    errors = []
    if invalid_record_objects:
        errors.append('invalid_record_object')
    if invalid_health_objects:
        errors.append('invalid_health_object')
    if not records:
        errors.append('empty_batch')
    if not health:
        errors.append('missing_source_health')
    if any(not isinstance(item.get('source'), str) for item in safe_health):
        errors.append('invalid_health_source')
    if any(not source for source in health_source_values):
        errors.append('missing_health_source')
    if any(isinstance(item.get('source'), str) and item['source'] != item['source'].strip() for item in safe_health):
        errors.append('whitespace_health_source')
    if len(health_source_values) != len(set(health_source_values)):
        errors.append('duplicate_health_source')
    for item in safe_health:
        source = item.get('source').strip() if isinstance(item.get('source'), str) else ''
        count = item.get('count')
        if type(count) is not int or count < 0:
            errors.append('invalid_health_count')
        elif source:
            health_counts[source] = count
    if any(not isinstance(row.get('Source'), str) for row in safe_records):
        errors.append('invalid_record_source')
    if any(not source.strip() for source in record_source_values):
        errors.append('missing_record_source')
    if any(isinstance(row.get('Source'), str) and row['Source'] != row['Source'].strip() for row in safe_records):
        errors.append('whitespace_record_source')
    if any(not isinstance(key, str) for key in keys):
        errors.append('invalid_opportunity_key')
    if any(isinstance(key, str) and not key.strip() for key in keys):
        errors.append('missing_opportunity_key')
    if any(isinstance(key, str) and key != key.strip() for key in keys):
        errors.append('whitespace_opportunity_key')
    comparable_keys = [key.strip() for key in keys if isinstance(key, str) and key.strip()]
    if len(comparable_keys) != len(set(comparable_keys)):
        errors.append('duplicate_opportunity_key')
    if any(item.get('status') != 'succeeded' for item in safe_health):
        errors.append('source_failure')
    if record_sources - health_sources:
        errors.append('unreported_source')
    actual_counts = {}
    for source in record_source_values:
        if source:
            actual_counts[source] = actual_counts.get(source, 0) + 1
    if health_counts != actual_counts:
        errors.append('health_record_count_mismatch')
    accepted = not errors
    return {
        'status': 'accepted' if accepted else 'rejected',
        'errors': errors,
        'records': records if accepted else list(prior_records or []),
        'preserved_prior': bool(errors and prior_records),
    }
