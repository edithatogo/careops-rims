"""Prepare existing native stager actions for a frozen query-projection batch.

Local only. Reuses the accepted fixed-batch stager and existing connector hosts;
does not fetch source data, deploy, run, or emit a commit marker.
"""
import argparse
import copy
import hashlib
import json
import zipfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_native_retention_package import build_definition, compose, after
from build_native_commit_package import validate_source_page_receipt
from build_source_extraction import SOURCES
from query_pubmed_projections import projection_page_query, _declarations, VARS
from scripts.prepare_pubmed_raw_source_capture import reconstruct_responses, RAW_KIND

TABLES = ('PubMedPublications', 'PubMedMetadataChunks', 'PubMedAuthorEvidence')
FOLDER = '/CHHHS Research System - DEV/01 Source archive'
RAW_PAGE_LIMIT = 2  # Conservative string() budget, not the documented API limit.
RAW_PAGE_STRING_BUDGET = 120000  # Power Automate expression evaluation: 131072 chars.
RAW_UTC_TRANSPORT_PREFIX = 'RAWUTC|'
RAW_WIRE_FIELDS = ('SourceKind', 'RawResponseIndex', 'RawEndpoint', 'RawRequestJSON',
    'RawAcquiredUTC', 'RawHTTPStatus', 'RawByteCount', 'RawSchemaByteCount',
    'RawChunkCount', 'RawChunkIndex', 'RawPayloadBase64', 'RawSchemaBase64')
RAW_HEADER_FIELDS = ('RawResponseIndex', 'RawEndpoint', 'RawRequestJSON', 'RawAcquiredUTC',
    'RawHTTPStatus', 'RawByteCount', 'RawSchemaByteCount', 'RawChunkCount')


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('Timezone-aware UTC source time required')
    instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.tzinfo is None or instant.utcoffset().total_seconds() != 0:
        raise ValueError('Timezone-aware UTC source time required')
    return instant


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=False)


def _operation(action):
    inputs = action.get('inputs') if isinstance(action, dict) else None
    return inputs.get('host', {}).get('operationId') if isinstance(inputs, dict) else None


def _walk(actions):
    for action in actions.values():
        yield action
        for children in (action.get('actions'), action.get('else', {}).get('actions')):
            if isinstance(children, dict):
                yield from _walk(children)


def _raw_capture(capture, *, test_only, now):
    """Bind raw pages to independent coverage and one source acquisition.

    Native capture is a prerequisite supplied by the source owner; this builder
    never fetches data or manufactures that evidence from fixture rows.
    """
    if not isinstance(capture, dict) or capture.get('kind') != 'pubmed_raw_archive_capture_v1':
        raise ValueError('Qualified raw capture required')
    if not test_only and capture.get('native_capture') is not True:
        raise ValueError('Real native capture required for deployment preparation')
    for name in ('batch_id', 'model_id', 'workspace_id', 'source_request_id'):
        value = capture.get(name)
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError('Canonical capture identity required: ' + name)
    if capture.get('source_scope') != ['PubMedSourceSnapshot']:
        raise ValueError('Raw capture must bind the existing source snapshot scope')
    source_hash = capture.get('source_capture_definition_sha256')
    if not isinstance(source_hash, str) or len(source_hash) != 64 or any(c not in '0123456789abcdef' for c in source_hash):
        raise ValueError('Source capture definition fingerprint required')
    started, completed = map(_utc, (capture.get('source_started_at_utc'), capture.get('source_completed_at_utc')))
    if started > completed or completed > now:
        raise ValueError('Source acquisition time is reversed or future-dated')
    counts = (capture.get('independent_response_count'), capture.get('independent_chunk_count'))
    if any(type(v) is not int or v <= 0 for v in counts):
        raise ValueError('Independent positive integer raw counts required')
    pages = capture.get('pages')
    if not isinstance(pages, list) or not 2 <= len(pages) <= 5000:
        raise ValueError('Raw paging and terminal empty page required')
    rows, cursor = [], [-1, -1]
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or page.get('after') != cursor or not isinstance(page.get('after'), list) or any(type(v) is not int for v in page['after']):
            raise ValueError('Raw compound paging cursor drift')
        current = page.get('rows')
        if not isinstance(current, list) or len(current) > RAW_PAGE_LIMIT:
            raise ValueError('Raw page exceeds qualified query size')
        if index == len(pages) - 1:
            if current:
                raise ValueError('Terminal raw page is not empty')
        elif not current:
            raise ValueError('Empty nonterminal raw page')
        for row in current:
            if not isinstance(row, dict):
                raise ValueError('Raw page rows must be records')
            if set(row) != set(RAW_WIRE_FIELDS):
                raise ValueError('Raw wire projection schema drift')
            pair = [row.get('RawResponseIndex'), row.get('RawChunkIndex')]
            if any(type(v) is not int for v in pair) or pair <= cursor:
                raise ValueError('Raw pages are duplicated or out of order')
            cursor = pair
        if len(_compact([{'[' + k + ']': r[k] for k in RAW_WIRE_FIELDS} for r in current])) > RAW_PAGE_STRING_BUDGET:
            raise ValueError('Raw page exceeds native expression string budget')
        rows.extend(current)
    responses = reconstruct_responses(rows)
    if any(not started <= _utc(r['acquired_at_utc']) <= completed for r in responses):
        raise ValueError('Raw response observation does not correlate to source acquisition')
    if (len(responses), len(rows)) != counts:
        raise ValueError('Independent raw counts do not reconcile')
    expected = capture.get('expected_requests')
    observed = [{'endpoint': r['endpoint'], 'request': r['request']} for r in responses]
    key = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
    if not isinstance(expected, list) or sorted(map(key, expected)) != sorted(map(key, observed)):
        raise ValueError('Independent request set does not reconcile')
    status, failures = capture.get('typed_status'), capture.get('typed_projection_failures')
    audits = capture.get('typed_audit_counts')
    if not isinstance(audits, dict) or set(audits) != {'rows', 'distinct_checks', 'expected_checks', 'failed_rows'} or any(type(v) is not int or v < 0 for v in audits.values()):
        raise ValueError('Same-generation typed audit counts required')
    if status not in ('accepted', 'rejected') or type(failures) is not int or failures < 0:
        raise ValueError('Explicit typed status and failure count required')
    http_failures = sum(row['RawHTTPStatus'] != 200 for row in rows)
    typed_valid = not (failures or http_failures) and audits == {'rows': 9, 'distinct_checks': 9, 'expected_checks': 9, 'failed_rows': 0}
    if (status == 'accepted') != typed_valid:
        raise ValueError('Typed acceptance contradicts captured failures')
    return pages, rows, http_failures


def build_raw_archive_extension(document, capture, *, test_only=False, now=None):
    """Prepend raw staging to the existing manual writer, retaining commit gates.

    Frozen-batch qualification only: no new flow, hosted collector, import,
    activation or claim of routine unattended operation. The next native stage
    must prove adoption, storage permissions, exact readback and replay.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Aware current time required')
    pages, rows, http_failures = _raw_capture(capture, test_only=test_only, now=now)
    result = copy.deepcopy(document)
    definition = result['properties']['definition']
    if list(definition['triggers']) != ['manual']:
        raise ValueError('Existing manual-only archive target required')
    original = definition['actions']
    if any(n.startswith('RawStage_') for n in original):
        raise ValueError('Raw staging already present; reconcile instead of duplicating')
    roots = [name for name, action in original.items() if not action.get('runAfter')]
    if not roots or 'Batch' not in original:
        raise ValueError('Existing archive batch identity or entry drift')
    manifest_bound = False
    if capture['typed_status'] == 'accepted':
        if original['Batch'].get('inputs') != capture['batch_id']:
            raise ValueError('Existing archive batch identity drift')
        manifest = original.get('Expected_manifest', {}).get('inputs')
        if manifest is None and not test_only:
            raise ValueError('Typed accepted manifest and R1 processing chain required')
        if manifest is not None:
            steps = manifest.get('ProcessingChain', {}).get('steps', []) if isinstance(manifest, dict) else []
            source = steps[0] if steps else {}
            if (manifest.get('BatchID') != capture['batch_id'] or manifest.get('ModelID') != capture['model_id']
                    or source.get('role') != 'source_materialization' or source.get('type') != 'DataOnly'
                    or source.get('tables') != ['PubMedSourceSnapshot'] or source.get('status') != 'Completed'
                    or source.get('request_id') != capture['source_request_id']
                    or _utc(source.get('started_at_utc')) != _utc(capture['source_started_at_utc'])
                    or _utc(source.get('completed_at_utc')) != _utc(capture['source_completed_at_utc'])):
                raise ValueError('Raw and typed manifest source generation differ; rebase before deployment')
            manifest_bound = True
    operations = list(_walk(original))
    queries = [a for a in operations if _operation(a) == 'ExecuteDatasetQuery']
    reads = [a for a in operations if _operation(a) == 'GetFileContentByPath']
    writes = [a for a in operations if _operation(a) == 'CreateFile']
    if not queries or not reads or not writes:
        raise ValueError('Qualified query/read/create operations are missing')
    if any(q['inputs']['parameters'].get('datasetid') != capture['model_id'] or q['inputs']['parameters'].get('groupid') != capture['workspace_id'] for q in queries):
        raise ValueError('Existing query/model/workspace binding drift')
    if any(w['inputs']['parameters'].get('folderPath') != FOLDER for w in writes):
        raise ValueError('Archive folder drift; qualify the actual existing target')
    query, read, write = queries[0], reads[0], writes[0]
    actions = {}
    def operation(name, template, parameters, previous):
        a = copy.deepcopy(template)
        a['inputs']['parameters'].update(parameters)
        a['runAfter'] = after(previous) if previous else {}
        if 'metadata' in a:
            a['metadata']['operationMetadataId'] = str(uuid5(NAMESPACE_URL, capture['batch_id'] + '/' + name))
        actions[name] = a
    def add_compose(name, value, previous):
        actions[name] = compose(value, previous)
    def freeze_file(prefix, name, content, previous):
        add_compose(prefix + '_Content', "@outputs('" + prefix + "_Expected')" if prefix + '_Expected' in actions else content, previous)
        path = "@concat('" + FOLDER + "/'," + name[1:] + ")" if name.startswith('@') else FOLDER + '/' + name
        operation(prefix + '_Existing', read, {'path': path}, prefix + '_Content')
        create = copy.deepcopy(write)
        create['inputs']['parameters'].update(folderPath=FOLDER, name=name, body="@outputs('" + prefix + "_Content')")
        create['runAfter'] = after(prefix + '_Require_absent')
        if 'metadata' in create:
            create['metadata']['operationMetadataId'] = str(uuid5(NAMESPACE_URL, capture['batch_id'] + '/' + prefix + '_Write'))
        actions[prefix + '_Exists'] = {'type': 'If', 'expression': "@equals(outputs('" + prefix + "_Existing')?['statusCode'],200)",
            'runAfter': {prefix + '_Existing': ['Succeeded', 'Failed']},
            'actions': {prefix + '_Require_replay': compose("@if(equals(base64ToString(body('" + prefix + "_Existing')['$content']),outputs('" + prefix + "_Content')),'REPLAY_VERIFIED',int('RAW_ARCHIVE_CONFLICT'))")},
            'else': {'actions': {prefix + '_Require_absent': compose("@if(equals(outputs('" + prefix + "_Existing')?['statusCode'],404),'ABSENT',int('RAW_ARCHIVE_READ_FAILED'))"), prefix + '_Write': create}}}
        operation(prefix + '_Readback', read, {'path': path}, prefix + '_Exists')
        add_compose(prefix + '_Require_exact_readback', "@if(equals(base64ToString(body('" + prefix + "_Readback')['$content']),outputs('" + prefix + "_Content')),'RAW_BYTES_VERIFIED',int('RAW_ARCHIVE_READBACK_MISMATCH'))", prefix + '_Readback')
        return prefix + '_Require_exact_readback'
    counts_query = (Path(__file__).resolve().parents[1] / 'config/source-PubMedRawResponseChunks-counts.dax').read_text()
    operation('RawStage_Current_counts', query, {'specification/query': counts_query, 'specification/serializerSettings/includeNulls': True}, None)
    # Require an actual singleton result, not a missing envelope interpreted as zero.
    row_path = "body('RawStage_Current_counts')?['results'][0]?['tables'][0]?['rows']"
    expected = {'RawResponses': capture['independent_response_count'], 'RawChunkRows': capture['independent_chunk_count'],
        'TypedProjectionFailures': capture['typed_projection_failures'], 'HTTPFailureChunkRows': http_failures}
    expected.update({'CurrentAuditRows': capture['typed_audit_counts']['rows'],
        'CurrentAuditDistinctChecks': capture['typed_audit_counts']['distinct_checks'],
        'CurrentAuditExpectedChecks': capture['typed_audit_counts']['expected_checks'],
        'CurrentAuditFailedRows': capture['typed_audit_counts']['failed_rows']})
    conditions = ["empty(body('RawStage_Current_counts')?['error'])", "empty(body('RawStage_Current_counts')?['results'][0]?['error'])",
        "equals(length(body('RawStage_Current_counts')?['results']),1)", "equals(length(body('RawStage_Current_counts')?['results'][0]?['tables']),1)"]
    conditions += [f"equals({row_path}[0]?['[{k}]'],{v})" for k, v in expected.items()]
    add_compose('RawStage_Require_current_counts', "@if(and(equals(length(" + row_path + "),1)," + ','.join(conditions) + "),'RAW_COUNTS_VERIFIED',int('RAW_SOURCE_COUNT_DRIFT'))", 'RawStage_Current_counts')
    files = []
    page_template = (Path(__file__).resolve().parents[1] / 'config/source-PubMedRawResponseChunks-page.dax').read_text()
    # The connector parses ISO-looking strings as dates and drops fractional
    # trailing zeroes (.350 becomes .35). Protect the source text in transit;
    # remove only this verified prefix before any existing byte/header checks.
    utc_projection = '"RawAcquiredUTC", PubMedSourceSnapshot[RawAcquiredUTC]'
    if page_template.count(utc_projection) != 1:
        raise ValueError('Raw timestamp projection changed; qualify transport before staging')
    page_template = page_template.replace(utc_projection,
        '"RawAcquiredUTC", "' + RAW_UTC_TRANSPORT_PREFIX + '" & PubMedSourceSnapshot[RawAcquiredUTC]')
    headers = list({r['RawResponseIndex']: {k: r[k] for k in RAW_HEADER_FIELDS} for r in rows}.values())
    page_plan = []
    for index, page in enumerate(pages):
        wire_rows = [{'[' + k + ']': row[k] for k in RAW_WIRE_FIELDS} for row in page['rows']]
        content = _compact(wire_rows)
        name = f"raw-observation-{capture['batch_id']}-PubMedRawResponseChunks-{index}.json" if page['rows'] else None
        page_plan.append({'after': page['after'], 'name': name,
            'keys': [{'RawResponseIndex': r['RawResponseIndex'], 'RawChunkIndex': r['RawChunkIndex'],
                'RawPayloadChars': len(r['RawPayloadBase64']), 'RawSchemaChars': len(r['RawSchemaBase64'])} for r in page['rows']]})
        if page['rows']:
            files.append({'name': name, 'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'rows': len(page['rows'])})
    add_compose('RawStage_ResponseHeaders', headers, 'RawStage_Require_current_counts')
    add_compose('RawStage_Page_plan', page_plan, 'RawStage_ResponseHeaders')
    add_compose('RawStage_Page_query_template', page_template.replace('{{PAGE_SIZE}}', str(RAW_PAGE_LIMIT)), 'RawStage_Page_plan')
    # Reuse one serial loop. Payloads remain in the source/file stream, not in the
    # flow definition; page metadata is compact and graph size is constant.
    top_actions = actions
    actions = {}
    dax = "@replace(replace(outputs('RawStage_Page_query_template'),'{{AFTER_RESPONSE_INDEX}}',string(items('RawStage_Pages')['after'][0])),'{{AFTER_CHUNK_INDEX}}',string(items('RawStage_Pages')['after'][1]))"
    operation('RawStage_Page_Query', query, {'specification/query': dax, 'specification/serializerSettings/includeNulls': True}, None)
    query_rows = "body('RawStage_Page_Query')?['results'][0]?['tables'][0]?['rows']"
    add_compose('RawStage_Page_Require_envelope', "@if(and(empty(body('RawStage_Page_Query')?['error']),empty(body('RawStage_Page_Query')?['results'][0]?['error']),equals(length(body('RawStage_Page_Query')?['results']),1),equals(length(body('RawStage_Page_Query')?['results'][0]?['tables']),1)),'RAW_QUERY_OK',int('RAW_QUERY_ENVELOPE_FAILED'))", 'RawStage_Page_Query')
    actions['RawStage_Page_Bad_timestamp_transport'] = {'type': 'Query', 'inputs': {
        'from': '@' + query_rows,
        'where': "@not(startsWith(coalesce(item()?['[RawAcquiredUTC]'],''),'" + RAW_UTC_TRANSPORT_PREFIX + "'))"},
        'runAfter': after('RawStage_Page_Require_envelope')}
    add_compose('RawStage_Page_Require_timestamp_transport',
        "@if(equals(length(body('RawStage_Page_Bad_timestamp_transport')),0),'RAW_TIMESTAMP_TEXT_VERIFIED',int('RAW_TIMESTAMP_TRANSPORT_INVALID'))",
        'RawStage_Page_Bad_timestamp_transport')
    wire_select = {'[' + k + ']': "@item()?['[" + k + "]']" for k in RAW_WIRE_FIELDS}
    wire_select['[RawAcquiredUTC]'] = "@substring(item()?['[RawAcquiredUTC]']," + str(len(RAW_UTC_TRANSPORT_PREFIX)) + ")"
    actions['RawStage_Page_Rows'] = {'type': 'Select', 'inputs': {'from': '@' + query_rows,
        'select': wire_select}, 'runAfter': after('RawStage_Page_Require_timestamp_transport')}
    actions['RawStage_Page_Keys'] = {'type': 'Select', 'inputs': {'from': "@body('RawStage_Page_Rows')", 'select': {
        'RawResponseIndex': "@item()?['[RawResponseIndex]']", 'RawChunkIndex': "@item()?['[RawChunkIndex]']",
        'RawPayloadChars': "@length(item()?['[RawPayloadBase64]'])", 'RawSchemaChars': "@length(item()?['[RawSchemaBase64]'])"}}, 'runAfter': after('RawStage_Page_Rows')}
    actions['RawStage_Page_Headers'] = {'type': 'Select', 'inputs': {'from': "@body('RawStage_Page_Rows')",
        'select': {k: "@item()?['[" + k + "]']" for k in RAW_HEADER_FIELDS}}, 'runAfter': after('RawStage_Page_Keys')}
    actions['RawStage_Page_Header_drift'] = {'type': 'Query', 'inputs': {'from': "@body('RawStage_Page_Headers')",
        'where': "@not(contains(outputs('RawStage_ResponseHeaders'),item()))"}, 'runAfter': after('RawStage_Page_Headers')}
    add_compose('RawStage_Page_Require_current_capture', "@if(and(equals(body('RawStage_Page_Keys'),items('RawStage_Pages')['keys']),equals(length(body('RawStage_Page_Header_drift')),0),lessOrEquals(length(string(body('RawStage_Page_Rows'))),120000)),'RAW_CAPTURE_VERIFIED',int('RAW_SOURCE_GENERATION_DRIFT'))", 'RawStage_Page_Header_drift')
    loop_prefix = actions
    actions = {}
    freeze_file('RawStage_Page', "@items('RawStage_Pages')['name']", "@string(body('RawStage_Page_Rows'))", None)
    write_branch = actions
    loop_prefix['RawStage_Page_Has_rows'] = {'type': 'If', 'expression': "@greater(length(body('RawStage_Page_Rows')),0)",
        'runAfter': after('RawStage_Page_Require_current_capture'), 'actions': write_branch, 'else': {'actions': {}}}
    actions = top_actions
    actions['RawStage_Pages'] = {'type': 'Foreach', 'foreach': "@outputs('RawStage_Page_plan')",
        'runtimeConfiguration': {'concurrency': {'repetitions': 1}}, 'runAfter': after('RawStage_Page_query_template'), 'actions': loop_prefix}
    previous = 'RawStage_Pages'
    indexes = []
    page_files = [{k: v for k, v in f.items() if k != 'content'} for f in files]
    for start in range(0, len(page_files), 100):
        index = len(indexes)
        part = {'kind': 'raw_observation_file_index_v1', 'batch_id': capture['batch_id'],
            'source_request_id': capture['source_request_id'], 'part_index': index, 'files': page_files[start:start+100]}
        text = _compact(part)
        if len(text) > RAW_PAGE_STRING_BUDGET:
            raise ValueError('Raw observation index exceeds qualified readback budget')
        name = f"raw-observation-{capture['batch_id']}-descriptor-part-{index}.json"
        indexes.append({'name': name, 'descriptor': part})
        files.append({'name': name, 'content': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'rows': 0})
    add_compose('RawStage_Descriptor_part_plan', indexes, previous)
    top_actions = actions
    actions = {}
    freeze_file('RawStage_Index', "@items('RawStage_Descriptor_parts')['name']", "@string(items('RawStage_Descriptor_parts')['descriptor'])", None)
    index_actions = actions
    actions = top_actions
    actions['RawStage_Descriptor_parts'] = {'type': 'Foreach', 'foreach': "@outputs('RawStage_Descriptor_part_plan')",
        'runtimeConfiguration': {'concurrency': {'repetitions': 1}}, 'runAfter': after('RawStage_Descriptor_part_plan'), 'actions': index_actions}
    previous = 'RawStage_Descriptor_parts'
    descriptor = {'kind': 'raw_observation_descriptor_v1', 'batch_id': capture['batch_id'],
        'source_request_id': capture['source_request_id'], 'model_id': capture['model_id'], 'workspace_id': capture['workspace_id'],
        'source_started_at_utc': capture['source_started_at_utc'], 'source_completed_at_utc': capture['source_completed_at_utc'],
        'source_capture_definition_sha256': capture['source_capture_definition_sha256'],
        'typed_status': capture['typed_status'], 'typed_audit_counts': capture['typed_audit_counts'], 'accepted_commit': False,
        'independent_response_count': capture['independent_response_count'], 'independent_chunk_count': len(rows),
        'data_file_count': len(page_files), 'file_parts': [{k: v for k, v in f.items() if k != 'content'} for f in files[len(page_files):]]}
    content = _compact(descriptor)
    if len(content) > RAW_PAGE_STRING_BUDGET:
        raise ValueError('Observation descriptor exceeds qualified readback budget')
    name = f"raw-observation-{capture['batch_id']}-descriptor.json"
    previous = freeze_file('RawStage_Descriptor', name, content, previous)
    files.append({'name': name, 'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'rows': 0})
    # The original typed writer/commit path can run only after raw readback AND
    # current typed proof. Old calculated audits or response timestamps are not used.
    acceptance = ["equals('" + capture['typed_status'] + "','accepted')",
        "equals(" + row_path + "[0]?['[TypedProjectionFailures]'],0)", "equals(" + row_path + "[0]?['[HTTPFailureChunkRows]'],0)",
        "equals(" + row_path + "[0]?['[CurrentAuditRows]'],9)", "equals(" + row_path + "[0]?['[CurrentAuditDistinctChecks]'],9)",
        "equals(" + row_path + "[0]?['[CurrentAuditExpectedChecks]'],9)", "equals(" + row_path + "[0]?['[CurrentAuditFailedRows]'],0)",
        "greaterOrEquals(ticks(utcNow()),ticks('" + capture['source_completed_at_utc'] + "'))",
        "lessOrEquals(sub(ticks(utcNow()),ticks('" + capture['source_completed_at_utc'] + "')),864000000000)"]
    add_compose('RawStage_Require_accepted_projection', "@if(and(" + ','.join(acceptance) + "),'ACCEPTED_SOURCE_ONLY',int('RAW_TYPED_GENERATION_REJECTED'))", previous)
    for name in roots:
        original[name]['runAfter'] = after('RawStage_Require_accepted_projection')
    definition['actions'] = {**actions, **original}
    evidence = {'kind': 'raw_archive_extension_preparation_v1', 'status': 'SYNTHETIC_LOCAL_ONLY' if test_only else 'PREPARED_NOT_DEPLOYED',
        'batch_id': capture['batch_id'], 'new_actions': list(actions), 'modified_original_entry_dependencies': roots,
        'files': files, 'observation_descriptor': descriptor, 'native_written': False,
        'routine_automation_accepted': False, 'atomic_concurrent_create_guarantee': False,
        'raw_page_limit': RAW_PAGE_LIMIT, 'native_page_string_budget': RAW_PAGE_STRING_BUDGET,
        'payloads_embedded_in_definition': False, 'full_capture_byte_equality_native_verified': False,
        'typed_manifest_bound_to_raw_r1': manifest_bound,
        'integration': 'Frozen batch native qualification; preserve original trigger/connections/typed actions. Native capture prerequisite and explicit writer handoff required.'}
    return result, evidence


def prepare_raw(capture_path, definition_path, prefix):
    """Prepare a same-object raw extension from real capture and native export.

    No ZIP editing or native writes. Output is private clientdata JSON plus exact
    rollback and staged content for the existing deployment/qualification route.
    """
    private_root = (Path(__file__).resolve().parents[1] / 'private/ops').resolve()
    capture_path, definition_path, prefix = map(lambda p: p.resolve(), (capture_path, definition_path, prefix))
    if any(not p.is_relative_to(private_root) for p in (capture_path, definition_path, prefix)):
        raise ValueError('Native captures/definitions/outputs must stay under private/ops')
    outputs = [Path(str(prefix) + suffix) for suffix in ('candidate-private.json', 'rollback-private.json', 'receipt-private.json', 'files')]
    if any(p.exists() for p in outputs) or capture_path in outputs or definition_path in outputs:
        raise ValueError('Use distinct new outputs; preserve prior evidence')
    capture = json.loads(capture_path.read_text())
    source_bytes = definition_path.read_bytes()
    document = json.loads(source_bytes)
    if 'value' in document:
        if not isinstance(document['value'], list) or len(document['value']) != 1:
            raise ValueError('Exact single-flow native readback required')
        raw = document['value'][0]['definition']
        document = json.loads(raw) if isinstance(raw, str) else raw
    candidate, evidence = build_raw_archive_extension(document, capture)
    directory = outputs[-1]
    directory.mkdir(parents=True, exist_ok=False)
    for artifact in evidence['files']:
        (directory / artifact['name']).write_text(artifact['content'], encoding='utf-8')
    payload = (_compact(candidate) + '\n').encode()
    outputs[0].write_bytes(payload)
    outputs[1].write_bytes(source_bytes)
    evidence.update(preimage_sha256=hashlib.sha256(source_bytes).hexdigest(),
        candidate_sha256=hashlib.sha256(payload).hexdigest(), capture_sha256=hashlib.sha256(capture_path.read_bytes()).hexdigest(),
        candidate=str(outputs[0]), rollback=str(outputs[1]))
    for artifact in evidence['files']:
        del artifact['content']
    outputs[2].write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


def prepare(pages_path, generation_path, manifest_path, template_path, prefix):
    if not prefix.resolve().is_relative_to((Path(__file__).resolve().parents[1] / 'private').resolve()):
        raise ValueError('Private output required')
    pages = json.loads(pages_path.read_text())
    generation = json.loads(generation_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    extraction = validate_source_page_receipt(pages, generation)
    extraction = {k: v for k, v in extraction.items() if k not in ('_publication_keys', '_metadata_keys')}
    if manifest['SourceExtraction'] != extraction:
        raise ValueError('Manifest and complete capture differ')
    batch = manifest['BatchID']
    with zipfile.ZipFile(template_path) as z:
        document = json.loads(z.read(next(n for n in z.namelist() if n.endswith('/definition.json'))))
    baseline = document['properties']['definition']['actions']
    if 'Create_file' not in baseline:
        baseline['Create_file'] = copy.deepcopy(baseline['Condition_commit_marker']['else']['actions']['Create_file'])
    qualified_queries = [a for a in baseline.values() if isinstance(a.get('inputs'), dict) and a['inputs'].get('host', {}).get('operationId') == 'ExecuteDatasetQuery']
    if len(qualified_queries) != 1 or qualified_queries[0]['inputs']['parameters']['datasetid'] != manifest['ModelID']:
        raise ValueError('Template must query the exact accepted model')
    # The accepted raw staging template supplies all three qualified actions.
    native = build_definition(document, tables=TABLES, batch=batch)
    actions = native['properties']['definition']['actions']
    proof = pages['query_projection']
    for table in TABLES:
        query = projection_page_query(proof, table)
        loop = actions[table + '_Pages']['actions']
        actions[table + '_Pages']['limit']['count'] = len(pages['sources'][table]['pages'])
        query_action = loop[table + '_Query']
        loop[table + '_Saved_query'] = compose(query)
        expression = "outputs('" + table + "_Saved_query')"
        for i in range(len(SOURCES[table])):
            original = 'VAR After' + str(i) + ' = ' + ('""' if i == 0 else '-1')
            cursor = "variables('" + table + '_cursor_' + str(i) + "')"
            value = "concat('\"',replace(" + cursor + ",'\"','\"\"'),'\"')" if i == 0 else 'string(' + cursor + ')'
            expression = "replace(" + expression + ", '" + original + "',concat('VAR After" + str(i) + " = '," + value + '))'
        query_action['inputs']['parameters']['specification/query'] = '@' + expression
        query_action['runAfter'] = after(table + '_Saved_query')
        keys = ','.join('"' + k + '",[' + k + ']' for k in SOURCES[table])
        key_query = 'EVALUATE\n' + _declarations(proof, (table,)) + '\nRETURN SELECTCOLUMNS(' + VARS[table] + ',' + keys + ')'
        for suffix in ('Expected_keys', 'Final_keys'):
            actions[table + '_' + suffix]['inputs']['parameters']['specification/query'] = key_query
    files = []
    totals = {}
    directory = Path(str(prefix) + 'files')
    directory.mkdir(parents=True, exist_ok=True)
    for table, source in {**pages['sources'], **pages['bounded_tables']}.items():
        rows_all = []
        for page in source['pages']:
            rows = page['body']['results'][0]['tables'][0].get('rows', [])
            if not rows:
                continue
            content = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
            name = f'uncommitted-{batch}-{table}-{len([f for f in files if f["table"] == table])}.json'
            raw = content.encode()
            (directory / name).write_bytes(raw)
            assert json.loads((directory / name).read_bytes()) == rows
            files.append({'table': table, 'name': name, 'rows': len(rows), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            rows_all.extend(rows)
        totals[table] = len(rows_all)
    # Audits are complete bounded captured sidecars; preserve literal contents.
    old = document['properties']['definition']['actions']
    previous = 'PubMedAuthorEvidence_Require_complete_keyset'
    for table in ('SearchAudit', 'PubMedIngestionAudit'):
        name = f'uncommitted-{batch}-{table}-0.json'
        content = (directory / name).read_text()
        start = table + '_Captured_content'
        actions[start] = compose(content, previous)
        read = copy.deepcopy(old['Get_file_content_using_path'])
        read['inputs']['parameters']['path'] = FOLDER + '/' + name
        read['runAfter'] = after(start)
        actions[table + '_Existing'] = read
        write = copy.deepcopy(old['Create_file'])
        write['inputs']['parameters'].update(folderPath=FOLDER, name=name, body="@outputs('" + start + "')")
        write['runAfter'] = after(table + '_Require_absent')
        actions[table + '_Exists'] = {'type': 'If', 'expression': "@equals(outputs('" + table + "_Existing')?['statusCode'],200)", 'runAfter': {table + '_Existing': ['Succeeded', 'Failed']}, 'actions': {}, 'else': {'actions': {table + '_Require_absent': compose("@if(equals(outputs('" + table + "_Existing')?['statusCode'],404),'ABSENT',int('ARCHIVE_READ_FAILED'))"), table + '_Write': write}}}
        readback = copy.deepcopy(read)
        readback['runAfter'] = after(table + '_Exists')
        actions[table + '_Readback'] = readback
        previous = table + '_Require_exact_readback'
        actions[previous] = compose("@if(equals(base64ToString(body('" + table + "_Readback')['$content']),outputs('" + start + "')),'VERIFIED',int('ARCHIVE_CONFLICT'))", table + '_Readback')
    del actions['Staging_only']
    actions['Require_archive_persisted'] = compose('All three paginated source keysets and both audit sidecars verified; commit marker may follow only after this action succeeds.', previous)
    fragment = {'kind': 'query_projection_archive_persistence_fragment_v1', 'batch_id': batch, 'actions': actions, 'marker_run_after': after('Require_archive_persisted'), 'integration': 'Replace old staging startup query with the existing current-validation action; keep validation before Batch, preserve all serial initializers and loops. Gate marker and replay-marker handling on Require_archive_persisted. Preserve existing manual trigger and connector references.'}
    Path(str(prefix) + 'fragment-private.json').write_text(json.dumps(fragment, ensure_ascii=False, separators=(',', ':')))
    receipt = {'batch_id': batch, 'capture_sha256': hashlib.sha256(pages_path.read_bytes()).hexdigest(), 'files': files, 'totals': totals, 'file_count': len(files), 'reconstruction_equal': True, 'native_written': False, 'folder': FOLDER, 'marker_dependency': 'Require_archive_persisted', 'source_extraction': extraction}
    Path(str(prefix) + 'receipt-private.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'file_count': len(files), 'totals': totals, 'native_written': False}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('pages', 'generation', 'manifest', 'template', 'prefix'):
        p.add_argument('--' + key, type=Path)
    p.add_argument('--raw-capture', type=Path)
    p.add_argument('--native-definition', type=Path)
    p.add_argument('--raw-prefix', type=Path)
    a = p.parse_args()
    if a.raw_capture or a.native_definition or a.raw_prefix:
        if not all((a.raw_capture, a.native_definition, a.raw_prefix)) or any((a.pages, a.generation, a.manifest, a.template, a.prefix)):
            p.error('Use all three raw-mode inputs separately from the existing typed mode')
        result = prepare_raw(a.raw_capture, a.native_definition, a.raw_prefix)
        print(json.dumps({'status': result['status'], 'file_count': len(result['files']), 'native_written': False}))
    else:
        if not all((a.pages, a.generation, a.manifest, a.template, a.prefix)):
            p.error('Existing typed mode requires pages, generation, manifest, template and prefix')
        prepare(a.pages, a.generation, a.manifest, a.template, a.prefix)
