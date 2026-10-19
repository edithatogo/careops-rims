"""Fictional standalone consumer. Standard library only; no RIMS import/network.

This local compatibility demonstration does not authenticate a real caller.
Live adapters require the consumer's established authentication and permissions.
"""
from __future__ import annotations
import copy
import hashlib
import json
from urllib.parse import urlsplit


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def receive(state, packet):
    """Atomic local receipt; conflicting content at the same revision is refused."""
    result = copy.deepcopy(state)
    if packet is None:
        result['availability'] = 'unavailable; retained references may be stale'
        return result
    expected = {'contract', 'provider', 'provider_version', 'consumer', 'consumer_version',
                'correlation_id', 'purpose', 'classification', 'captured_at', 'source_revision',
                'evidence_url', 'references', 'idempotency_key'}
    if set(packet) != expected or packet.get('provider_version') != '1':
        raise ValueError('Unsupported packet fields/provider version')
    if not isinstance(packet['references'], list) or len(packet['references']) > 50:
        raise ValueError('Expected bounded reference list')
    if (packet.get('contract') != 'careops-rims.references/1'
            or packet.get('provider') != 'careops-rims'
            or packet.get('consumer') != 'fictional-case-workbench'
            or packet.get('consumer_version') != '1'
            or packet.get('purpose') != 'evidence-navigation'
            or packet.get('classification') != 'public'):
        raise ValueError('Unsupported contract, consumer, purpose or classification')
    actual = digest({k: v for k, v in packet.items() if k not in {'correlation_id', 'idempotency_key'}})
    if actual != packet.get('idempotency_key'):
        raise ValueError('Packet integrity mismatch; hash is not authentication')
    cache = result.setdefault('references', {})
    pending, seen = {}, set()
    def safe_url(value):
        if not isinstance(value, str):
            raise ValueError('Expected evidence URL')
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Unsafe evidence URL')
    safe_url(packet['evidence_url'])
    for ref in packet['references']:
        if set(ref) != {'source', 'kind', 'id', 'revision', 'label', 'evidence_url', 'links', 'links_state'}:
            raise ValueError('Unexpected reference fields')
        if any(not isinstance(ref[k], str) or not ref[k] or ref[k] != ref[k].strip() for k in ['id', 'revision', 'label']):
            raise ValueError('Invalid canonical text')
        safe_url(ref['evidence_url'])
        if ref['links_state'] not in {'not_provided', 'unresolved_reference', 'resolved_reference_only'} or not isinstance(ref['links'], list):
            raise ValueError('Invalid reference resolution state')
        for link in ref['links']:
            if (set(link) != {'source', 'id', 'revision', 'status', 'confidence'}
                    or link['source'] != 'careops-rims/organisations'
                    or any(not isinstance(link[k], str) or not link[k] or link[k] != link[k].strip() for k in ['id', 'revision'])
                    or link['status'] not in {'explicit-affiliation-alias', 'unmatched', 'review-required'}
                    or link['confidence'] not in {'high', 'medium', 'low', 'unknown'}):
                raise ValueError('Invalid organisation reference')
        if ref.get('source') != {'publication': 'careops-rims/publications', 'organisation': 'careops-rims/organisations'}.get(ref.get('kind')):
            raise ValueError('Unknown source-qualified kind')
        key = json.dumps([ref['source'], ref['id']])
        if key in seen:
            raise ValueError('Duplicate reference')
        seen.add(key)
        old = cache.get(key)
        if old and old['revision'] != ref['revision']:
            raise ValueError('Changed revision requires explicit source reconciliation')
        if old and old != ref:
            raise ValueError('Conflicting content at the same revision')
        pending[key] = copy.deepcopy(ref)
    cache.update(pending)
    result['availability'] = 'available'
    result['receipt'] = packet['idempotency_key']
    result['context'] = {k: packet[k] for k in ['provider', 'provider_version', 'captured_at', 'source_revision', 'purpose', 'classification', 'evidence_url']}
    return result


def view(state, allowed_keys):
    """Current caller scope is applied again at display, including cached rows."""
    visible = [copy.deepcopy(r) for r in state.get('references', {}).values()
               if (r['source'], r['id']) in allowed_keys]
    for ref in visible:
        ref['links'] = [link for link in ref['links'] if (link['source'], link['id']) in allowed_keys]
    status = state.get('availability', 'optional adapter absent')
    if state.get('references') and not visible:
        status = 'reference access restricted; standalone case remains available'
    return {'case': copy.deepcopy(state['case']),
            'integration_status': status,
            'source_context': copy.deepcopy(state.get('context')) if visible else None,
            'references': sorted(visible, key=lambda r: (r['source'], r['id']))}
