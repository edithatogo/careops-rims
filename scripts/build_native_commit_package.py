"""Prepare a manual first-batch commit writer from the verified native export.

This is an operator-assisted bootstrap, not unattended batch acceptance. The
operator must independently correlate the supplied batch with its completed
refresh and successful extraction run. Native validation tables must be loaded
before this flow can pass. Packages and batch identifiers remain private.
"""
import argparse
import copy
import json
import uuid
import zipfile
from pathlib import Path

from build_native_retention_package import ROOT, after, compose


def build(baseline, output, batch):
    if output.exists() or output.is_symlink():
        raise ValueError('Preserve the existing package; choose a new output revision.')
    if not isinstance(batch, str):
        raise ValueError('batch must be a UUID string')
    try:
        batch = str(uuid.UUID(batch))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('batch must be a UUID string') from exc
    if not output.resolve().is_relative_to((ROOT / 'private').resolve()):
        raise ValueError('Package contains private connection references.')
    with zipfile.ZipFile(baseline) as z:
        files = {n: z.read(n) for n in z.namelist()}
    name = next(n for n in files if n.endswith('/definition.json'))
    document = json.loads(files[name])
    definition = document['properties']['definition']
    if list(definition['triggers']) != ['manual']:
        raise ValueError('Require a manual native baseline.')
    definition['triggers']['manual']['inputs']['schema'] = {
        'type': 'object', 'properties': {'text': {'title': 'Validated manifest',
        'type': 'string', 'x-ms-content-hint': 'TEXT', 'x-ms-dynamically-added': True}},
        'required': ['text']}
    old = definition['actions']
    query = copy.deepcopy(old['Run_a_query_against_a_dataset'])
    query['runAfter'] = {}
    query['inputs']['parameters']['specification/query'] = '''EVALUATE
ROW("Tests",COUNTROWS(RetentionValidation),
"Failed",COALESCE(COUNTROWS(FILTER(RetentionValidation,NOT(RetentionValidation[Passed] == TRUE()))),0),
"VerifiedSources",COUNTROWS(FILTER(StoredMetadataValidation,
StoredMetadataValidation[KeysMatch] == TRUE() && StoredMetadataValidation[MetadataValid] == TRUE() && StoredMetadataValidation[PayloadIdentitiesMatch] == TRUE() &&
((StoredMetadataValidation[Source] = "PubMed" && StoredMetadataValidation[ExpectedRecords] = 1261 && StoredMetadataValidation[ReconstructedRecords] = 1261 && StoredMetadataValidation[MetadataCharacters] = 32289819) ||
(StoredMetadataValidation[Source] = "DORA" && StoredMetadataValidation[ExpectedRecords] = 709 && StoredMetadataValidation[ReconstructedRecords] = 709 && StoredMetadataValidation[MetadataCharacters] = 2603915)))))'''
    actions = {'Read_native_validation': query,
               'Manifest': compose("@json(triggerBody()['text'])", 'Read_native_validation')}
    result = "body('Read_native_validation')['results'][0]['tables'][0]['rows'][0]"
    m = "outputs('Manifest')"
    checks = [f"equals({result}['[Tests]'],10)",
              f"equals(coalesce({result}['[Failed]'],0),0)",
              f"equals({result}['[VerifiedSources]'],2)",
              f"equals({m}['BatchID'],'{batch}')", f"equals({m}['SchemaVersion'],1)",
              f"equals({m}['Status'],'committed')", f"equals(length({m}['Sources']),2)",
              f"equals({m}['Validation']['Keysets'],true)",
              f"equals({m}['Validation']['Metadata'],true)",
              f"equals({m}['Validation']['RefreshGeneration'],true)"]
    for i, source, count, pages in [(0, 'PubMed', 1261, 39), (1, 'DORA', 709, 8)]:
        s = f"{m}['Sources'][{i}]"
        publication_table, publication_pages, chunk_table, key = (
            ('PubMedPublications', 13, 'PubMedMetadataChunks', 'PMID') if source == 'PubMed'
            else ('DoraPublications', 8, 'DoraMetadataChunks', 'DORAKey'))
        checks += [f"equals({s}['Source'],'{source}')", f"equals({s}['ExpectedRecords'],{count})",
                   f"equals({s}['PublicationTable'],'{publication_table}')",
                   f"equals({s}['PublicationPageCount'],{publication_pages})",
                   f"equals({s}['ChunkTable'],'{chunk_table}')", f"equals({s}['KeyColumn'],'{key}')",
                   f"equals({s}['PageCount'],{pages})", f"equals(length({s}['ExpectedKeys']),{count})",
                   f"equals(length(union({s}['ExpectedKeys'],{s}['ExpectedKeys'])),{count})"]
    # A Compose returning failure text still succeeds. Fail the action so its
    # Succeeded-only dependent cannot write a rejected generation.
    actions['Require_validation'] = compose("@if(and(" + ','.join(checks) + "),'VERIFIED',int('COMMIT_VALIDATION_FAILED'))", 'Manifest')
    folder = '/CHHHS Research System - DEV/01 Source archive'
    filename = f'commit-{batch}.json'
    read = copy.deepcopy(old['Get_file_content_using_path'])
    read['inputs']['parameters']['path'] = folder + '/' + filename
    read['runAfter'] = after('Require_validation')
    actions['Read_existing_commit'] = read
    absent = compose("@if(equals(outputs('Read_existing_commit')?['statusCode'],404),'ABSENT',int('COMMIT_ALREADY_EXISTS_OR_READ_FAILED'))")
    absent['runAfter'] = {'Read_existing_commit': ['Succeeded', 'Failed']}
    actions['Require_commit_absent'] = absent
    write = copy.deepcopy(old['Create_file'])
    write['runAfter'] = after('Require_commit_absent')
    write['inputs']['parameters'] = {'folderPath': folder,
        'name': filename, 'body': "@string(outputs('Manifest'))"}
    actions['Create_file'] = write
    readback = copy.deepcopy(read)
    readback['runAfter'] = after('Create_file')
    actions['Get_file_content_using_path'] = readback
    actions['Verify_commit_readback'] = compose(
        "@if(equals(base64ToString(body('Get_file_content_using_path')['$content']),string(outputs('Manifest'))),'COMMIT_READBACK_VERIFIED',int('COMMIT_READBACK_FAILED'))",
        'Get_file_content_using_path')
    definition['actions'] = actions
    title = 'CHHHS Publications - DEV validated first history commit'
    document['properties']['displayName'] = title
    files[name] = json.dumps(document).encode()
    manifest = json.loads(files['manifest.json'])
    manifest['details']['displayName'] = title
    for resource in manifest['resources'].values():
        if resource['type'] == 'Microsoft.Flow/flows':
            resource['suggestedCreationType'] = 'New'
            resource['details']['displayName'] = title
    files['manifest.json'] = json.dumps(manifest).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, content in files.items():
            z.writestr(n, content)




# Portable validation helpers from the qualified source snapshot.
import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from import_dora import OFFICIAL_HANDLE

EXPECTED_PUBMED_AUDIT_CHECKS = (
    "Full metadata publications",
    "Distinct full-metadata PMIDs",
    "Missing metadata PMIDs",
    "Unexpected metadata PMIDs",
    "Metadata reconstruction failures",
    "Metadata chunk rows",
    "Author evidence count failures",
    "Date precision failures",
    "Blank full titles",
)

NATIVE_PAGE_SIZE = 100

METADATA_CHUNK_SIZE = 20000

CONFIGURED_SEARCH_PROFILE = 'configured_facility_search_v1'

REVIEW_ONLY_SEARCH_KEYS = ('scope-review:cphu',)

PUBMED_SOURCE_TABLE_ALIASES = {
    'PubMedPublications': 'FreshPubMedPublications',
    'PubMedMetadataChunks': 'FreshPubMedMetadataChunks',
    'PubMedAuthorEvidence': 'FreshPubMedAuthorEvidence',
    'SearchAudit': 'FreshSearchAudit',
    'PubMedIngestionAudit': 'FreshPubMedIngestionAudit',
}

PUBMED_SOURCE_SNAPSHOT_TABLE = 'PubMedSourceSnapshot'

SOURCE_MATERIALIZATION_FRESHNESS = timedelta(hours=24)

def validate_pubmed_source_table_aliases(aliases):
    """Accept only the complete, known staging-model alias contract."""
    if aliases is None:
        return None
    if aliases != PUBMED_SOURCE_TABLE_ALIASES:
        raise ValueError('PubMed source table aliases differ from the allowlisted staging contract')
    return dict(PUBMED_SOURCE_TABLE_ALIASES)

def validate_processing_chain(chain, generation, *, now=None):
    """Validate a source and projection-processing chain without resetting freshness.

    v1 is the ready two-request DataOnly -> Calculate path. v2 records the
    observed recovery where Calculate completed without materializing its
    outputs and a single, scoped Full recalculation made the projections ready.
    v3 binds independently verified query projections directly to their persisted
    DataOnly source; it does not claim physical Fresh-table materialization.
    """
    if not isinstance(chain, dict) or not isinstance(generation, dict):
        raise ValueError('A captured PubMed source-materialization chain is required')
    calculated_tables = sorted(PUBMED_SOURCE_TABLE_ALIASES.values())
    common_invalid = (
            not isinstance(chain.get('model_id'), str) or not chain['model_id'].strip()
            or not isinstance(chain.get('workspace_id'), str) or not chain['workspace_id'].strip()
            or not isinstance(chain.get('definition_sha256'), str)
            or re.fullmatch(r'[0-9a-f]{64}', chain['definition_sha256']) is None
            or chain.get('source_freshness_window_hours') != 24)
    if chain.get('kind') == 'native_pubmed_processing_chain_v1':
        if (common_invalid
            or not isinstance(chain.get('model_id'), str) or not chain['model_id'].strip()
            or not isinstance(chain.get('workspace_id'), str) or not chain['workspace_id'].strip()
            or not isinstance(chain.get('definition_sha256'), str)
            or re.fullmatch(r'[0-9a-f]{64}', chain['definition_sha256']) is None
            or not isinstance(chain.get('source_request_id'), str) or not chain['source_request_id'].strip()
            or chain.get('source_type') != 'DataOnly'
            or chain.get('source_tables') != [PUBMED_SOURCE_SNAPSHOT_TABLE]
            or not isinstance(chain.get('calculation_request_id'), str) or not chain['calculation_request_id'].strip()
            or chain.get('calculation_type') != 'Calculate'
            or chain.get('calculation_tables') != calculated_tables
            or chain.get('consecutive_completed_history_verified') is not True):
            raise ValueError('PubMed processing chain source/calculation scope or evidence is invalid')
        if (chain['source_request_id'] == chain['calculation_request_id']
                or chain['model_id'] != generation.get('modelId')
                or chain['calculation_request_id'] != generation.get('refreshRequestId')):
            raise ValueError('PubMed processing chain does not match the current model generation')
        timestamp_fields = (
            ('source_started_at_utc', 'Source materialization start'),
            ('source_completed_at_utc', 'Source materialization completion'),
            ('calculation_started_at_utc', 'Fresh projection calculation start'),
            ('calculation_completed_at_utc', 'Fresh projection calculation completion'),
        )
        timestamps = [datetime.fromisoformat(_utc_timestamp(chain.get(field), label).replace('Z', '+00:00'))
                      for field, label in timestamp_fields]
        if not timestamps[0] <= timestamps[1] <= timestamps[2] <= timestamps[3]:
            raise ValueError('PubMed DataOnly source and Calculate timestamps are not ordered')
        source_completed = timestamps[1]
        final_started, final_completed = timestamps[2:]
    elif chain.get('kind') == 'native_pubmed_processing_chain_v2':
        expected_steps = (
            ('source_materialization', 'DataOnly', [PUBMED_SOURCE_SNAPSHOT_TABLE]),
            ('initial_projection', 'Calculate', calculated_tables),
            ('final_projection', 'Full', calculated_tables),
        )
        steps = chain.get('steps')
        if (common_invalid or not isinstance(steps, list) or len(steps) != len(expected_steps)
                or chain.get('consecutive_completed_history_verified') is not True):
            raise ValueError('Three-step PubMed processing chain is incomplete or lacks history verification')
        request_ids = []
        parsed_times = []
        for step, (role, process_type, tables) in zip(steps, expected_steps):
            if (not isinstance(step, dict) or step.get('role') != role
                    or step.get('type') != process_type or step.get('tables') != tables
                    or step.get('status') != 'Completed'
                    or not isinstance(step.get('request_id'), str) or not step['request_id'].strip()):
                raise ValueError('Three-step PubMed processing chain has an invalid operation scope or terminal status')
            request_ids.append(step['request_id'])
            parsed_times.append((
                datetime.fromisoformat(_utc_timestamp(step.get('started_at_utc'), f'{role} start').replace('Z', '+00:00')),
                datetime.fromisoformat(_utc_timestamp(step.get('completed_at_utc'), f'{role} completion').replace('Z', '+00:00')),
            ))
        if len(set(request_ids)) != len(request_ids):
            raise ValueError('Three-step PubMed processing chain reuses a native request ID')
        if ('history_request_ids' in chain and chain.get('history_request_ids') != request_ids):
            raise ValueError('Three-step PubMed processing history IDs differ from the ordered steps')
        final_partitions = {table: f'{table}_SourceProjection' for table in calculated_tables}
        if (steps[1].get('outputs_ready') is not False
                or str(steps[1].get('readback_error_code')) != '3241804068'
                or steps[2].get('partitions') != final_partitions):
            raise ValueError('Three-step PubMed processing chain misstates the Calculate or final Full readback')
        mode = chain.get('mode', 'stored_materialization')
        if mode == 'stored_materialization':
            if steps[2].get('outputs_ready') is not True:
                raise ValueError('Stored-table mode requires a ready Full materialization readback')
        elif mode == 'query_projection':
            if (steps[2].get('outputs_ready') is not False
                    or str(steps[2].get('readback_error_code')) != '3241804068'
                    or chain.get('physical_tables_ready') is not False
                    or generation.get('mode') != 'query_projection'
                    or generation.get('query_outputs_ready') is not True):
                raise ValueError('Query-projection mode must report physical Fresh tables as unready')
        else:
            raise ValueError('Three-step PubMed processing chain has an unsupported output mode')
        source_started, source_completed = parsed_times[0]
        prior_started, prior_completed = parsed_times[1]
        final_started, final_completed = parsed_times[2]
        if not (source_started <= source_completed <= prior_started <= prior_completed <= final_started <= final_completed):
            raise ValueError('Three-step PubMed processing history timestamps are not strictly ordered')
        if (chain['model_id'] != generation.get('modelId')
                or steps[2]['request_id'] != generation.get('refreshRequestId')):
            raise ValueError('Three-step PubMed chain final Full request is not the current model generation')
    elif chain.get('kind') == 'native_pubmed_processing_chain_v3':
        steps = chain.get('steps')
        if (common_invalid or chain.get('mode') != 'query_projection'
                or chain.get('physical_tables_ready') is not False
                or generation.get('mode') != 'query_projection'
                or generation.get('query_outputs_ready') is not True
                or chain.get('consecutive_completed_history_verified') is not True
                or not isinstance(steps, list) or len(steps) != 1):
            raise ValueError('Source-only chain requires verified ready query projections and source history')
        source = steps[0]
        if (not isinstance(source, dict)
                or source.get('role') != 'source_materialization'
                or source.get('type') != 'DataOnly'
                or source.get('tables') != [PUBMED_SOURCE_SNAPSHOT_TABLE]
                or source.get('status') != 'Completed'
                or source.get('outputs_ready') is not True
                or not isinstance(source.get('request_id'), str) or not source['request_id'].strip()
                or chain.get('history_request_ids') != [source['request_id']]
                or source['request_id'] != generation.get('refreshRequestId')
                or chain['model_id'] != generation.get('modelId')):
            raise ValueError('Source-only chain differs from its exact completed Snapshot generation')
        final_started = datetime.fromisoformat(
            _utc_timestamp(source.get('started_at_utc'), 'Source-only materialization start').replace('Z', '+00:00'))
        source_completed = final_completed = datetime.fromisoformat(
            _utc_timestamp(source.get('completed_at_utc'), 'Source-only materialization completion').replace('Z', '+00:00'))
        if final_started > source_completed:
            raise ValueError('Source-only materialization timestamps are reversed')
    else:
        raise ValueError('Unsupported PubMed processing-chain version')
    refresh_started = datetime.fromisoformat(
        _utc_timestamp(generation.get('refreshStartedAtUTC'), 'Refresh start').replace('Z', '+00:00'))
    refresh_completed = datetime.fromisoformat(
        _utc_timestamp(generation.get('refreshCompletedAtUTC'), 'Refresh completion').replace('Z', '+00:00'))
    if final_started != refresh_started or final_completed != refresh_completed:
        raise ValueError('Final PubMed projection-processing timestamps are not generation-bound')
    now = now or datetime.now(timezone.utc)
    age = now - source_completed
    if age < timedelta(minutes=-5) or age > SOURCE_MATERIALIZATION_FRESHNESS:
        raise ValueError('PubMed source materialization exceeds its fixed 24-hour freshness window')
    return chain

def validate_processing_chain_receipts(generation, source_pages, current_validation=None, *, now=None):
    """Require the same optional chain in each captured native receipt."""
    receipts = (generation, source_pages) + ((current_validation,) if current_validation is not None else ())
    present = ['processing_chain' in receipt for receipt in receipts]
    if not any(present):
        return None
    if not all(present):
        raise ValueError('Generation, source pages and current validation must carry the same processing chain')
    chains = [receipt.get('processing_chain') for receipt in receipts]
    if any(chain != chains[0] for chain in chains[1:]):
        raise ValueError('Generation, source pages and current validation processing chains differ')
    if chains[0].get('mode') == 'query_projection':
        for receipt in receipts:
            if (receipt.get('mode') != 'query_projection'
                    or receipt.get('query_outputs_ready') is not True):
                raise ValueError('Query-projection receipts must declare the same ready projection mode')
        proofs = [receipt.get('query_projection') for receipt in receipts]
        if any(not isinstance(proof, dict) for proof in proofs) or any(
                proof != proofs[0] for proof in proofs[1:]):
            raise ValueError('Generation, source pages and validation query-projection proofs differ')
    return validate_processing_chain(chains[0], generation, now=now)

def configured_search_profile():
    """Return the exact active config profile plus the qualified review-only probe."""
    path = ROOT / 'config' / 'facilities.json'
    raw = path.read_bytes()
    config = json.loads(raw)
    version = config.get('version')
    rows = config.get('rows')
    if not isinstance(version, str) or not version.strip() or not isinstance(rows, list):
        raise ValueError('Configured PubMed facility source lacks a version or rows')
    active = [row.get('FacilityKey') for row in rows if isinstance(row, dict) and row.get('Active') is True]
    if (not active or any(not isinstance(key, str) or not key.strip() for key in active)
            or len(active) != len(set(active))):
        raise ValueError('Configured PubMed facility keys must be non-empty and unique')
    return {'Profile': CONFIGURED_SEARCH_PROFILE, 'QueryVersion': version,
            'ActiveFacilityKeys': sorted(active), 'ReviewOnlyFacilityKeys': list(REVIEW_ONLY_SEARCH_KEYS),
            'FacilityConfigSHA256': hashlib.sha256(raw).hexdigest()}

def _validated_search_profile(profile):
    expected = configured_search_profile()
    if profile != expected:
        raise ValueError('Configured PubMed search profile differs from the qualified facility source')
    return expected

def page_query(table, cursor=None, source_table_aliases=None):
    """Render one exact generated source-page DAX query for its prior cursor."""
    if table not in ('PubMedPublications', 'PubMedMetadataChunks', 'PubMedAuthorEvidence', 'DoraSourceObservations', 'DoraPublications', 'DoraMetadataChunks'):
        raise ValueError('Unsupported native source page table')
    path = ROOT / 'config' / f'source-{table}-page.dax'
    query = path.read_text(encoding='utf-8')
    arity = {'PubMedPublications': 1, 'PubMedMetadataChunks': 2,
             'PubMedAuthorEvidence': 3, 'DoraSourceObservations': 1, 'DoraPublications': 1, 'DoraMetadataChunks': 2}[table]
    values = ['""', '-1', '-1'][:arity]
    if cursor is not None:
        if len(cursor) != arity:
            raise ValueError(f'{table} page cursor must contain {arity} ordered key fields')
        if not isinstance(cursor[0], str):
            raise ValueError(f'{table} page cursor first key must be text')
        values[0] = '"' + cursor[0].replace('"', '""') + '"'
        for index in range(1, arity):
            if type(cursor[index]) is not int:
                raise ValueError(f'{table} page cursor numeric fields must be integers')
            values[index] = str(cursor[index])
    variables = tuple(f'After{i}' for i in range(arity))
    for variable, value in zip(variables, values):
        pattern = rf'(?m)^VAR {variable} = .*?$'
        query, count = re.subn(pattern, f'VAR {variable} = {value}', query, count=1)
        if count != 1:
            raise ValueError('Generated page query does not contain its declared cursor variables')
    aliases = validate_pubmed_source_table_aliases(source_table_aliases)
    if aliases is not None:
        query = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(table) + r'(?![A-Za-z0-9_])',
                       aliases[table], query)
    return query

def _page_rows(source, table, key_fields, source_table_aliases=None, query_projection=None,
               search_profile=None):
    pages = source.get('pages') if isinstance(source, dict) else None
    if (not isinstance(source, dict) or source.get('page_size') != NATIVE_PAGE_SIZE
            or not isinstance(pages, list) or not pages):
        raise ValueError(f'{table} requires a page sequence and a terminal empty page')
    rows = []
    cursor = None
    empty_seen = False
    for number, page in enumerate(pages):
        if not isinstance(page, dict) or page.get('page_number') != number or page.get('http') != 200:
            raise ValueError(f'{table} page ordering or HTTP result is incomplete')
        if query_projection is None:
            query = page_query(table, cursor, source_table_aliases)
        elif table in ('SearchAudit', 'PubMedIngestionAudit'):
            from scripts.query_pubmed_projections import projection_bounded_query
            after = cursor[0] if cursor else ''
            query = projection_bounded_query(query_projection, table, search_profile, after)
        else:
            from scripts.query_pubmed_projections import projection_page_query
            query = projection_page_query(query_projection, table, cursor)
        if (page.get('query') != query
                or page.get('query_sha256') != hashlib.sha256(query.encode()).hexdigest()):
            raise ValueError(f'{table} page query/cursor fingerprint does not match the generated extractor')
        if query_projection is not None:
            projected = query_projection.get('tables', {}).get(
                PUBMED_SOURCE_TABLE_ALIASES[table], {})
            query_hashes = projected.get('page_query_sha256s')
            if (not isinstance(query_hashes, list) or number >= len(query_hashes)
                    or query_hashes[number] != hashlib.sha256(query.encode()).hexdigest()):
                raise ValueError(f'{table} page query hash differs from the saved projection proof')
        body = page.get('body')
        if not isinstance(body, dict) or body.get('error') is not None:
            raise ValueError(f'{table} page response is malformed or contains an error')
        results = body.get('results')
        tables = results[0].get('tables') if isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict) else None
        page_rows = tables[0].get('rows') if isinstance(tables, list) and len(tables) == 1 and isinstance(tables[0], dict) else None
        if not isinstance(page_rows, list) or len(page_rows) > NATIVE_PAGE_SIZE:
            raise ValueError(f'{table} page rows are missing or exceed the native page size')
        if not page_rows:
            if number != len(pages) - 1 or empty_seen:
                raise ValueError(f'{table} has an early or repeated empty page')
            empty_seen = True
            continue
        if empty_seen:
            raise ValueError(f'{table} contains data after its terminal empty page')
        keys = []
        for row in page_rows:
            if not isinstance(row, dict):
                raise ValueError(f'{table} page contains a missing or invalid key tuple')
            if any((type(row.get(f'[{key}]')) is not int if key in ('ChunkIndex', 'AuthorIndex', 'AffiliationIndex')
                    else not isinstance(row.get(f'[{key}]'), str)) for key in key_fields):
                raise ValueError(f'{table} page contains a missing or invalid key tuple')
            key = tuple(row[f'[{field}]'] for field in key_fields)
            if key_fields[0] in ('PMID',) and (not str(key[0]).isascii() or not str(key[0]).isdecimal()):
                raise ValueError(f'{table} page contains an invalid PubMed PMID')
            keys.append(key)
        if keys != sorted(keys) or (cursor is not None and keys[0] <= tuple(cursor)):
            raise ValueError(f'{table} page keys are not strictly ordered after the prior cursor')
        rows.extend(page_rows)
        cursor = keys[-1]
    if not empty_seen:
        raise ValueError(f'{table} export lacks a complete terminal-page proof')
    all_keys = [tuple(row[f'[{field}]'] for field in key_fields) for row in rows]
    if len(set(all_keys)) != len(all_keys):
        raise ValueError(f'{table} export contains duplicate page keys')
    return rows, len(pages) - 1

def reconstruct_metadata_rows(chunks, key_column):
    """Reuse exact chunk/count/UTF-8/JSON validation for either publication source."""
    grouped = {}
    for row in chunks:
        pmid = row[f'[{key_column}]']
        index, declared_count = row.get('[ChunkIndex]'), row.get('[ChunkCount]')
        declared_chars, value, encoding = row.get('[MetadataCharacters]'), row.get('[MetadataChunk]'), row.get('[Encoding]')
        if (type(index) is not int or type(declared_count) is not int or declared_count <= 0
                or type(declared_chars) is not int or declared_chars <= 0
                or not isinstance(value, str) or len(value) > METADATA_CHUNK_SIZE
                or encoding != 'UTF8-HEX' or re.fullmatch(r'[0-9a-fA-F]*', value) is None):
            raise ValueError('Metadata page has invalid chunk types, length, or encoding')
        grouped.setdefault(pmid, []).append(row)
    documents = {}
    payload_entries = []
    payload_characters = 0
    for pmid, pmid_rows in sorted(grouped.items()):
        pmid_rows.sort(key=lambda row: row['[ChunkIndex]'])
        declared_counts = {row['[ChunkCount]'] for row in pmid_rows}
        declared_chars = {row['[MetadataCharacters]'] for row in pmid_rows}
        expected_chunks = pmid_rows[0]['[ChunkCount]']
        joined = ''.join(row['[MetadataChunk]'] for row in pmid_rows)
        if (declared_counts != {expected_chunks} or len(declared_chars) != 1
                or [row['[ChunkIndex]'] for row in pmid_rows] != list(range(expected_chunks))
                or len(pmid_rows) != expected_chunks
                or sum(len(row['[MetadataChunk]']) for row in pmid_rows) != pmid_rows[0]['[MetadataCharacters]']
                or expected_chunks != (pmid_rows[0]['[MetadataCharacters]'] + METADATA_CHUNK_SIZE - 1) // METADATA_CHUNK_SIZE
                or len(joined) % 2):
            raise ValueError('Metadata chunks are incomplete or their declared lengths/counts drift')
        try:
            payload = bytes.fromhex(joined)
            payload.decode('utf-8')
            json.loads(payload)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('Reconstructed metadata payload is invalid UTF-8 JSON') from exc
        documents[pmid] = payload.decode('utf-8')
        digest = hashlib.sha256(payload).hexdigest()
        payload_entries.append([pmid, digest])
        payload_characters += pmid_rows[0]['[MetadataCharacters]']
    return documents, payload_entries, payload_characters

def validate_source_page_receipt(receipt, generation_receipt, source='PubMed'):
    """Validate same-refresh paginated native exports and reconstructed payloads."""
    if source == 'DORA':
        return _validate_dora_source_page_receipt(receipt, generation_receipt)
    if source != 'PubMed':
        raise ValueError('Only PubMed or DORA source extraction is supported')
    if not isinstance(receipt, dict) or receipt.get('kind') != 'native_source_page_extraction_v1':
        raise ValueError('A native source-page extraction receipt is required')
    aliases = validate_pubmed_source_table_aliases(receipt.get('source_table_aliases'))
    query_projection = None
    query_projection_mode = receipt.get('mode') == 'query_projection'
    if query_projection_mode:
        query_projection = receipt.get('query_projection')
        if (generation_receipt.get('mode') != 'query_projection'
                or generation_receipt.get('query_outputs_ready') is not True
                or receipt.get('query_outputs_ready') is not True
                or not isinstance(query_projection, dict)
                or generation_receipt.get('query_projection') != query_projection):
            raise ValueError('Query-projection generation and source-page proof are missing or differ')
        chain = receipt.get('processing_chain')
        if (not isinstance(chain, dict)
                or query_projection.get('definition_sha256') != chain.get('definition_sha256')):
            raise ValueError('Query-projection proof is not bound to the native definition in the processing chain')
        _validate_query_projection_proof(query_projection, chain)
    expected = {
        'generation': generation_receipt.get('generation'),
        'model_id': generation_receipt.get('modelId'),
        'request_id': generation_receipt.get('refreshRequestId'),
    }
    if any(not value or receipt.get(field) != value for field, value in expected.items()):
        raise ValueError('Source-page receipt belongs to another model, request or generation')
    if (receipt.get('refresh_status') != 'Completed'
            or receipt.get('latest_request_before') != expected['request_id']
            or receipt.get('latest_request_after') != expected['request_id']):
        raise ValueError('Source-page export is not bracketed by the exact completed refresh generation')
    processing_chain = validate_processing_chain_receipts(generation_receipt, receipt)
    sources = receipt.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('Source-page receipt lacks required sources')
    publications, publication_pages = _page_rows(sources.get('PubMedPublications'), 'PubMedPublications', ('PMID',), aliases, query_projection)
    chunks, metadata_pages = _page_rows(sources.get('PubMedMetadataChunks'), 'PubMedMetadataChunks', ('PMID', 'ChunkIndex'), aliases, query_projection)
    author_evidence, author_pages = _page_rows(sources.get('PubMedAuthorEvidence'), 'PubMedAuthorEvidence', ('PMID', 'AuthorIndex', 'AffiliationIndex'), aliases, query_projection)
    audit_rows = {}
    if query_projection_mode:
        bounded = receipt.get('bounded_tables')
        if not isinstance(bounded, dict) or set(bounded) != {'SearchAudit', 'PubMedIngestionAudit'}:
            raise ValueError('Query-projection source receipt lacks both bounded audit page streams')
        audit_rows['SearchAudit'], search_pages = _page_rows(
            bounded['SearchAudit'], 'SearchAudit', ('FacilityKey',), query_projection=query_projection,
            search_profile=receipt.get('search_profile'))
        audit_rows['PubMedIngestionAudit'], ingestion_pages = _page_rows(
            bounded['PubMedIngestionAudit'], 'PubMedIngestionAudit', ('Check',), query_projection=query_projection,
            search_profile=receipt.get('search_profile'))
        profile = _validated_search_profile(receipt.get('search_profile'))
        search_keys = [row['[FacilityKey]'] for row in audit_rows['SearchAudit']]
        ingestion_checks = [row['[Check]'] for row in audit_rows['PubMedIngestionAudit']]
        if (search_keys != sorted(profile['ActiveFacilityKeys'] + profile['ReviewOnlyFacilityKeys'])
                or len(search_keys) != len(set(search_keys))
                or ingestion_checks != sorted(EXPECTED_PUBMED_AUDIT_CHECKS)
                or len(ingestion_checks) != len(set(ingestion_checks))
                or any(row.get('[QueryVersion]') != profile['QueryVersion']
                       or type(row.get('[SearchCount]')) is not int or row['[SearchCount]'] < 0
                       or not isinstance(row.get('[QueryTranslation]'), str)
                       or not row['[QueryTranslation]'].strip()
                       or row.get('[Warnings]') is not None and not isinstance(row.get('[Warnings]'), str)
                       for row in audit_rows['SearchAudit'])
                or any(row.get('[Passed]') is not True
                       or type(row.get('[Observed]')) is not int or row['[Observed]'] < 0
                       for row in audit_rows['PubMedIngestionAudit'])):
            raise ValueError('Query-projection bounded SearchAudit or ingestion-audit rows failed exact key/value checks')
    publication_keys = [row['[PMID]'] for row in publications]
    metadata_keys = {str(row['[PMID]']) for row in chunks}
    if (any(not isinstance(key, str) for key in publication_keys)
            or len(set(publication_keys)) != len(publication_keys) or set(publication_keys) != metadata_keys):
        raise ValueError('Source-page publication and metadata identities do not reconcile')
    publication_key_set = set(publication_keys)
    author_keys = [(row['[PMID]'], row['[AuthorIndex]'], row['[AffiliationIndex]']) for row in author_evidence]
    if len(set(author_keys)) != len(author_keys) or any(key[0] not in publication_key_set or key[1] < 1 or key[2] < 1 for key in author_keys):
        raise ValueError('Author-evidence keys are duplicated, invalid, or orphaned from publications')
    _, payload_entries, payload_characters = reconstruct_metadata_rows(chunks, 'PMID')
    key_digest = hashlib.sha256(json.dumps(sorted(map(str, publication_keys)), separators=(',', ':')).encode()).hexdigest()
    payload_digest = hashlib.sha256(json.dumps(payload_entries, separators=(',', ':')).encode()).hexdigest()
    if query_projection_mode:
        for logical, pages, row_count in (
                ('PubMedPublications', publication_pages, len(publications)),
                ('PubMedMetadataChunks', metadata_pages, len(chunks)),
                ('PubMedAuthorEvidence', author_pages, len(author_evidence))):
            entry = query_projection['tables'].get(PUBMED_SOURCE_TABLE_ALIASES[logical])
            if (not isinstance(entry, dict) or entry.get('page_count') != pages
                    or entry.get('row_count') != row_count
                    or len(entry.get('page_query_sha256s', [])) != pages + 1
                    or entry.get('terminal_empty_page_verified') is not True):
                raise ValueError(f'{logical} query-projection page proof counters differ from the captured rows')
        for logical, rows, pages in (
                ('SearchAudit', audit_rows['SearchAudit'], search_pages),
                ('PubMedIngestionAudit', audit_rows['PubMedIngestionAudit'], ingestion_pages)):
            entry = query_projection['tables'][PUBMED_SOURCE_TABLE_ALIASES[logical]]
            if (entry['row_count'] != len(rows) or entry['page_count'] != pages
                    or len(entry['page_query_sha256s']) != pages + 1
                    or entry.get('terminal_empty_page_verified') is not True):
                raise ValueError(f'{logical} bounded query-projection proof counters differ from captured audit rows')
    result = {
        'Generation': expected['generation'],
        'ModelID': expected['model_id'],
        'RefreshRequestID': expected['request_id'],
        'PublicationPageCount': publication_pages,
        'MetadataPageCount': metadata_pages,
        'PublicationTerminalPageVerified': True,
        'MetadataTerminalPageVerified': True,
        'AuthorEvidencePageCount': author_pages,
        'AuthorEvidenceTerminalPageVerified': True,
        'AuthorEvidenceRowCount': len(author_evidence),
        'AuthorEvidenceKeySHA256': hashlib.sha256(json.dumps(sorted(author_keys), separators=(',', ':')).encode()).hexdigest(),
        'PublicationKeySHA256': key_digest,
        'MetadataKeySHA256': key_digest,
        'MetadataChunkCount': len(chunks),
        'MetadataPayloadCharacters': payload_characters,
        'MetadataPayloadSHA256': payload_digest,
        **({'ProcessingChain': processing_chain} if processing_chain is not None else {}),
        '_source_table_aliases': aliases,
        '_publication_keys': [str(key) for key in publication_keys],
        '_metadata_keys': sorted(metadata_keys),
    }
    if query_projection_mode:
        result['QueryProjection'] = copy.deepcopy(query_projection)
        result['QueryProjectionAudit'] = {
            'SearchAuditKeys': [row['[FacilityKey]'] for row in audit_rows['SearchAudit']],
            'IngestionAuditChecks': [row['[Check]'] for row in audit_rows['PubMedIngestionAudit']],
            'SearchAuditWarnings': '\n'.join(
                f"{row['[FacilityKey]']}: {row['[Warnings]']}" for row in audit_rows['SearchAudit']
                if isinstance(row.get('[Warnings]'), str) and row['[Warnings]']),
            'SearchAuditWarningRows': sum(
                1 for row in audit_rows['SearchAudit']
                if isinstance(row.get('[Warnings]'), str) and row['[Warnings]']),
        }
    return result

def _validate_dora_source_page_receipt(receipt, generation_receipt):
    if not isinstance(receipt, dict) or receipt.get('kind') != 'native_source_page_extraction_v1':
        raise ValueError('A native source-page extraction receipt is required')
    expected = {'generation': generation_receipt.get('generation'),
                'model_id': generation_receipt.get('modelId'),
                'request_id': generation_receipt.get('refreshRequestId')}
    if (generation_receipt.get('refreshStatus') != 'Completed'
            or generation_receipt.get('refreshComplete') is not True
            or generation_receipt.get('extractionComplete') is not True):
        raise ValueError('DoRA extraction requires the exact completed refresh generation')
    if any(not value or receipt.get(field) != value for field, value in expected.items()):
        raise ValueError('Source-page receipt belongs to another model, request or generation')
    if (receipt.get('refresh_status') != 'Completed'
            or receipt.get('latest_request_before') != expected['request_id']
            or receipt.get('latest_request_after') != expected['request_id']):
        raise ValueError('Source-page export is not bracketed by the exact completed refresh generation')
    sources = receipt.get('sources')
    if (not isinstance(sources, dict)
            or set(sources) != {'DoraPublications', 'DoraMetadataChunks'}
            or not isinstance(receipt.get('refreshed_tables'), list)
            or set(receipt['refreshed_tables']) != {'DoraHarvest', 'DoraPublications', 'DoraMetadataChunks', 'DoraIngestionAudit'}):
        raise ValueError('DoRA receipt requires only the qualified publication, metadata and audit refresh scope')
    publications, publication_pages = _page_rows(sources.get('DoraPublications'), 'DoraPublications', ('DORAKey',))
    chunks, metadata_pages = _page_rows(sources.get('DoraMetadataChunks'), 'DoraMetadataChunks', ('DORAKey', 'ChunkIndex'))
    keys = [row['[DORAKey]'] for row in publications]
    if (not keys or len(set(keys)) != len(keys)
            or any(not key.startswith('DORA:') or not OFFICIAL_HANDLE.fullmatch(key[5:]) for key in keys)):
        raise ValueError('DoRA publications require unique official canonical DORA handles')
    metadata_keys = {str(row['[DORAKey]']) for row in chunks}
    if set(keys) != metadata_keys:
        raise ValueError('DoRA publication and metadata identities do not reconcile')
    _, payload_entries, payload_characters = reconstruct_metadata_rows(chunks, 'DORAKey')
    key_digest = hashlib.sha256(json.dumps(sorted(keys), separators=(',', ':')).encode()).hexdigest()
    payload_digest = hashlib.sha256(json.dumps(payload_entries, separators=(',', ':')).encode()).hexdigest()
    return {'Generation': expected['generation'], 'ModelID': expected['model_id'],
            'RefreshRequestID': expected['request_id'], 'PublicationPageCount': publication_pages,
            'MetadataPageCount': metadata_pages, 'PublicationTerminalPageVerified': True,
            'MetadataTerminalPageVerified': True, 'MetadataChunkCount': len(chunks),
            'MetadataPayloadCharacters': payload_characters, 'MetadataPayloadSHA256': payload_digest,
            'PublicationKeySHA256': key_digest, 'MetadataKeySHA256': key_digest,
            '_publication_keys': keys, '_metadata_keys': sorted(metadata_keys)}

def _utc_timestamp(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a timezone-aware ISO-8601 timestamp')
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{label} must be a timezone-aware ISO-8601 timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{label} must include a UTC offset')
    return parsed.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def _validate_query_projection_proof(proof, chain):
    from scripts.query_pubmed_projections import TABLES as PROJECTION_TABLES
    if (not isinstance(proof, dict)
            or proof.get('kind') != 'saved_native_pubmed_var_projection_v1'
            or proof.get('compiler') != 'saved_projection_var_v1'
            or proof.get('definition_sha256') != chain.get('definition_sha256')
            or set(proof.get('tables', {})) != set(PROJECTION_TABLES.values())):
        raise ValueError('Saved native query-projection proof differs from the exact five-table definition')
    for physical, entry in proof['tables'].items():
        if (not isinstance(entry, dict)
                or entry.get('logical_table') != next(logical for logical, name in PROJECTION_TABLES.items()
                                                      if name == physical)
                or not isinstance(entry.get('expression'), str)
                or not entry['expression'].strip()
                or entry.get('expression_sha256') != hashlib.sha256(entry['expression'].encode()).hexdigest()
                or not isinstance(entry.get('columns'), list)
                or not entry['columns']
                or any(not isinstance(column, str) or not column for column in entry['columns'])
                or len(set(entry['columns'])) != len(entry['columns'])
                or type(entry.get('row_count')) is not int or entry['row_count'] < 0
                or type(entry.get('page_count')) is not int or entry['page_count'] <= 0
                or not isinstance(entry.get('page_query_sha256s'), list)
                or any(not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None
                       for value in entry['page_query_sha256s'])):
            raise ValueError(f'Saved native query-projection proof is malformed for {physical}')
    for logical in ('PubMedPublications', 'PubMedMetadataChunks', 'PubMedAuthorEvidence'):
        physical = PUBMED_SOURCE_TABLE_ALIASES[logical]
        query_path = ROOT / 'config' / f'source-{logical}-page.dax'
        selected_columns = re.findall(
            r'^\s+"([A-Za-z0-9_]+)",\s*' + re.escape(logical) + r'\[',
            query_path.read_text(encoding='utf-8'), re.M)
        if proof['tables'][physical]['columns'] != selected_columns:
            raise ValueError(f'Saved projection columns differ from the {logical} page contract')
    required_audit_columns = {
        'FreshSearchAudit': {'FacilityKey', 'QueryVersion', 'SearchCount', 'QueryTranslation', 'Warnings'},
        'FreshPubMedIngestionAudit': {'Check', 'Observed', 'Passed'},
    }
    for physical, required in required_audit_columns.items():
        if not required.issubset(proof['tables'][physical]['columns']):
            raise ValueError(f'Saved audit projection columns are incomplete for {physical}')
    return proof

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    build(args.baseline, args.output, args.batch)
    print('Prepared manual bootstrap package; native import and validation pending.')
