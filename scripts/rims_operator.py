"""Small operator-side conveniences; no hosted runtime or native mutations."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def walk(value, path='$'):
    """Visit JSON metadata without evaluating expressions or following links."""
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, path + '.' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f'{path}[{index}]')


def receipt_document(document):
    # Connector Get file content action receipts may contain a JSON $content body.
    body = document.get('body') if isinstance(document, dict) else None
    if isinstance(body, dict) and '$content' in body:
        media = body.get('$content-type', '').split(';')[0].lower()
        if media in {'application/json', 'text/json'}:
            decoded = json.loads(base64.b64decode(body['$content'], validate=True))
            return {'transport_status': document.get('statusCode'), 'receipt': decoded}
    return document


def run_summary(document):
    document = receipt_document(document)
    reported_outcome = None
    if isinstance(document, dict):
        for candidate in [document.get('properties'), document.get('text'), document.get('receipt'), document]:
            if isinstance(candidate, dict) and isinstance(candidate.get('status'), str):
                reported_outcome = candidate['status']
                break
    statuses, counts, locations, problems, identities = [], [], [], [], []
    count_keys = {'records', 'rows', 'count', 'record_count', 'records_processed',
                  'register_row_count', 'part_count', 'current_rows', 'candidate',
                  'confirmed', 'native_rows', 'candidates', 'confirmed_reviewed'}
    location_keys = {'manifest_file', 'csv_file', 'index_file', 'output_location',
                     'output_path', 'folder', 'path', 'Path', 'ServerRelativeUrl'}
    identity_keys = {'run_id', 'flow_run_id', 'run', 'flow_id', 'runName', 'runId', 'name', 'id'}
    for path, value in walk(document):
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            entry = {'field': path + '.' + key, 'value': item}
            if key in {'status', 'extendedStatus', 'transport_status', 'statusCode', 'status_code'} and isinstance(item, (str, int)):
                statuses.append(entry)
            if (key in count_keys or key.endswith('_count') or key in {'source_total', 'rows_processed', 'rows_created', 'rows_updated'}) and isinstance(item, int) and not isinstance(item, bool):
                counts.append(entry)
            if key in location_keys and isinstance(item, str):
                locations.append(entry)
            if key in identity_keys and isinstance(item, str) and path.count('.') < 3:
                identities.append(entry)
            if key in {'error', 'errors', 'serviceExceptionJson', 'readback_error'} and item:
                problems.append(entry)
        status = value.get('status', value.get('Status'))
        if isinstance(status, str) and any(word in status.casefold() for word in ['fail', 'timedout', 'timed-out', 'cancel', 'uncertain']):
            problems.append({'field': path, 'value': {k: value[k] for k in ['name', 'code', 'status', 'Status', 'error', 'message'] if k in value}})
        if str(value.get('type', '')).casefold() in {'warning', 'error'} and value.get('message'):
            problems.append({'field': path, 'value': value})
    return {'reported_outcome': reported_outcome or 'UNKNOWN',
            'statuses': statuses, 'identities': identities, 'record_counts': counts,
            'output_locations': locations, 'unresolved_errors_and_warnings': problems,
            'limits': ['Only fields present in this saved receipt are reported.',
                       'Transport success and receipt status do not prove native output acceptance.',
                       'Missing counts, outputs or errors are unknown, not zero or healthy.']}


RECOVERY = [
    ('conditional_access', ['AADSTS53003', 'Conditional Access denial'],
     'Stop unchanged authentication retries. Use the established permitted route; retain the exact denial and do not change policy or identity to bypass it.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('permission_denied', ['HTTP 403', 'AccessDenied', '"status_code": 403', '"statusCode": 403'],
     'Inspect the exact denied operation and its impact. A 403 alone does not prove ordinary expiry. Preserve the denial, use an already permitted route where supported, and do not change grants or bypass policy.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('expired_authentication', ['AADSTS70043', 'interaction_required', 'token expired', 'expired token'],
     'Recover the exact workload through the established VS Code method and account/resource mapping, then verify the failed target once. Preserve any submitted run handle.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('unbound_sources', ['DMTS_MonikerWithUnboundDataSources'],
     'Read item connections and restore the exact previously qualified bindings. Verify all bindings before another targeted refresh; datasource declarations alone are insufficient.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('source_discovery', ['Premium_ASWL_Error'],
     'Inspect saved partition source discovery and exact existing bindings. The known fix used a literal SharePoint site in the partition. Do not infer that a gateway purchase or new connector is required.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('etag_conflict', ['HTTP 412', 'PreconditionFailed', 'Precondition Failed',
                       '"code": "412"', '"statusCode": 412', '"status_code": 412'],
     'Read the exact current item and reconcile its values with the intended change. Obtain its current ETag through the qualified metadata read; never substitute a wildcard or blindly resubmit.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
    ('dax_warning', ["syntax for 'Typed'", 'calculated-column warning'],
     'Inspect refresh warnings and calculated outputs even if status is Completed. The known repair renamed reserved DAX variable Typed to RegisteredAdmission, then verified the affected refresh and rows.',
     'docs/RIMS_OPERATOR_TOOLS.md#2-find-the-next-recovery-step'),
]


def recovery(document):
    text = json.dumps(receipt_document(document), ensure_ascii=False).casefold()
    matches = [{'cause': code, 'next_step': instruction, 'runbook': source}
               for code, needles, instruction, source in RECOVERY
               if any(needle.casefold() in text for needle in needles)]
    return {'matched_causes': matches, 'default_next_step':
            'Preserve the exact run handle and last-good output. Reconcile uncertain effects before any retry; use the affected action error to select recovery.',
            'automatic_retry': False, 'known_match_is_diagnosis': False}


def failed_actions(document):
    document = receipt_document(document)
    actions = []
    failed = {'failed', 'timedout', 'timed-out', 'cancelled', 'canceled', 'faulted'}
    for path, value in walk(document):
        if not isinstance(value, dict) or path.endswith('.properties'):
            continue
        props = value.get('properties', value)
        if not isinstance(props, dict) or str(props.get('status', '')).casefold() not in failed:
            continue
        name = value.get('action') or value.get('actionName') or value.get('name')
        if not name and '.actions.' in path:
            name = path.rsplit('.', 1)[-1]
        resource = str(value.get('type', ''))
        if resource.endswith('/runs') or any(k in value for k in ['run_id', 'flow_run_id']):
            continue  # A failed run is not itself a failed action.
        if not name:
            continue
        errors = {k: props[k] for k in ['error', 'errors', 'message', 'code', 'statusCode'] if props.get(k) is not None}
        codes = []
        for _, item in walk(errors):
            if isinstance(item, dict):
                codes.extend(str(item[k]) for k in ['code', 'statusCode'] if item.get(k) is not None)
        actions.append({'action': name, 'field': path, 'status': props['status'],
                        'error_codes': list(dict.fromkeys(codes)), 'error_details': errors,
                        'recovery': recovery(errors)})
    return {'failed_actions': actions, 'failed_action_count': len(actions),
            'run_identities': run_summary(document)['identities'],
            'scope': 'Saved action metadata only; absent action details are unknown. Content links are never followed.'}


def compare_receipts(before, after):
    left, right = run_summary(before), run_summary(after)
    changes = []
    for section in ['reported_outcome', 'record_counts', 'output_locations', 'unresolved_errors_and_warnings']:
        if section == 'reported_outcome':
            if left[section] != right[section]:
                changes.append({'section': section, 'before': left[section], 'after': right[section]})
            continue
        # Paths retain separate fields even when their values happen to be equal.
        a = {x['field']: x['value'] for x in left[section]}
        b = {x['field']: x['value'] for x in right[section]}
        for field in sorted(a.keys() | b.keys()):
            if field not in a or field not in b or a[field] != b[field]:
                change = {'section': section, 'field': field,
                          'before_present': field in a, 'after_present': field in b}
                if field in a:
                    change['before'] = a[field]
                if field in b:
                    change['after'] = b[field]
                changes.append(change)
    return {'equal': not changes, 'before_identities': left['identities'],
            'after_identities': right['identities'], 'changes': changes,
            'scope': 'Comparison of reported outcome, counts, warnings/errors and output locations; no cross-run causality or acceptance inferred.'}


def summarize_receipts(paths):
    rows = []
    for path in paths:
        try:
            summary = run_summary(read_json(path))
            rows.append({'receipt': str(path), 'identities': summary['identities'],
                         'outcome': summary['reported_outcome'], 'counts': summary['record_counts'],
                         'outputs': summary['output_locations'],
                         'problem_fields': len(summary['unresolved_errors_and_warnings']), 'read_error': None})
        except (OSError, ValueError, TypeError) as error:
            rows.append({'receipt': str(path), 'identities': [], 'outcome': 'UNREADABLE',
                         'counts': [], 'outputs': [], 'problem_fields': None, 'read_error': str(error)})
    return {'receipts': rows, 'receipt_count': len(rows),
            'scope': 'Explicit input order retained; no latest-run selection, merged totals or inferred success.'}


def render_text(result):
    """Readable display, keeping JSON as the stable default interchange format."""
    def compact(value):
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    def table(headers, rows):
        clean = lambda x: str(x).replace('\n', '\\n').replace('|', '\\|')
        return '\n'.join([' | '.join(headers), ' | '.join('---' for _ in headers)] +
                         [' | '.join(clean(x) for x in row) for row in rows])
    if 'run_identity' in result and 'files' in result:
        rows = []
        for entry in result['files']:
            rows.append([entry.get('name') or entry.get('Name') or entry.get('Path'),
                         entry.get('bytes', entry.get('native_length_bytes', 'unknown')),
                         entry.get('sha256', 'not recorded'), entry.get('verification', 'not recorded')])
        return 'Run: ' + compact(result['run_identity']) + '\n' + table(
            ['File', 'Bytes', 'SHA256', 'Saved verification'], rows) + '\n' + result['scope']
    if 'failed_actions' in result:
        lines = []
        for action in result['failed_actions']:
            lines.append(f"{action['action']}: {action['status']} ({', '.join(action['error_codes']) or 'code not recorded'})")
            lines.append('Error: ' + compact(action['error_details']))
            lines.append(render_text(action['recovery']))
        return '\n'.join(lines or ['No failed action details found; this does not prove run success.'])
    if 'receipts' in result:
        rows = []
        for row in result['receipts']:
            rows.append([row['receipt'], '; '.join(str(x['value']) for x in row['identities']) or 'unknown',
                         row['outcome'], '; '.join(f"{x['field']}={x['value']}" for x in row['counts']) or 'unknown',
                         '; '.join(str(x['value']) for x in row['outputs']) or 'unknown',
                         row['read_error'] or row['problem_fields']])
        return table(['Receipt', 'Run identity', 'Outcome', 'Counts', 'Outputs', 'Problem fields / read error'], rows) + '\n' + result['scope']
    if 'before_identities' in result:
        lines = ['Before identity: ' + compact(result['before_identities']),
                 'After identity: ' + compact(result['after_identities'])]
        for change in result['changes']:
            lines.append(f"{change['section']} {change.get('field', '')}: " +
                         compact(change.get('before', '<absent>')) + ' -> ' + compact(change.get('after', '<absent>')))
        return '\n'.join(lines + ([] if result['changes'] else ['No reported differences.']))
    if 'file_count' in result and 'files' in result:
        return f"Revision: {result['revision']}\nStatus: {result.get('status', 'PLAN_ONLY')}\n" + table(
            ['File', 'Result', 'Expected SHA256'],
            [[x['file'], x.get('status', 'planned'), x['expected_sha256']] for x in result['files']])
    if 'reported_outcome' in result:
        lines = ['Outcome: ' + result['reported_outcome']]
        for title, key in [('Identity', 'identities'), ('Count', 'record_counts'),
                           ('Output', 'output_locations'), ('Problem', 'unresolved_errors_and_warnings')]:
            entries = result[key]
            lines.extend(f"{title}: {x['field']} = {compact(x['value'])}" for x in entries)
            if not entries:
                lines.append(title + ': not recorded')
        return '\n'.join(lines + ['Saved receipt only; missing fields do not prove success.'])
    if 'matched_causes' in result:
        lines = []
        for match in result['matched_causes']:
            lines.extend([match['cause'] + ': ' + match['next_step'], 'Runbook: ' + match['runbook']])
        return '\n'.join(lines or ['No known cause matched.', result['default_next_step']])
    return '\n'.join(f'{key}: {compact(value)}' for key, value in result.items())


def aware_time(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be explicit ISO8601 text with timezone')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Timestamp requires a timezone offset')
    return result


def monitor(args):
    from scripts.prepare_register_export_monitoring import (
        evaluate_occurrence, monthly_occurrence_policy, prepare_occurrence_packet)
    policy = monthly_occurrence_policy(args.month)
    times = {name: aware_time(getattr(args, name)) for name in
             ['as_of', 'observation_start', 'observation_end']}
    evidence = read_json(args.evidence or args.history)
    if args.history:
        if not all([args.environment_id, args.dataverse_flow_id, args.runtime_flow_id]):
            raise ValueError('Native history requires exact environment, Dataverse and runtime flow IDs')
        return prepare_occurrence_packet(native_history=evidence,
            environment_id=args.environment_id, dataverse_flow_id=args.dataverse_flow_id,
            runtime_flow_id=args.runtime_flow_id, **policy, **times,
            history_complete=args.history_complete, reads_verified=args.reads_verified)
    runs = evidence.get('runs')
    if not isinstance(runs, list):
        raise ValueError('Normalized evidence requires a runs array')
    parsed_runs = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError('Normalized runs must be objects')
        parsed = dict(run)
        for name in ['scheduled_for', 'started_at', 'completed_at']:
            if parsed.get(name) is not None:
                parsed[name] = aware_time(parsed[name])
        parsed_runs.append(parsed)
    decision = evaluate_occurrence(**policy, **times,
        runtime_flow_id=evidence.get('runtime_flow_id'), runs=parsed_runs,
        history_complete=evidence.get('history_complete'), reads_verified=evidence.get('reads_verified'))
    return {'month': args.month, **{k: v.isoformat() for k, v in {**policy, **times}.items()},
            'decision': decision, 'operator_run_only': True,
            'evidence_sha256': hashlib.sha256(Path(args.evidence).read_bytes()).hexdigest(),
            'qualification': 'Caller-supplied evidence flags are not independently qualified by this command.'}


def flow_view(document):
    """Extract supported saved Flow API and Dataverse clientdata shapes."""
    if not isinstance(document, dict):
        raise ValueError('Saved flow must be a JSON object')
    if 'clientdata' in document:
        client = document['clientdata']
        client = json.loads(client) if isinstance(client, str) else client
        result = flow_view(client)
        result['state'].update({k: document[k] for k in ['statecode', 'statuscode'] if k in document})
        result['identity'].update({k: document[k] for k in ['workflowid', 'workflowidunique'] if k in document})
        return result
    if 'definition' in document:
        props = document
    elif isinstance(document.get('properties'), dict) and 'definition' in document['properties']:
        props = document['properties']
    elif 'actions' in document and 'triggers' in document:
        props = {'definition': document}
    else:
        raise ValueError('Unsupported flow shape: expected definition, properties.definition, clientdata or raw triggers/actions')
    if not isinstance(props['definition'], dict):
        raise ValueError('Flow definition must be an object')
    return {'definition': props['definition'],
            'connections': {k: props[k] for k in ['connectionReferences', 'connections', 'parameters'] if k in props},
            'state': {k: props[k] for k in ['state', 'statecode', 'statuscode'] if k in props},
            'identity': {k: document[k] for k in ['name', 'id', 'workflowid'] if k in document}}


def redacted(value, key=''):
    if any(word in key.casefold() for word in ['password', 'secret', 'token', 'authorization', 'credential']):
        return '<redacted>'
    if isinstance(value, dict):
        if str(value.get('type', '')).casefold() in {'securestring', 'secureobject'}:
            return '<redacted secure parameter>'
        return {k: redacted(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redacted(v) for v in value]
    return value


def compare_flows(before, after):
    before, after = flow_view(before), flow_view(after)
    changes = []
    def compare(left, right, path):
        if type(left) is type(right) and left == right:
            return
        if any(isinstance(v, dict) and str(v.get('type', '')).casefold() in {'securestring', 'secureobject'} for v in [left, right]):
            changes.append({'path': path, 'change': 'changed',
                            'before': '<redacted secure parameter>', 'after': '<redacted secure parameter>'})
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                child = path + '/' + key.replace('~', '~0').replace('/', '~1')
                if key not in left:
                    changes.append({'path': child, 'change': 'added', 'after': redacted(right[key], key)})
                elif key not in right:
                    changes.append({'path': child, 'change': 'removed', 'before': redacted(left[key], key)})
                else:
                    compare(left[key], right[key], child)
        else:
            key = path.rsplit('/', 1)[-1]
            changes.append({'path': path, 'change': 'changed',
                            'before': redacted(left, path), 'after': redacted(right, path)})
    compare(before, after, '')
    return {'equal': not changes, 'changes': changes,
            'scope': 'Saved definition, action graph, triggers, parameters, connections, state and identity; not native/runtime acceptance.'}


def manifest_document(document):
    if not isinstance(document, dict):
        raise ValueError('Manifest must be a JSON object')
    for key in ['statusCode', 'status_code']:
        if key in document and (not isinstance(document[key], int) or document[key] >= 400):
            raise ValueError('Failed manifest retrieval receipt')
    if 'body' in document:
        document = document['body']
    if isinstance(document, dict) and '$content' in document:
        document = json.loads(base64.b64decode(document['$content'], validate=True))
    if not isinstance(document, dict):
        raise ValueError('Decoded manifest must be an object')
    return document


def manifest_entries(manifest):
    entries = manifest.get('files', [])
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError('Manifest files must be an array of objects')
    entries = [dict(e) for e in entries]
    for role in ['csv_file', 'index_file']:
        if isinstance(manifest.get(role), dict):
            entries.append({'name': role, **manifest[role]})
    if 'part_name_pattern' in manifest or 'part_count' in manifest:
        count, pattern = manifest.get('part_count'), manifest.get('part_name_pattern')
        if (type(count) is not int or count < 0 or not isinstance(pattern, str)
                or pattern.count('{zero-based-index}') != 1 or pattern.startswith('@')):
            raise ValueError('Printable parts require a resolved pattern and nonnegative integer part_count')
        entries.extend({'name': pattern.replace('{zero-based-index}', str(i))} for i in range(count))
    for entry in entries:
        selector = entry.get('name') or entry.get('Name') or entry.get('Path')
        if not isinstance(selector, str) or not selector:
            raise ValueError('Every manifest file requires an exact name or Path')
    selectors = [e.get('name') or e.get('Name') or e.get('Path') for e in entries]
    if len(set(selectors)) != len(selectors):
        raise ValueError('Ambiguous duplicate manifest file names')
    return entries


def list_export(document):
    manifest = manifest_document(document)
    entries = manifest_entries(manifest)
    fields = ['name', 'Name', 'Path', 'path', 'ServerRelativeUrl', 'sha256', 'bytes',
              'rows', 'native_length_bytes', 'native_unique_id', 'native_etag',
              'native_version', 'verification']
    return {'run_identity': {k: manifest[k] for k in ['run', 'run_id', 'flow_run_id', 'source_run'] if k in manifest},
            'file_count': len(entries), 'files': [{k: e[k] for k in fields if k in e} for e in entries],
            'verification': {k: manifest[k] for k in ['hashes_verified', 'cryptographic_hashes',
                'native_stored_content_readback_verified', 'status', 'canonical_acceptance'] if k in manifest},
            'scope': 'Saved manifest metadata only; no file content or current native state verified.'}


def retrieval_plan(args):
    manifest = manifest_document(read_json(args.manifest))
    revisions = [manifest[k] for k in ['run', 'run_id', 'flow_run_id'] if manifest.get(k)]
    if not revisions or any(revision != args.revision for revision in revisions):
        raise ValueError('Exact manifest run revision does not match --revision')
    entries = manifest_entries(manifest)
    matches = [entry for entry in entries if isinstance(entry, dict)
               and args.file in [entry.get('name'), entry.get('Name'), entry.get('Path')]]
    if len(matches) != 1:
        raise ValueError('Select exactly one file name/role/Path in the existing manifest')
    entry = matches[0]
    site = urlsplit(args.site)
    if (site.scheme != 'https' or not (site.hostname or '').endswith('.sharepoint.com')
            or site.username or site.password or site.query or site.fragment):
        raise ValueError('Use an existing exact HTTPS SharePoint site URL')
    remote = entry.get('Path') or entry.get('path') or entry.get('ServerRelativeUrl')
    if not remote:
        name = entry.get('name') or entry.get('Name')
        if not args.folder or not isinstance(name, str) or '/' in name or '\\' in name or name in {'.', '..'}:
            raise ValueError('Manifest file names require an explicit existing --folder')
        remote = args.folder.rstrip('/') + '/' + name
    if (not isinstance(remote, str) or not remote.startswith('/') or remote.startswith('//')
            or any(c in remote for c in ['?', '#', '\\', '%']) or '..' in remote.split('/')):
        raise ValueError('Exact decoded site/server-relative file path required')
    expected = entry.get('sha256') or args.sha256
    if args.reference:
        reference_hash = hashlib.sha256(args.reference.read_bytes()).hexdigest()
        if expected and expected != reference_hash:
            raise ValueError('Reference bytes disagree with expected hash')
        expected = reference_hash
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Exact revision requires a manifest SHA256, --sha256 or accepted --reference bytes')
    if args.sha256 and args.sha256 != expected:
        raise ValueError('Conflicting expected hash')
    destination = args.destination.resolve()
    if not destination.is_relative_to(ROOT / 'private' / 'ops'):
        raise ValueError('Retrieved exports must remain under private/ops')
    if destination.exists():
        raise ValueError('Preserve existing output; choose a new destination')
    return {'revision': args.revision, 'file': args.file, 'site': args.site,
            'remote_path': remote, 'expected_sha256': expected,
            'destination': str(destination), 'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            'command': ['m365', 'spo', 'file', 'get', '--webUrl', args.site,
                        '--url', remote, '--asFile', '--path', str(destination), '--output', 'json'],
            'native_writes': False, 'execute': args.execute}


def retrieve(args):
    plan = retrieval_plan(args)
    if not args.execute:
        return plan
    destination = Path(plan['destination'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='retrieval-', dir=destination.parent))
    receipt_path = attempt / 'receipt.json'
    plan.update(status='DOWNLOAD_PENDING', attempt_directory=str(attempt))
    receipt_path.write_text(json.dumps(plan, indent=2) + '\n')
    command = list(plan['command'])
    command[command.index('--path') + 1] = str(attempt / 'download.partial')
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (attempt / 'stderr.txt').write_text(result.stderr)
        if result.returncode != 0:
            raise ValueError('M365 download failed; inspect private attempt stderr. No authentication or retry was started by this tool.')
        raw = (attempt / 'download.partial').read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        plan['downloaded_sha256'] = actual
        if actual != plan['expected_sha256']:
            raise ValueError('Downloaded bytes differ from selected accepted revision; partial retained, destination not created')
        # Same-filesystem atomic no-overwrite publication of already verified bytes.
        # A competing create raises FileExistsError instead of replacing that file.
        os.link(attempt / 'download.partial', destination)
        plan.update(status='VERIFIED_EXACT_EXPORT_REVISION', bytes=len(raw))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        plan.update(status='FAILED_OR_UNVERIFIED', error=str(error))
        raise
    finally:
        receipt_path.write_text(json.dumps(plan, indent=2) + '\n')
    return plan


def bundle_plan(args):
    manifest = manifest_document(read_json(args.manifest))
    entries = manifest_entries(manifest)
    if not entries:
        raise ValueError('Bundle requires at least one manifest-listed file')
    destination = args.destination.resolve()
    if not destination.is_relative_to(ROOT / 'private' / 'ops') or destination.exists():
        raise ValueError('Choose a new bundle directory under private/ops')
    plans, names = [], set()
    for entry in entries:
        selector = entry.get('name') or entry.get('Name') or entry.get('Path')
        remote = entry.get('Path') or entry.get('path') or entry.get('ServerRelativeUrl')
        name = Path(remote or selector).name
        if name in names or name in {'.', '..', '.rims-bundle-receipt.json'} or not name:
            raise ValueError('Bundle requires distinct, nonreserved local file names')
        names.add(name)
        reference = args.reference_directory / name if args.reference_directory else None
        # Complete all file/hash/identity checks before the first network read.
        file_args = argparse.Namespace(**vars(args))
        file_args.file, file_args.destination = selector, destination / name
        file_args.reference = reference if reference and (reference.exists() or not entry.get('sha256')) else None
        file_args.sha256 = None
        plans.append(retrieval_plan(file_args))
    if len({plan['manifest_sha256'] for plan in plans}) != 1:
        raise ValueError('Manifest changed during bundle preparation')
    if len({plan['remote_path'] for plan in plans}) != len(plans):
        raise ValueError('Multiple manifest entries resolve to the same remote file')
    return {'revision': args.revision, 'destination': str(destination), 'file_count': len(plans),
            'files': plans, 'execute': args.execute, 'native_writes': False,
            'manifest_sha256': plans[0]['manifest_sha256']}


def retrieve_bundle(args):
    plan = bundle_plan(args)
    if not args.execute:
        return plan
    destination = Path(plan['destination'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='bundle-retrieval-', dir=destination.parent))
    receipt_path = attempt / 'receipt.json'
    plan.update(status='BUNDLE_DOWNLOAD_PENDING', attempt_directory=str(attempt))
    def save():
        receipt_path.write_text(json.dumps(plan, indent=2) + '\n')
    save()
    try:
        for index, item in enumerate(plan['files']):
            local = attempt / f'{index}.partial'
            command = list(item['command'])
            command[command.index('--path') + 1] = str(local)
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            (attempt / f'{index}.stderr.txt').write_text(result.stderr)
            if result.returncode != 0:
                raise ValueError(f'M365 download failed for {item["file"]}; inspect private attempt stderr')
            raw = local.read_bytes()
            item['downloaded_sha256'] = hashlib.sha256(raw).hexdigest()
            if item['downloaded_sha256'] != item['expected_sha256']:
                raise ValueError(f'Downloaded bytes differ from accepted revision: {item["file"]}')
            item.update(status='VERIFIED', bytes=len(raw))
            save()
        # mkdir is exclusive: preserve even a competing empty directory. The
        # completion receipt is written last; interrupted publication stays pending.
        destination.mkdir(exist_ok=False)
        for index, item in enumerate(plan['files']):
            os.link(attempt / f'{index}.partial', item['destination'])
        completed = {**plan, 'status': 'VERIFIED_COMPLETE_EXPORT_BUNDLE'}
        final_receipt = attempt / 'completed.json'
        final_receipt.write_text(json.dumps(completed, indent=2) + '\n')
        os.link(final_receipt, destination / '.rims-bundle-receipt.json')
        plan.update(status=completed['status'])
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        plan.update(status='FAILED_OR_UNVERIFIED', error=str(error))
        raise
    finally:
        save()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['summary', 'recover']:
        command = commands.add_parser(name)
        command.add_argument('receipt', type=Path)
    command = commands.add_parser('list-export', help='List saved manifest file identities and verification metadata')
    command.add_argument('manifest', type=Path)
    command = commands.add_parser('failed-actions', help='Extract saved failed action metadata and recovery leads')
    command.add_argument('receipt', type=Path)
    command = commands.add_parser('compare-runs', help='Compare two explicitly selected run receipts')
    command.add_argument('before', type=Path)
    command.add_argument('after', type=Path)
    command = commands.add_parser('summaries', help='Summarize explicit receipt files without merging runs')
    command.add_argument('receipts', type=Path, nargs='+')
    command = commands.add_parser('monitor', help='Evaluate one explicit monthly occurrence; never schedules or reads native state')
    command.add_argument('--month', required=True, help='YYYY-MM; expected day1 09:00 and deadline noon Brisbane')
    group = command.add_mutually_exclusive_group(required=True)
    group.add_argument('--evidence', type=Path, help='Normalized runs and explicit history_complete/reads_verified flags')
    group.add_argument('--history', type=Path, help='Exact saved M365 native run-list array; cannot infer output success')
    for option in ['as-of', 'observation-start', 'observation-end']:
        command.add_argument('--' + option, required=True)
    for option in ['environment-id', 'dataverse-flow-id', 'runtime-flow-id']:
        command.add_argument('--' + option)
    command.add_argument('--history-complete', action='store_true', help='Explicit operator assertion, not qualification by this tool')
    command.add_argument('--reads-verified', action='store_true', help='Explicit operator assertion, not qualification by this tool')
    command = commands.add_parser('compare', help='Compare saved flow definitions without native effects')
    command.add_argument('before', type=Path)
    command.add_argument('after', type=Path)
    command = commands.add_parser('retrieve', help='Plan or download one exact manifest-selected export through existing M365 access')
    command.add_argument('--manifest', type=Path, required=True)
    command.add_argument('--revision', required=True, help='Exact manifest run/flow_run_id, never latest')
    command.add_argument('--file', required=True, help='Exact manifest name, csv_file/index_file role, or Path')
    command.add_argument('--site', required=True)
    command.add_argument('--folder', help='Existing decoded folder for manifests containing names only')
    command.add_argument('--sha256', help='Accepted readback hash when absent in native manifest')
    command.add_argument('--reference', type=Path, help='Accepted saved output bytes supplying expected SHA256')
    command.add_argument('--destination', type=Path, required=True)
    command.add_argument('--execute', action='store_true', help='Read-only native download; default prints plan')
    command = commands.add_parser('retrieve-bundle', help='Download and verify every manifest-listed file into a new directory')
    command.add_argument('--manifest', type=Path, required=True)
    command.add_argument('--revision', required=True)
    command.add_argument('--site', required=True)
    command.add_argument('--folder')
    command.add_argument('--reference-directory', type=Path, help='Accepted saved bytes for all files without manifest SHA256')
    command.add_argument('--destination', type=Path, required=True)
    command.add_argument('--execute', action='store_true')
    for command in commands.choices.values():
        command.add_argument('--format', choices=['json', 'text'], default='json')
    args = parser.parse_args(argv)
    try:
        if args.command == 'monitor':
            result = monitor(args)
        elif args.command == 'compare':
            result = compare_flows(read_json(args.before), read_json(args.after))
        elif args.command == 'retrieve':
            result = retrieve(args)
        elif args.command == 'list-export':
            result = list_export(read_json(args.manifest))
        elif args.command == 'failed-actions':
            result = failed_actions(read_json(args.receipt))
        elif args.command == 'compare-runs':
            result = compare_receipts(read_json(args.before), read_json(args.after))
        elif args.command == 'summaries':
            result = summarize_receipts(args.receipts)
        elif args.command == 'retrieve-bundle':
            result = retrieve_bundle(args)
        else:
            document = read_json(args.receipt)
            result = run_summary(document) if args.command == 'summary' else recovery(document)
        print(render_text(result) if args.format == 'text' else json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
