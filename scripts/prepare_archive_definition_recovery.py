"""Prepare a bounded Stopped archive-definition canary/restore; no service calls.

The owner must qualify the exact target and use the recorded If-Match condition.
This is an in-place native-clientdata route, never modification of a solution ZIP.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from urllib.parse import urlsplit

PROBE = 'RIMS_DefinitionRestore_Probe'
PROBE_ACTION = {'type': 'Compose', 'inputs': 'Stopped definition recovery qualification only',
                'runAfter': {}}
TIMESTAMP_PATHS = (
    '/actions/Condition_OpenAlex_archive/actions/OpenAlex_Expected_manifest/inputs/AttemptStatuses/16/ObservedUTC',
    '/actions/Condition_OpenAlex_native_capture/actions/NativeCapture_Acq_expected_manifest/inputs/AttemptStatuses/0/ObservedUTC',
    '/actions/Expected_manifest/inputs/ObservedAtUTC',
    '/actions/Expected_manifest/inputs/RefreshCompletedAtUTC',
    '/actions/Expected_manifest/inputs/Provenance/RefreshCompletedAtUTC',
    '/actions/Expected_manifest/inputs/RefreshStartedAtUTC',
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def _lexemes(definition):
    result = {}
    for path in TIMESTAMP_PATHS:
        node = definition
        try:
            for part in path.strip('/').split('/'):
                node = node[int(part)] if isinstance(node, list) else node[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError('Expected existing source-archive timestamp contract missing') from exc
        if not isinstance(node, str) or not node:
            raise ValueError('Archive timestamps must remain exact nonempty strings')
        result[path] = node
    return result


def _snapshot(receipt, workflow_id):
    if (not isinstance(receipt, dict) or type(receipt.get('http')) is not int
            or receipt['http'] != 200):
        raise ValueError('Successful recorded native read required')
    row = receipt.get('body')
    if (not isinstance(row, dict) or not isinstance(row.get('workflowid'), str)
            or row['workflowid'].lower() != workflow_id
            or type(row.get('statecode')) is not int or row['statecode'] != 0
            or type(row.get('statuscode')) is not int or row['statuscode'] != 1):
        raise ValueError('Exact existing workflow must be Stopped')
    etag = row.get('@odata.etag')
    if not isinstance(etag, str) or not re.fullmatch(r'W/"[0-9]+"', etag):
        raise ValueError('Recorded native row ETag required')
    context = row.get('@odata.context')
    if not isinstance(context, str):
        raise ValueError('Native entity context required to bind the environment')
    url = urlsplit(context)
    if (url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.dynamics.com')
            or url.username or url.password or url.query
            or not re.fullmatch(r'/api/data/v9\.2/\$metadata', url.path)
            or not re.fullmatch(r'workflows(?:\([^#]*\))?/\$entity', url.fragment)):
        raise ValueError('Qualified Dataverse workflow entity context required')
    api_base = 'https://' + url.netloc + '/api/data/v9.2'
    data = json.loads(row['clientdata'])
    properties = data.get('properties') if isinstance(data, dict) else None
    if (not isinstance(properties, dict) or not isinstance(properties.get('definition'), dict)
            or not isinstance(properties.get('connectionReferences'), dict)):
        raise ValueError('Complete native definition and binding preimage required')
    _lexemes(properties['definition'])
    return data, etag, api_base


def prepare(current, workflow_id, *, last_good=None):
    """Allow one inert probe, or remove that exact probe to recover last-good A."""
    if not isinstance(workflow_id, str) or str(uuid.UUID(workflow_id)) != workflow_id:
        raise ValueError('Canonical workflow UUID required')
    data, etag, api_base = _snapshot(current, workflow_id)
    original = data['properties']['definition']
    desired = copy.deepcopy(data)
    definition = desired['properties']['definition']
    actions = definition.get('actions')
    if not isinstance(actions, dict):
        raise ValueError('Archive root actions required')
    if last_good is None:
        if PROBE in actions:
            raise ValueError('Probe already present; reconcile instead of repeating')
        actions[PROBE] = copy.deepcopy(PROBE_ACTION)
        mode = 'prepare_stopped_canary'
    else:
        good, _, good_base = _snapshot(last_good, workflow_id)
        if good_base != api_base:
            raise ValueError('Environment drift; do not restore a different environment')
        good_properties = good['properties']
        if data['properties']['connectionReferences'] != good_properties['connectionReferences']:
            raise ValueError('Binding drift; do not overwrite')
        if actions.get(PROBE) != PROBE_ACTION:
            raise ValueError('Exact qualification probe missing or altered')
        del actions[PROBE]
        if definition != good_properties['definition']:
            raise ValueError('Unrelated definition drift; do not overwrite')
        mode = 'restore_exact_last_good_definition'
    assert _lexemes(original) == _lexemes(definition)
    assert desired['properties']['connectionReferences'] == data['properties']['connectionReferences']
    return {'kind': 'bounded_stopped_archive_definition_recovery_v1', 'mode': mode,
            'workflow_id': workflow_id, 'expected_etag': etag,
            'target_url': api_base + '/workflows(' + workflow_id + ')',
            'expected_statecode': 0, 'expected_statuscode': 1,
            'baseline_definition_sha256': _digest(original),
            'desired_definition_sha256': _digest(definition),
            'exact_timestamp_strings': _lexemes(definition),
            'patch_fields': {'clientdata': json.dumps(desired, ensure_ascii=False, separators=(',', ':'))},
            'state_activation_or_run_requested': False,
            'scope': 'Recorded preparation only; owner must qualify target/current state and apply If-Match. No native restore or runtime acceptance proved.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--current', type=Path, required=True)
    p.add_argument('--last-good', type=Path)
    p.add_argument('--workflow-id', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    private = (Path(__file__).resolve().parents[1] / 'private/ops').resolve()
    paths = [args.current, args.output] + ([args.last_good] if args.last_good else [])
    if any(not path.resolve().is_relative_to(private) for path in paths):
        p.error('Native inputs and prepared output must remain in private/ops')
    result = prepare(json.loads(args.current.read_text()), args.workflow_id,
                     last_good=json.loads(args.last_good.read_text()) if args.last_good else None)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    print('Prepared bounded Stopped archive recovery packet; no service call or run submitted')


if __name__ == '__main__':
    main()
