"""Prepare native failure receipts for the existing monthly register export.

Local authoring only. Native ownership, acceptance, and activation remain separate.
The native handler cannot detect a trigger that never runs. evaluate_occurrence
specifies the evidence decision for a separate independent observer; it is local
preparation, not a deployed Python runtime or proof of automatic monitoring.

Current qualified routes are native Power Automate run history and existing-QH
Microsoft365 CLI persisted-file reads. A run reader must bind the Dataverse row
to its distinct runtime flow identity using the retained native identity receipt,
and supply actual recurrence occurrence evidence, complete paginated history,
correlated output readback, and an explicit observation as_of. Completion time
does not identify a scheduled occurrence. Restrict history to the selected
occurrence before evaluation; wrong-period records remain UNKNOWN.

No independent scheduler/trigger or deployment of this evaluator is qualified.
The export's own recurrence cannot monitor its absence, and G07's source-batch
health evaluator is not a scheduler. The user-selected policy is day1 at09:00
Brisbane, completion deadline12:00; monthly_occurrence_policy requires the month.
Evaluation still requires explicit occurrence/deadline/as_of inputs. Other test
deadlines are fixtures, not operating approval. Existing monthly activation
does not authorise an additional monitor recurrence, notifications or recipients.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo


def monthly_occurrence_policy(occurrence_month):
    """User-selected policy, 17 October 2026; no schedule activation implied.

    The occurrence month is explicit. Observation time is supplied separately;
    neither the current clock nor a fixture grace interval selects policy.
    """
    if not isinstance(occurrence_month, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', occurrence_month):
        raise ValueError('Explicit occurrence month must be YYYY-MM')
    year, month = map(int, occurrence_month.split('-'))
    zone = ZoneInfo('Australia/Brisbane')
    return {
        'expected_at': datetime(year, month, 1, 9, tzinfo=zone),
        'deadline': datetime(year, month, 1, 12, tzinfo=zone),
    }


def normalise_native_history(records, *, environment_id, dataverse_flow_id, runtime_flow_id):
    """Adapt exact-owner M365 run-list JSON, retaining manual-test evidence.

    Shape verification alone does not prove complete pagination, retention,
    observation coverage, an approved deadline, or persisted output readback.
    """
    ids = (environment_id, dataverse_flow_id, runtime_flow_id)
    if any(not isinstance(v, str) or not v.strip() or v != v.strip() for v in ids):
        return {'runs': [], 'history_shape_verified': False}
    if not isinstance(records, list):
        return {'runs': [], 'history_shape_verified': False}
    prefix = f'/providers/Microsoft.ProcessSimple/environments/{environment_id}/flows/{dataverse_flow_id}/runs/'
    normalised = []
    def timestamp(value):
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed if parsed.utcoffset() is not None else None
        except ValueError:
            return None
    for record in records:
        if not isinstance(record, Mapping):
            return {'runs': [], 'history_shape_verified': False}
        name = record.get('name')
        props = record.get('properties')
        if (not isinstance(name, str) or not name.strip() or name != name.strip()
                or record.get('id') != prefix + name or not isinstance(props, Mapping)):
            return {'runs': [], 'history_shape_verified': False}
        trigger = props.get('trigger')
        correlation = props.get('correlation', {})
        if not isinstance(trigger, Mapping) or not isinstance(correlation, Mapping):
            return {'runs': [], 'history_shape_verified': False}
        trigger_correlation = trigger.get('correlation', {})
        if not isinstance(trigger_correlation, Mapping):
            return {'runs': [], 'history_shape_verified': False}
        keywords = []
        for source in (correlation, trigger_correlation):
            values = source.get('clientKeywords', [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                return {'runs': [], 'history_shape_verified': False}
            keywords.extend(values)
        kind = 'Manual' if 'testFlow' in keywords else ('Recurrence' if trigger.get('name') == 'Recurrence' else 'Unknown')
        normalised.append({
            'run_id': name, 'flow_id': runtime_flow_id, 'trigger_kind': kind,
            'scheduled_for': timestamp(trigger.get('scheduledTime')),
            'started_at': timestamp(props.get('startTime')),
            'completed_at': timestamp(props.get('endTime')),
            'status': props.get('status'),
            'health_run_id': None, 'output_readback_verified': False,
        })
    return {'runs': normalised, 'history_shape_verified': True}


def evaluate_occurrence(*, expected_at, deadline, as_of, observation_start,
                        observation_end, history_complete, reads_verified,
                        runtime_flow_id, runs):
    """Evaluate supplied native evidence; this function is not a scheduler.

    Times are timezone-aware datetimes. Callers must supply a selected deadline
    and normalized evidence from a qualified native history/content reader.
    `scheduled_for` must come from trigger evidence, never from completion time.
    """
    def aware(value):
        return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    def result(status, reason):
        return {'status': status, 'reason': reason, 'automatic_detection_proved': False}
    def identity(value):
        return isinstance(value, str) and bool(value.strip()) and value == value.strip()
    times = (expected_at, deadline, as_of, observation_start, observation_end)
    if not all(aware(v) for v in times) or not identity(runtime_flow_id):
        return result('UNKNOWN', 'Missing timezone-aware policy or identity')
    if not isinstance(runs, list) or any(not isinstance(run, Mapping) for run in runs):
        return result('UNKNOWN', 'Malformed native history collection or record')
    if any(not identity(run.get('flow_id')) or not identity(run.get('run_id'))
           or not isinstance(run.get('status'), str) for run in runs):
        return result('UNKNOWN', 'Malformed native run identity or status')
    if deadline < expected_at or observation_end > as_of or observation_start > observation_end:
        return result('UNKNOWN', 'Inconsistent policy or future observation')
    if history_complete is not True or reads_verified is not True or observation_start > expected_at or observation_end < as_of:
        return result('UNKNOWN', 'Incomplete qualified observation/readback')
    if as_of < deadline:
        return result('PENDING', 'Explicit occurrence deadline has not passed')
    matched = []
    for run in runs:
        # Manual runs cannot establish or refute a scheduled occurrence.
        if run.get('trigger_kind') == 'Manual':
            continue
        if run.get('trigger_kind') != 'Recurrence' or run.get('flow_id') != runtime_flow_id:
            return result('UNKNOWN', 'Unqualified trigger or identity evidence')
        scheduled = run.get('scheduled_for')
        started = run.get('started_at')
        completed = run.get('completed_at')
        if not aware(scheduled) or not aware(started) or scheduled != expected_at:
            return result('UNKNOWN', 'Missing or wrong occurrence period')
        if started < expected_at or started > as_of or (completed is not None and (not aware(completed) or completed > as_of or completed < started)):
            return result('UNKNOWN', 'Invalid or future native run timestamp')
        matched.append(run)
    if not matched:
        return result('MISSED', 'No scheduled occurrence in complete observation after explicit deadline')
    if len(matched) != 1:
        return result('UNKNOWN', 'Multiple scheduled runs require duplicate reconciliation')
    run = matched[0]
    if run.get('status') == 'Succeeded':
        if not run.get('completed_at') or not identity(run.get('health_run_id')) or run.get('health_run_id') != run['run_id'] or run.get('output_readback_verified') is not True:
            return result('UNKNOWN', 'Missing correlated terminal output evidence')
        return result('SUCCEEDED', 'Scheduled occurrence and correlated output verified')
    if run.get('status') in {'Failed', 'TimedOut', 'Cancelled'} and run.get('completed_at'):
        return result('FAILED', 'Scheduled occurrence reached a non-success terminal state')
    return result('UNKNOWN', 'Scheduled occurrence has no verified terminal outcome')


def prepare_occurrence_packet(*, native_history, environment_id, dataverse_flow_id,
                              runtime_flow_id, expected_at, deadline, as_of,
                              observation_start, observation_end, history_complete,
                              reads_verified):
    """Prepare a minimal operator evidence packet, without writes or activation.

    Native run-list data cannot prove persisted output readback. Consequently
    this history-only packet cannot report a successful export as accepted.
    Full source history stays private; only minimal correlated metadata leaves
    this preparation step. Caller-selected policy is never defaulted.
    """
    adapted = normalise_native_history(native_history, environment_id=environment_id,
        dataverse_flow_id=dataverse_flow_id, runtime_flow_id=runtime_flow_id)
    decision = evaluate_occurrence(expected_at=expected_at, deadline=deadline, as_of=as_of,
        observation_start=observation_start, observation_end=observation_end,
        history_complete=history_complete is True and adapted['history_shape_verified'] is True,
        reads_verified=reads_verified, runtime_flow_id=runtime_flow_id, runs=adapted['runs'])
    def stamp(value):
        return value.isoformat() if isinstance(value, datetime) and value.utcoffset() is not None else None
    packet = {
        'kind': 'rims_monthly_occurrence_observation_v1',
        'dataverse_flow_id': dataverse_flow_id if isinstance(dataverse_flow_id, str) else None,
        'runtime_flow_id': runtime_flow_id if isinstance(runtime_flow_id, str) else None,
        'expected_at': stamp(expected_at), 'deadline': stamp(deadline), 'as_of': stamp(as_of),
        'observation_start': stamp(observation_start), 'observation_end': stamp(observation_end),
        'history_complete': history_complete is True and adapted['history_shape_verified'] is True,
        'reads_verified': reads_verified is True,
        'run_ids': [r['run_id'] for r in adapted['runs']],
        'decision': decision,
        'native_output_verification_inferred': False,
        'scheduled_trigger_activation': False,
    }
    canonical = json.dumps(packet, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    packet['observation_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return packet


def normalise_empty_join_delimiters(document):
    """Keep empty Join output while satisfying the native designer's required field.

    A literal empty delimiter is valid at runtime but the new designer rejects it.
    The explicit empty-string expression has the same runtime value. Other inputs,
    bindings, triggers and nonempty delimiters remain unchanged.
    """
    candidate = copy.deepcopy(document)

    def visit(value):
        if isinstance(value, dict):
            if value.get('type') == 'Join' and value.get('inputs', {}).get('joinWith') == '':
                value['inputs']['joinWith'] = "@string('')"
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(candidate)
    return candidate


def build(document):
    """Preserve export behaviour and append correlated success/failure receipts."""
    candidate = normalise_empty_join_delimiters(document)
    definition = candidate['properties']['definition']
    original = definition['actions']
    if 'Export_Run' in original or any(k.startswith('Monitor_') for k in original):
        raise ValueError('Monitoring already present; reconcile native drift')
    if not {'Printable_Verify_manifest', 'Printable_Save_completion_manifest'}.issubset(original):
        raise ValueError('Expected current printable export with manifest verification')
    save = original['Save_Registered_Publications_CSV']
    params = save['inputs']['parameters']
    if (save['inputs']['host']['operationId'] != 'CreateFile'
            or params['folderPath'] != '/Documents/CHHHS Research System - DEV/03 Reporting'):
        raise ValueError('Existing reporting storage binding changed')
    # A Scope must not contain a Terminate action. Do not silently transform one.
    def contains_terminate(value):
        if isinstance(value, dict):
            return value.get('type') == 'Terminate' or any(contains_terminate(v) for v in value.values())
        if isinstance(value, list):
            return any(contains_terminate(v) for v in value)
        return False
    if contains_terminate(original):
        raise ValueError('Existing termination requires explicit scope design')
    failure_statuses = ['Failed', 'TimedOut']
    all_statuses = ['Succeeded', 'Failed', 'Skipped', 'TimedOut']
    summary = {
        'type': 'Select',
        'inputs': {
            'from': "@result('Export_Run')",
            'select': {
                'action': "@item()?['name']",
                'status': "@item()?['status']",
                'code': "@item()?['code']",
            },
        },
        'runAfter': {'Export_Run': failure_statuses},
    }
    receipt = copy.deepcopy(save)
    receipt['inputs']['parameters']['name'] = "@concat('publication-register-',workflow()?['run']?['name'],'-failure.json')"
    receipt['inputs']['parameters']['body'] = "@string(outputs('Monitor_Failure_receipt'))"
    receipt['runAfter'] = {'Monitor_Failure_receipt': ['Succeeded']}
    success_receipt = copy.deepcopy(save)
    success_receipt['runAfter'] = {'Monitor_Success_receipt': ['Succeeded']}
    success_receipt['inputs']['parameters']['name'] = "@concat('publication-register-',workflow()?['run']?['name'],'-health.json')"
    success_receipt['inputs']['parameters']['body'] = "@string(outputs('Monitor_Success_receipt'))"
    definition['actions'] = {
        'Export_Run': {'type': 'Scope', 'actions': original, 'runAfter': {}},
        # Emit health only after the entire scope, including final manifest
        # readback, succeeds. The earlier manifest is not itself terminal proof.
        'Monitor_Success_receipt': {
            'type': 'Compose',
            'inputs': {
                'kind': 'rims_register_export_health_v1',
                'flow_id': "@workflow()?['name']",
                'run_id': "@workflow()?['run']?['name']",
                'completed_at_utc': '@utcNow()',
                'status': 'export-and-native-readback-succeeded',
                'manifest_file': "@body('Printable_Save_completion_manifest')?['Path']",
                'scheduled_trigger_proved': False,
            },
            'runAfter': {'Export_Run': ['Succeeded']},
        },
        'Monitor_Save_success': success_receipt,
        'Monitor_Action_statuses': summary,
        'Monitor_Failure_receipt': {
            'type': 'Compose',
            'inputs': {
                'kind': 'rims_register_export_failure_v1',
                'flow_id': "@workflow()?['name']",
                'run_id': "@workflow()?['run']?['name']",
                'observed_at_utc': '@utcNow()',
                'status': 'failed-or-timed-out',
                'actions': "@body('Monitor_Action_statuses')",
                'recovery': 'Inspect this correlated native run. Preserve existing outputs and last-good manifest; reconcile partial files before any rerun.',
                'completion_claimed': False,
            },
            'runAfter': {'Monitor_Action_statuses': ['Succeeded']},
        },
        'Monitor_Save_failure': receipt,
        # Logging success must not turn an export failure into a successful run.
        'Monitor_Retain_failed_status': {
            'type': 'Terminate',
            'inputs': {'runStatus': 'Failed', 'runError': {
                'code': 'RIMS_REGISTER_EXPORT_FAILED',
                'message': 'Export failed or timed out; inspect native run and any correlated failure receipt.',
            }},
            'runAfter': {'Monitor_Save_failure': all_statuses, 'Export_Run': failure_statuses},
        },
    }
    return candidate


def prepare_failure_probe(document):
    """Prepare a reversible, no-export native probe; never deploy it implicitly.

    Every original export action remains present for valid references, but its
    root actions wait on a deliberately failed Compose. No registry query or
    export write can run. The real monitoring failure branch is unchanged.
    Native use requires a separate bounded handoff and exact final restoration.
    """
    candidate = copy.deepcopy(document)
    actions = candidate['properties']['definition']['actions']
    if not {'Export_Run', 'Monitor_Save_failure', 'Monitor_Retain_failed_status'}.issubset(actions):
        raise ValueError('Expected integrated monitoring graph')
    inner = actions['Export_Run']['actions']
    if 'Monitor_Controlled_failure' in inner:
        raise ValueError('Probe already present')
    roots = [action for action in inner.values() if not action.get('runAfter')]
    if not roots:
        raise ValueError('Expected export root actions')
    for action in roots:
        action['runAfter'] = {'Monitor_Controlled_failure': ['Succeeded']}
    inner['Monitor_Controlled_failure'] = {
        'type': 'Compose', 'inputs': "@int('RIMS_CONTROLLED_MONITOR_FAILURE')", 'runAfter': {},
    }
    return candidate
