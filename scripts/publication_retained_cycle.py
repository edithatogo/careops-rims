"""Prepare immutable automatic retention cycles from validated native source pages.

No tenant write occurs. Raw observations and all prior accepted versions remain
available; missing records and rejected cycles never delete last-good data.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.publication_policy import evaluate, load_policy, validate_policy
from scripts.build_native_commit_package import validate_source_page_receipt, _page_rows
from scripts.reconcile_pubmed_source_cycle import verify_current_validation
from scripts.organisation_enrichment import load_reference
from scripts.verify_retained_canary_metadata_values import expected as archive_metadata


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def utc(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError('Observation time must be UTC')
    return timestamp


def validate_state(state):
    if set(state) != {'kind', 'cycles', 'versions', 'latest'} or not isinstance(state['versions'], list) or not isinstance(state['latest'], dict) or not isinstance(state['cycles'], list):
        raise ValueError('Malformed retained state')
    latest = {}
    for index, version in enumerate(state['versions']):
        if not isinstance(version, dict) or version.get('RecordSHA256') != digest(version.get('Record')):
            raise ValueError('Retained record hash mismatch')
        utc(version['ObservedAtUTC'])
        latest[version['SourceKey']] = index
    if latest != state['latest']:
        raise ValueError('Latest projection lost or rewrote an accepted source identity')


def latest_projection(state):
    """Show current values and source disappearance without rewriting history."""
    validate_state(state)
    newest = {}
    for cycle in state['cycles']:
        newest[cycle['source']] = set(cycle['keys'])
    result = []
    for key, index in sorted(state['latest'].items()):
        row = copy.deepcopy(state['versions'][index])
        source = 'PubMed' if key.startswith('pubmed:') else 'DORA'
        row['PresentInLatestSourceCycle'] = key in newest.get(source, set())
        result.append(row)
    return result


def retain(state, records, *, generation, observed_at, source, complete, policy=None):
    """Pure append-only acceptance; source-specific batch replay is idempotent."""
    if complete is not True or not isinstance(records, list) or not generation:
        raise ValueError('Complete validated cycle required')
    time = utc(observed_at)
    policy = load_policy() if policy is None else validate_policy(policy)
    original = state or {'kind': 'publication_retained_versions_v1', 'cycles': [], 'versions': [], 'latest': {}}
    if original.get('kind') != 'publication_retained_versions_v1':
        raise ValueError('Unknown retention state')
    validate_state(original)
    reference = load_reference()
    prepared = [evaluate(source, source_id, record, policy=policy, reference=reference) for source_id, record in records]
    keys = [r['SourceKey'] for r in prepared]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate source identities in a cycle')
    fingerprint = digest({'records': records, 'policy': policy, 'observed_at': observed_at})
    prior = [c for c in original['cycles'] if c['source'] == source]
    replay = [c for c in prior if c['generation'] == generation]
    if replay:
        if replay[0]['sha256'] != fingerprint:
            raise ValueError('Replayed generation has different content/time/policy')
        return copy.deepcopy(original)
    if prior and time < max(utc(c['observed_at']) for c in prior):
        raise ValueError('Out-of-order cycle cannot replace latest data')
    result = copy.deepcopy(original)
    for record in prepared:
        record.update(Generation=generation, ObservedAtUTC=observed_at, RecordSHA256=digest(record['Record']))
        index = len(result['versions'])
        result['versions'].append(record)
        result['latest'][record['SourceKey']] = index
    result['cycles'].append({'source': source, 'generation': generation, 'observed_at': observed_at,
                             'sha256': fingerprint, 'keys': sorted(keys), 'policy_version': policy['version']})
    return result


def seed_archive(archive_dir, validated_dir):
    """Seed complete prior source versions from the already validated archive."""
    receipt = json.loads((validated_dir / 'validated-receipt.json').read_text())
    batch = receipt['batch_id']
    manifest = json.loads((archive_dir / f'commit-{batch}.json').read_text())
    if manifest.get('Status') != 'committed':
        raise ValueError('Prior archive must be committed')
    state = None
    for source in ('PubMed', 'DORA'):
        summaries = archive_metadata(archive_dir, validated_dir, source)
        metadata = json.loads((validated_dir / f'{source}-metadata.json').read_text())
        records = []
        for key, summary in sorted(summaries.items()):
            record = dict(summary)
            record['MetadataJSON'] = json.dumps(metadata[key], ensure_ascii=False)
            record['BaselineProvenance'] = 'validated-committed-archive'
            records.append((key, record))
        state = retain(state, records, generation=batch, observed_at=manifest['ObservedAtUTC'],
                       source=source, complete=True)
    return state


def prepare(pages, generation, validation, state=None):
    extraction = validate_source_page_receipt(pages, generation)
    verify_current_validation(validation, generation, extraction)
    if generation.get('refreshStatus') != 'Completed' or generation.get('refreshComplete') is not True or generation.get('extractionComplete') is not True:
        raise ValueError('Terminal complete source cycle required')
    summaries, _ = _page_rows(pages['sources']['PubMedPublications'], 'PubMedPublications', ('PMID',))
    chunks, _ = _page_rows(pages['sources']['PubMedMetadataChunks'], 'PubMedMetadataChunks', ('PMID', 'ChunkIndex'))
    authors, _ = _page_rows(pages['sources']['PubMedAuthorEvidence'], 'PubMedAuthorEvidence', ('PMID', 'AuthorIndex', 'AffiliationIndex'))
    grouped, affiliations = {}, {}
    for row in chunks:
        grouped.setdefault(row['[PMID]'], []).append(row)
    for row in authors:
        affiliations.setdefault(row['[PMID]'], []).append({k.strip('[]'): v for k, v in row.items()})
    records = []
    for row in summaries:
        key = row['[PMID]']
        parts = sorted(grouped[key], key=lambda x: x['[ChunkIndex]'])
        metadata_text = bytes.fromhex(''.join(x['[MetadataChunk]'] for x in parts)).decode('utf-8')
        record = {k.strip('[]'): v for k, v in row.items()}
        record.update(MetadataJSON=metadata_text, AuthorEvidence=affiliations.get(key, []),
                      AffiliationsRaw='; '.join(x['AffiliationText'] for x in affiliations.get(key, []) if isinstance(x.get('AffiliationText'), str)))
        records.append((key, record))
    retained = retain(state, records, generation=generation['generation'],
                      observed_at=generation['refreshCompletedAtUTC'], source='PubMed', complete=True)
    return retained, extraction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-pages', 'generation', 'current-validation', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--archive-dir', type=Path)
    parser.add_argument('--validated-dir', type=Path)
    args = parser.parse_args()
    private = (ROOT / 'private/ops').resolve()
    if bool(args.archive_dir) != bool(args.validated_dir) or (not args.previous and not args.archive_dir):
        parser.error('Supply previous state or both validated archive paths to preserve prior data')
    paths = [args.source_pages, args.generation, args.current_validation, args.output] + ([args.previous] if args.previous else []) + ([args.archive_dir, args.validated_dir] if args.archive_dir else [])
    if any(not p.resolve().is_relative_to(private) for p in paths) or args.output.exists():
        parser.error('Use private inputs and a new private output directory')
    # A failed validation still preserves its original bytes as diagnostic data.
    args.output.mkdir(parents=True)
    raw_inputs, inputs = [], {}
    for name, path in zip(('source-pages', 'generation', 'current-validation'), paths[:3]):
        raw = path.read_bytes()
        (args.output / (name + '.json')).write_bytes(raw)
        inputs[name] = hashlib.sha256(raw).hexdigest()
        raw_inputs.append(raw)
    previous = None
    if args.previous:
        raw = args.previous.read_bytes()
        (args.output / 'previous.json').write_bytes(raw)
        inputs['previous'] = hashlib.sha256(raw).hexdigest()
        previous_raw = raw
    try:
        loaded = [json.loads(value) for value in raw_inputs]
        if args.previous:
            previous = json.loads(previous_raw)
        if args.previous:
            receipt = json.loads(args.previous.with_name('receipt.json').read_text())
            if receipt.get('state_sha256') != hashlib.sha256(previous_raw).hexdigest():
                raise ValueError('Previous retained state lacks matching acceptance hash')
        if args.archive_dir:
            if previous is not None:
                raise ValueError('Use previous state or archive baseline, not both')
            for label, directory in (('archive', args.archive_dir), ('validated', args.validated_dir)):
                for path in directory.rglob('*'):
                    if path.is_symlink():
                        raise ValueError('Archive must not contain symlinks')
                    if path.is_file():
                        raw = path.read_bytes()
                        relative = path.relative_to(directory)
                        destination = args.output / 'baseline' / label / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(raw)
                        inputs[f'{label}/{relative}'] = hashlib.sha256(raw).hexdigest()
            previous = seed_archive(args.output / 'baseline/archive', args.output / 'baseline/validated')
        state, validation = prepare(*loaded, previous)
    except (ValueError, KeyError, TypeError) as exc:
        (args.output / 'rejected.json').write_text(json.dumps({'status': 'REJECTED', 'reason': str(exc), 'input_sha256': inputs, 'last_good_changed': False}, indent=2))
        print('REJECTED; raw diagnostic observations retained; last-good unchanged')
        return 1
    state_raw = json.dumps(state, ensure_ascii=False, indent=2).encode()
    (args.output / 'state.json').write_bytes(state_raw)
    (args.output / 'latest.json').write_text(json.dumps(latest_projection(state), ensure_ascii=False, indent=2))
    receipt = {'status': 'PASS_LOCAL_RETENTION', 'input_sha256': inputs, 'validation': validation,
               'versions': len(state['versions']), 'latest_keys': len(state['latest']), 'cycles': len(state['cycles']),
               'policy': load_policy(), 'state_sha256': hashlib.sha256(state_raw).hexdigest(),
               'tenant_written': False, 'native_retention_committed': False}
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: receipt[k] for k in ('status', 'versions', 'latest_keys', 'cycles', 'tenant_written')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
