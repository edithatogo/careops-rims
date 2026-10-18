"""Exact-definition recovery packets refuse drift and preserve source strings."""
import copy
import json
import unittest

from scripts.prepare_archive_definition_recovery import prepare, PROBE, TIMESTAMP_PATHS

WORKFLOW = '00000000-0000-4000-8000-7ac1b8d7010b'


def receipt():
    definition = {'actions': {}}
    for path in TIMESTAMP_PATHS:
        parts = path.strip('/').split('/')
        node = definition
        for i, part in enumerate(parts[:-1]):
            if isinstance(node, list):
                index = int(part)
                while len(node) <= index:
                    node.append({})
                node = node[index]
            else:
                node = node.setdefault(part, [] if parts[i + 1].isdigit() else {})
        node[parts[-1]] = '2026-10-14T11:59:41.2290370Z'
    data = {'properties': {'displayName': 'Synthetic archive', 'definition': definition,
                           'connectionReferences': {'existing': {'source': 'Embedded'}}}}
    return {'http': 200, 'body': {'workflowid': WORKFLOW, 'statecode': 0, 'statuscode': 1,
                                 '@odata.context': 'https://example.crm.dynamics.com/api/data/v9.2/$metadata#workflows/$entity',
                                 '@odata.etag': 'W/"1"', 'clientdata': json.dumps(data)}}


class ArchiveDefinitionRecoveryTests(unittest.TestCase):
    def test_canary_and_restore_change_only_probe_and_keep_all_timestamp_bytes(self):
        good = receipt()
        canary = prepare(good, WORKFLOW)
        after = copy.deepcopy(good)
        after['body']['clientdata'] = canary['patch_fields']['clientdata']
        after['body']['@odata.etag'] = 'W/"2"'
        restored = prepare(after, WORKFLOW, last_good=good)
        self.assertEqual(restored['expected_etag'], 'W/"2"')
        self.assertEqual(json.loads(restored['patch_fields']['clientdata']), json.loads(good['body']['clientdata']))
        self.assertEqual(restored['desired_definition_sha256'], canary['baseline_definition_sha256'])
        self.assertEqual(len(restored['exact_timestamp_strings']), 6)
        self.assertTrue(all(v.endswith('.2290370Z') for v in restored['exact_timestamp_strings'].values()))
        self.assertFalse(restored['state_activation_or_run_requested'])
        self.assertEqual(set(restored['patch_fields']), {'clientdata'})
        self.assertEqual(restored['target_url'], 'https://example.crm.dynamics.com/api/data/v9.2/workflows(' + WORKFLOW + ')')

    def test_same_workflow_id_in_different_environment_is_not_a_restore_target(self):
        good = receipt()
        after = copy.deepcopy(good)
        after['body']['clientdata'] = prepare(good, WORKFLOW)['patch_fields']['clientdata']
        after['body']['@odata.context'] = 'https://other.crm.dynamics.com/api/data/v9.2/$metadata#workflows/$entity'
        with self.assertRaises(ValueError):
            prepare(after, WORKFLOW, last_good=good)

    def test_unknown_identity_active_state_failed_read_and_missing_etag_rejected(self):
        for field, value in [('workflowid', '00000000-0000-4000-8000-90d5b0a26955'),
                             ('statecode', 1), ('statecode', False), ('statuscode', 2),
                             ('@odata.etag', None)]:
            with self.subTest(field=field, value=value):
                current = receipt()
                current['body'][field] = value
                with self.assertRaises(ValueError):
                    prepare(current, WORKFLOW)
        current = receipt()
        current['http'] = 403
        with self.assertRaises(ValueError):
            prepare(current, WORKFLOW)

    def test_repeated_canary_and_unrelated_edits_or_binding_drift_are_not_overwritten(self):
        good = receipt()
        after = copy.deepcopy(good)
        after['body']['clientdata'] = prepare(good, WORKFLOW)['patch_fields']['clientdata']
        with self.assertRaises(ValueError):
            prepare(after, WORKFLOW)
        for boundary in ('definition', 'binding', 'probe', 'timestamp'):
            altered = copy.deepcopy(after)
            data = json.loads(altered['body']['clientdata'])
            if boundary == 'definition':
                data['properties']['definition']['actions']['Other_change'] = {'type': 'Compose', 'inputs': 'later edit'}
            elif boundary == 'binding':
                data['properties']['connectionReferences']['existing']['source'] = 'Invoker'
            elif boundary == 'probe':
                data['properties']['definition']['actions'][PROBE]['inputs'] = 'changed'
            else:
                data['properties']['definition']['actions']['Expected_manifest']['inputs']['ObservedAtUTC'] = '2026-10-14T11:59:41.229037Z'
            altered['body']['clientdata'] = json.dumps(data)
            with self.assertRaises(ValueError):
                prepare(altered, WORKFLOW, last_good=good)

    def test_other_workflow_purpose_cannot_be_used_for_archive_recovery(self):
        current = receipt()
        data = json.loads(current['body']['clientdata'])
        del data['properties']['definition']['actions']['Expected_manifest']
        current['body']['clientdata'] = json.dumps(data)
        with self.assertRaises(ValueError):
            prepare(current, WORKFLOW)
