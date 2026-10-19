"""Offline preparation of optional RIMS references; no hosted runtime or access grant.

Inputs are already accepted, permission-filtered canonical snapshots. Identifiers
and evidence hashes are provenance, never authentication or identity matching.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

CONTRACT = 'careops-rims.references/1'
SOURCES = {'publication': 'careops-rims/publications', 'organisation': 'careops-rims/organisations'}


def text(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f'{label}: expected nonblank unpadded text')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def prepare(snapshot, context, allowed_keys):
    """Copy only explicit canonical identities; do not enrich, infer or merge."""
    required = {'provider_version', 'consumer', 'consumer_version', 'correlation_id',
                'purpose', 'classification', 'captured_at', 'source_revision', 'evidence_url'}
    if set(context) != required:
        raise ValueError('Unsupported context fields')
    for key in required:
        text(context[key], key)
    if context['purpose'] != 'evidence-navigation' or context['classification'] not in {'public', 'internal'}:
        raise ValueError('Unsupported purpose/classification')
    stamp = datetime.fromisoformat(context['captured_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('captured_at requires timezone')
    url = urlsplit(context['evidence_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Expected HTTPS evidence URL without credentials, query or fragment')
    if set(snapshot) != {'publications', 'organisation_reference'}:
        raise ValueError('Unexpected snapshot shape')
    if not isinstance(snapshot['publications'], list) or not isinstance(snapshot['organisation_reference'], dict):
        raise ValueError('Expected canonical publication rows and organisation reference')
    reference = snapshot['organisation_reference']
    version = text(reference['version'], 'organisation reference version')
    organisations = {}
    for row in reference['units']:
        key = text(row['OrganisationKey'], 'OrganisationKey')
        if key in organisations:
            raise ValueError('Duplicate OrganisationKey')
        organisations[key] = row
    if len(snapshot['publications']) + len(organisations) > 50:
        raise ValueError('Bounded adapter accepts at most50 references')
    rows, seen = [], set()

    def append(kind, key, revision, label, **extra):
        identity = (SOURCES[kind], key)
        if identity not in allowed_keys:
            raise PermissionError('Reference outside supplied authorised scope')
        if identity in seen:
            raise ValueError('Duplicate source-qualified identity')
        seen.add(identity)
        rows.append({'source': SOURCES[kind], 'kind': kind, 'id': text(key, 'id'),
                     'revision': text(revision, 'revision'), 'label': text(label, 'label'),
                     'evidence_url': context['evidence_url'], **extra})

    for key, row in organisations.items():
        append('organisation', key, version, row['OrganisationName'], links=[], links_state='not_provided')
    for row in snapshot['publications']:
        key = text(row['CanonicalKey'], 'CanonicalKey')
        raw = row.get('OrganisationKeys')
        if raw is None:
            raw = ''
        if not isinstance(raw, str):
            raise ValueError('OrganisationKeys must retain canonical semicolon text')
        keys = raw.split(';') if raw else []
        if len(keys) != len(set(keys)) or any(not k or k != k.strip() for k in keys):
            raise ValueError('Ambiguous organisation keys')
        links = []
        resolved = row.get('OrganisationReferenceVersion') == version and all(k in organisations for k in keys)
        if keys and resolved:
            method = row.get('OrganisationMatchMethod')
            confidence = row.get('OrganisationMatchConfidence')
            if method not in {'explicit-affiliation-alias', 'unmatched', 'review-required'} or confidence not in {'high', 'medium', 'low', 'unknown'}:
                raise ValueError('Unknown existing organisation assertion state')
            links = [{'source': SOURCES['organisation'], 'id': k, 'revision': version,
                      'status': method, 'confidence': confidence} for k in keys]
        append('publication', key, context['source_revision'], row['Title'], links=links,
               links_state='resolved_reference_only' if links else 'unresolved_reference' if keys else 'not_provided')
    packet = {'contract': CONTRACT, 'provider': 'careops-rims', **context,
              'references': sorted(rows, key=lambda r: (r['source'], r['id']))}
    # Correlation belongs to the attempt; unchanged content remains idempotent.
    packet['idempotency_key'] = digest({k: v for k, v in packet.items() if k != 'correlation_id'})
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    packet = prepare(data['snapshot'], data['context'], {tuple(k) for k in data['allowed_keys']})
    with args.output.open('x') as stream:
        json.dump(packet, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(f'PREPARED_LOCAL_ONLY: {len(packet["references"])} optional references; no tenant effects')


if __name__ == '__main__':
    main()
