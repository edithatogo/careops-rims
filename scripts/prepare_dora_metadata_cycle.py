"""Prepare DoRA publication metadata in the existing two-source retained state.

No fetch, archive write, commit marker or tenant call. Reuse the native paging,
chunk reconstruction, metadata field verifier and append-only retention gates.
The existing PubMed-only native writer is not represented as a DoRA publisher.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.build_native_commit_package import _page_rows, reconstruct_metadata_rows
from scripts.import_dora import OFFICIAL_HANDLE
from scripts.publication_retained_cycle import retain, validate_state
from scripts.verify_retained_canary_metadata_values import _dora, _check_dora_identity, verify, SOURCES

DORA_CHECKS = (
    'Retained DORA records', 'Observed RSS items', 'RSS new identities', 'Union DORA records',
    'Distinct DORA keys', 'Historical DORA records lost', 'RSS title differences preserved as observations',
    'Metadata reconstruction failures', 'Date precision failures', 'Records needing explicit attribution review',
)


def current_validation_query():
    return '''EVALUATE
VAR Keys = VALUES(DoraPublications[DORAKey])
VAR MetadataKeys = VALUES(DoraMetadataChunks[DORAKey])
RETURN ROW(
    "CurrentRows", COUNTROWS(DoraPublications),
    "DistinctCurrentKeys", COUNTROWS(Keys),
    "CurrentKeysJSON", "[" & CONCATENATEX(Keys, """" & DoraPublications[DORAKey] & """", ",", DoraPublications[DORAKey], ASC) & "]",
    "MetadataRows", COUNTROWS(DoraMetadataChunks),
    "MetadataCharacters", SUMX(DoraMetadataChunks,LEN(DoraMetadataChunks[MetadataChunk])),
    "DistinctMetadataKeys", COUNTROWS(MetadataKeys),
    "MissingMetadataKeys", COALESCE(COUNTROWS(EXCEPT(Keys,MetadataKeys)),0),
    "UnexpectedMetadataKeys", COALESCE(COUNTROWS(EXCEPT(MetadataKeys,Keys)),0),
    "AuditRows", COUNTROWS(DoraIngestionAudit),
    "AuditCheckCount", DISTINCTCOUNT(DoraIngestionAudit[Check]),
    "AuditCheckNamesJSON", "[" & CONCATENATEX(VALUES(DoraIngestionAudit[Check]), """" & DoraIngestionAudit[Check] & """", ",", DoraIngestionAudit[Check], ASC) & "]",
    "AuditFailures", COALESCE(COUNTROWS(FILTER(DoraIngestionAudit,DoraIngestionAudit[Passed]=FALSE())),0),
    "AuditNullCount", COALESCE(COUNTBLANK(DoraIngestionAudit[Passed]),0))'''


def prepare(pages, generation, validation, state):
    """Return a candidate state/receipt; a rejected cycle never mutates last-good."""
    if not isinstance(state, dict):
        raise ValueError('Existing two-source retained state required')
    validate_state(state)
    required = {'model_id': generation.get('modelId'), 'request_id': generation.get('refreshRequestId'),
                'generation': generation.get('generation')}
    if (generation.get('refreshStatus') != 'Completed' or generation.get('refreshComplete') is not True
            or generation.get('extractionComplete') is not True
            or any(not value or pages.get(key) != value for key, value in required.items())
            or pages.get('kind') != 'native_source_page_extraction_v1'
            or pages.get('refresh_status') != 'Completed'
            or pages.get('latest_request_before') != required['request_id']
            or pages.get('latest_request_after') != required['request_id']
            or not {'DoraPublications','DoraMetadataChunks','DoraIngestionAudit'}.issubset(pages.get('refreshed_tables', []))):
        raise ValueError('DoRA metadata pages require the same completed refreshed source generation')
    sources = pages.get('sources', {})
    summaries, summary_pages = _page_rows(sources.get('DoraPublications'), 'DoraPublications', ('DORAKey',))
    chunks, chunk_pages = _page_rows(sources.get('DoraMetadataChunks'), 'DoraMetadataChunks', ('DORAKey','ChunkIndex'))
    documents, payloads, characters = reconstruct_metadata_rows(chunks, 'DORAKey')
    keys = [row['[DORAKey]'] for row in summaries]
    if not keys or set(keys) != set(documents):
        raise ValueError('DoRA summary/reconstructed metadata keysets differ or are empty')
    prior_keys = {'DORA:'+key[5:] for key in state['latest'] if key.startswith('dora:')}
    if not prior_keys.issubset(keys):
        raise ValueError('Prepared DoRA union lost an accepted historical identity')
    projected = {}
    for row in summaries:
        key = row['[DORAKey]']
        if not key.startswith('DORA:') or not OFFICIAL_HANDLE.fullmatch(key[5:]):
            raise ValueError('DoRA canonical publication identity required')
        metadata = json.loads(documents[key])
        if not isinstance(metadata, list) or not all(isinstance(f, dict) and {'Field','Value'}.issubset(f) for f in metadata):
            raise ValueError('DoRA complete metadata field/value list required')
        projected[key] = _dora(metadata)
        _check_dora_identity(key, {k.strip('[]'): v for k,v in row.items()}, metadata, projected[key])
        if (projected[key]['PublicationDatePrecision'] in ('unknown','year','range')
                and row.get('[PublicationDate]') is not None):
            raise ValueError('DoRA uncertain date cannot have a precise publication date')
    aliases = {f'[{name}]' for name in ('DORAKey',)+SOURCES['DORA'][3]}
    comparison_rows = [{name:value for name,value in row.items() if name in aliases} for row in summaries]
    field_check, _ = verify({'results':[{'tables':[{'rows':comparison_rows}]}]}, projected, 'DORA')
    if (field_check['status'] not in ('PASS', 'PASS_WITH_ENGINE_NORMALIZATION')
            or field_check.get('substantive_differences', 0) != 0):
        raise ValueError('DoRA summary fields differ from reconstructed metadata')
    if (validation.get('kind') != 'native_dora_current_validation_v1' or validation.get('http') != 200
            or validation.get('model_id') != required['model_id'] or validation.get('request_id') != required['request_id']
            or validation.get('refresh_status') != 'Completed'
            or validation.get('query_sha256') != hashlib.sha256(current_validation_query().encode()).hexdigest()):
        raise ValueError('DoRA audit validation belongs to another source query/generation')
    results = validation.get('body', {}).get('results')
    tables = results[0].get('tables') if isinstance(results,list) and len(results)==1 else None
    rows = tables[0].get('rows') if isinstance(tables,list) and len(tables)==1 else None
    if not isinstance(rows,list) or len(rows)!=1:
        raise ValueError('One DoRA source validation summary row required')
    counts = {'CurrentRows':len(keys),'DistinctCurrentKeys':len(keys),'MetadataRows':len(chunks),
              'MetadataCharacters':characters,'DistinctMetadataKeys':len(keys),'MissingMetadataKeys':0,
              'UnexpectedMetadataKeys':0,'AuditRows':len(DORA_CHECKS),'AuditCheckCount':len(DORA_CHECKS),
              'AuditFailures':0,'AuditNullCount':0}
    if any(type(rows[0].get(f'[{field}]')) is not int or rows[0][f'[{field}]']!=value for field,value in counts.items()):
        raise ValueError('DoRA actual source/audit counts fail metadata parity')
    for field, expected in [('CurrentKeysJSON', sorted(keys)), ('AuditCheckNamesJSON', sorted(DORA_CHECKS))]:
        try:
            actual = json.loads(rows[0].get(f'[{field}]', ''))
        except (TypeError, ValueError):
            raise ValueError('DoRA current keys/audit identities are malformed')
        # Power BI sorts text using model collation, which differs from Python
        # for names such as RSS and Retained. Identity coverage is order-free.
        if not isinstance(actual, list) or any(not isinstance(value, str) for value in actual) or sorted(actual) != expected:
            raise ValueError('DoRA current keys/audit identities differ')
    old_versions = state.get('versions', []) if isinstance(state,dict) else []
    old_latest = state.get('latest', {}) if isinstance(state,dict) else {}
    records = []
    for row in summaries:
        key = row['[DORAKey]']
        record = {k.strip('[]'): v for k,v in row.items()}
        record['MetadataJSON'] = documents[key]
        source_key = 'dora:' + key[5:]
        if source_key in old_latest:
            prior = old_versions[old_latest[source_key]]['Record']['MetadataJSON']
            old_profile = next((f.get('Value') for f in json.loads(prior) if f.get('Field')=='rims.source.format'),None)
            new_profile = next((f.get('Value') for f in json.loads(documents[key]) if f.get('Field')=='rims.source.format'),None)
            if old_profile is None and new_profile=='dora_rss_v1':
                raise ValueError('Sparse RSS cannot overwrite accepted full DoRA metadata')
        records.append((key,record))
    candidate = retain(state,records,generation=required['generation'],observed_at=generation['refreshCompletedAtUTC'],source='DORA',complete=True)
    batch = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(
        ['RIMS DORA publication metadata',required['model_id'],required['request_id'],required['generation']],separators=(',',':'))))
    prior_cycles = [cycle for cycle in state['cycles'] if cycle['source']=='DORA' and cycle['generation']==required['generation']]
    if prior_cycles and prior_cycles[0].get('BatchID') not in (None,batch):
        raise ValueError('DoRA metadata generation already belongs to another immutable batch')
    if not prior_cycles:
        candidate['cycles'][-1]['BatchID'] = batch
    key_hash = hashlib.sha256(json.dumps(sorted(keys),separators=(',',':')).encode()).hexdigest()
    descriptor = {'Source':'DORA','ExpectedRecords':len(keys),'ExpectedKeys':sorted(keys),
                  'PublicationTable':'DoraPublications','PublicationPageCount':summary_pages,
                  'ChunkTable':'DoraMetadataChunks','KeyColumn':'DORAKey','PageCount':chunk_pages,
                  'SummaryKeySHA256':key_hash,'MetadataKeySHA256':key_hash,
                  'ExpectedAuditChecksJSON':json.dumps(sorted(DORA_CHECKS),separators=(',',':')),
                  'ExpectedAuditCheckCount':len(DORA_CHECKS)}
    return candidate, {'kind':'dora_metadata_cycle_preparation_v1','status':'PASS_LOCAL_ONLY',
                       'BatchID':batch,'SourceDescriptor':descriptor,
                       'Generation':required['generation'],'ModelID':required['model_id'],'RefreshRequestID':required['request_id'],
                       'PublicationPageCount':summary_pages,'MetadataPageCount':chunk_pages,'Records':len(keys),
                       'FieldParity':field_check,'PayloadSHA256':hashlib.sha256(json.dumps(payloads,separators=(',',':')).encode()).hexdigest(),
                       'batch_commit_written':False,'native_writer_dora_role_implemented':False}
