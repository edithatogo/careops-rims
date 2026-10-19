"""Run the fictional, offline optional-reference compatibility demonstration."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from module_reference_adapter import prepare
from consumer import receive, view, digest


def demonstrate(data):
    allowed = {tuple(k) for k in data['allowed_keys']}
    initial = {'case': {'CaseKey': 'fictional-case-1', 'Title': 'Fictional standalone case', 'Status': 'Draft'}}
    absent = view(initial, allowed)
    packet = prepare(data['snapshot'], data['context'], allowed)
    saved = receive(initial, packet)
    replay = receive(saved, packet)
    assert replay == saved
    unavailable = view(receive(saved, None), allowed)
    assert unavailable['references'] == view(saved, allowed)['references']
    assert view(saved, set())['references'] == []
    conflict = copy.deepcopy(packet)
    conflict['references'][-1]['label'] += ' conflicting edit'
    conflict['idempotency_key'] = digest({k: v for k, v in conflict.items() if k not in {'correlation_id', 'idempotency_key'}})
    try:
        receive(saved, conflict)
    except ValueError:
        pass
    else:
        raise AssertionError('Same-revision conflicting content was admitted')
    assert all(v['case'] == initial['case'] for v in [absent, view(saved, allowed), unavailable, view(saved, set())])
    return {'status': 'PASS_FICTIONAL_OFFLINE_COMPATIBILITY',
            'scope': 'Fictional local adapter compatibility only; no tenant integration or caller authentication claimed',
            'checks': {'standalone_without_adapter': True, 'source_qualified_references': len(packet['references']),
                       'unchanged_replay': True, 'same_revision_conflict_refused': True,
                       'unavailable_retains_references_with_stale_notice': True,
                       'current_denied_scope_hides_cached_references': True, 'consumer_case_preserved': True},
            'packet': packet, 'standalone': absent, 'connected': view(saved, allowed),
            'unavailable': unavailable, 'denied': view(saved, set())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.loads((Path(__file__).parent / 'input.json').read_text())
    result = demonstrate(data)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(result['status'])
