import copy
import unittest
import json
from datetime import datetime, timedelta, timezone

from scripts.prepare_register_export_monitoring import build, prepare_failure_probe, evaluate_occurrence, normalise_empty_join_delimiters, normalise_native_history, prepare_occurrence_packet
from scripts.prepare_register_export_monitoring import monthly_occurrence_policy


class MonthlyPolicyTests(unittest.TestCase):
    def test_user_selected_policy_is_explicit_month_and_brisbane_time(self):
        p = monthly_occurrence_policy('2026-11')
        self.assertEqual(p['expected_at'].isoformat(), '2026-11-01T09:00:00+10:00')
        self.assertEqual(p['deadline'].isoformat(), '2026-11-01T12:00:00+10:00')
        self.assertNotIn('as_of', p)

    def test_missing_or_ambiguous_month_is_rejected(self):
        for value in (None, '', 'November', '2026-1', '2026-13', ' 2026-11'):
            with self.subTest(month=value), self.assertRaises(ValueError):
                monthly_occurrence_policy(value)


class NativeHistoryTests(unittest.TestCase):
    def record(self):
        return {'name':'run', 'id':'/providers/Microsoft.ProcessSimple/environments/env/flows/dv/runs/run',
                'properties':{'startTime':'2026-11-01T09:00:00+10:00',
                    'endTime':'2026-11-01T09:02:00+10:00','status':'Succeeded',
                    'correlation':{'clientKeywords':['testFlow']},
                    'trigger':{'name':'Recurrence','scheduledTime':'2026-11-01T09:00:00+10:00'}}}

    def adapt(self, records):
        return normalise_native_history(records,environment_id='env',dataverse_flow_id='dv',runtime_flow_id='runtime')

    def test_manual_recurrence_is_not_scheduled_or_output_verified(self):
        r = self.adapt([self.record()])
        self.assertTrue(r['history_shape_verified'])
        self.assertEqual(r['runs'][0]['trigger_kind'], 'Manual')
        self.assertFalse(r['runs'][0]['output_readback_verified'])

    def test_other_flow_or_malformed_trigger_fails_closed(self):
        r = self.record(); r['id'] = r['id'].replace('/dv/', '/other/')
        self.assertFalse(self.adapt([r])['history_shape_verified'])
        r = self.record(); r['properties']['trigger'] = []
        self.assertFalse(self.adapt([r])['history_shape_verified'])

    def test_missing_keyword_is_not_content_or_pagination_proof(self):
        r = self.record(); r['properties']['correlation'] = {}
        adapted = self.adapt([r])
        self.assertEqual(adapted['runs'][0]['trigger_kind'], 'Recurrence')
        self.assertFalse(adapted['runs'][0]['output_readback_verified'])
        self.assertNotIn('history_complete', adapted)


class OccurrenceTests(unittest.TestCase):
    def args(self):
        due = datetime(2026, 11, 1, 9, tzinfo=timezone(timedelta(hours=10)))
        return dict(expected_at=due, deadline=due+timedelta(hours=1),
                    as_of=due+timedelta(hours=2), observation_start=due,
                    observation_end=due+timedelta(hours=2), history_complete=True,
                    reads_verified=True, runtime_flow_id='runtime', runs=[])

    def test_absence_requires_complete_read_and_explicit_deadline(self):
        a = self.args()
        self.assertEqual(evaluate_occurrence(**a)['status'], 'MISSED')
        a['history_complete'] = False
        self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')
        a = self.args(); a['as_of'] = a['expected_at']; a['observation_end'] = a['as_of']
        self.assertEqual(evaluate_occurrence(**a)['status'], 'PENDING')

    def test_manual_success_does_not_clear_expected_occurrence(self):
        a = self.args(); a['runs'] = [{'trigger_kind':'Manual','status':'Succeeded',
                                     'flow_id':'runtime','run_id':'manual-run'}]
        self.assertEqual(evaluate_occurrence(**a)['status'], 'MISSED')

    def test_success_needs_correct_period_and_correlated_content(self):
        a = self.args(); due = a['expected_at']
        run = dict(trigger_kind='Recurrence', flow_id='runtime', run_id='run',
                   scheduled_for=due, started_at=due, completed_at=due+timedelta(minutes=2),
                   status='Succeeded', health_run_id='run', output_readback_verified=True)
        a['runs'] = [run]
        self.assertEqual(evaluate_occurrence(**a)['status'], 'SUCCEEDED')
        run['output_readback_verified'] = False
        self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')
        run['output_readback_verified'] = True; run['scheduled_for'] = due-timedelta(days=31)
        self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')

    def test_future_or_duplicate_evidence_stays_unknown(self):
        a = self.args(); due = a['expected_at']
        run = dict(trigger_kind='Recurrence', flow_id='runtime', run_id='run',
                   scheduled_for=due, started_at=a['as_of']+timedelta(seconds=1),
                   status='Running')
        a['runs'] = [run]
        self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')
        run.update(started_at=due, completed_at=due+timedelta(minutes=2), status='Failed')
        self.assertEqual(evaluate_occurrence(**a)['status'], 'FAILED')
        a['runs'] = [run,dict(run)]
        self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')

    def test_observation_flags_require_exact_true(self):
        for field in ('history_complete', 'reads_verified'):
            for value in ('false', 'true', 0, 1, None, [], {}):
                with self.subTest(field=field, value=value):
                    a = self.args(); a[field] = value
                    self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')

    def test_output_flag_and_identifiers_are_typed_evidence(self):
        a = self.args(); due = a['expected_at']
        valid = dict(trigger_kind='Recurrence', flow_id='runtime', run_id='run',
                     scheduled_for=due, started_at=due, completed_at=due,
                     status='Succeeded', health_run_id='run', output_readback_verified=True)
        for value in ('false', 'true', 0, 1, None, [], {}):
            with self.subTest(flag=value):
                a['runs'] = [{**valid, 'output_readback_verified': value}]
                self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')
        for field in ('flow_id', 'run_id', 'health_run_id'):
            for value in ('', ' ', ' run ', None, 1, [], {}):
                with self.subTest(field=field, value=value):
                    a['runs'] = [{**valid, field: value}]
                    self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')
        a['runs'] = [valid]
        for value in ('', ' ', ' runtime ', None, 1, [], {}):
            a['runtime_flow_id'] = value
            self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')

    def test_malformed_history_never_throws_or_proves_absence(self):
        for value in (None, {}, 'history', (), [None], [1], [[]], ['record'], [{}]):
            with self.subTest(history=value):
                a = self.args(); a['runs'] = value
                self.assertEqual(evaluate_occurrence(**a)['status'], 'UNKNOWN')

    def test_packet_replay_is_stable_and_does_not_leak_native_payload(self):
        args = self.args(); args.pop('runs')
        packet = prepare_occurrence_packet(native_history=[], environment_id='env',
            dataverse_flow_id='dv', **args)
        self.assertEqual(packet['decision']['status'], 'MISSED')
        replay = prepare_occurrence_packet(native_history=[], environment_id='env',
            dataverse_flow_id='dv', **args)
        self.assertEqual(packet, replay)
        changed = dict(args, as_of=args['as_of']+timedelta(seconds=1),
                       observation_end=args['observation_end']+timedelta(seconds=1))
        revision = prepare_occurrence_packet(native_history=[], environment_id='env',
            dataverse_flow_id='dv', **changed)
        self.assertNotEqual(packet['observation_sha256'], revision['observation_sha256'])
        self.assertFalse(packet['decision']['automatic_detection_proved'])
        self.assertNotIn('outputsLink', json.dumps(packet))

    def test_packet_missing_policy_and_bad_history_remain_unknown(self):
        args = self.args(); args.pop('runs'); args['deadline'] = None
        p = prepare_occurrence_packet(native_history={}, environment_id='env',
            dataverse_flow_id='dv', **args)
        self.assertEqual(p['decision']['status'], 'UNKNOWN')
        self.assertIsNone(p['deadline'])
        self.assertFalse(p['history_complete'])


class MonitoringTests(unittest.TestCase):
    def baseline(self):
        return {'properties': {'definition': {
            'triggers': {'Recurrence': {'type': 'Recurrence'}},
            'actions': {
                'Save_Registered_Publications_CSV': {
                    'type': 'OpenApiConnection', 'runAfter': {},
                    'inputs': {'authentication': 'preserve-auth', 'host': {
                        'operationId': 'CreateFile', 'connectionName': 'existing'},
                        'parameters': {'dataset': 'existing-site',
                            'folderPath': '/Documents/CHHHS Research System - DEV/03 Reporting',
                            'name': 'existing-name', 'body': 'existing-content'}}},
                'Printable_Verify_manifest': {'type': 'Compose', 'inputs': 'verified',
                    'runAfter': {'Save_Registered_Publications_CSV': ['Succeeded']}},
                'Printable_Save_completion_manifest': {'type': 'Compose', 'inputs': 'saved',
                    'runAfter': {'Save_Registered_Publications_CSV': ['Succeeded']}},
            }}, 'connectionReferences': {'existing': {'unchanged': True}}}}

    def test_preserves_graph_bindings_and_input(self):
        before = self.baseline(); saved = copy.deepcopy(before); after = build(before)
        self.assertEqual(before, saved)
        self.assertEqual(after['properties']['definition']['actions']['Export_Run']['actions'],
                         before['properties']['definition']['actions'])
        self.assertEqual(after['properties']['connectionReferences'], before['properties']['connectionReferences'])
        self.assertEqual(after['properties']['definition']['triggers'], before['properties']['definition']['triggers'])
        save = after['properties']['definition']['actions']['Monitor_Save_failure']['inputs']
        self.assertEqual(save['authentication'], 'preserve-auth')
        self.assertEqual(save['parameters']['dataset'], 'existing-site')

    def test_failure_only_and_logging_failure_cannot_hide_export_failure(self):
        actions = build(self.baseline())['properties']['definition']['actions']
        self.assertEqual(actions['Monitor_Action_statuses']['runAfter']['Export_Run'], ['Failed', 'TimedOut'])
        self.assertEqual(set(actions['Monitor_Action_statuses']['inputs']['select']), {'action', 'status', 'code'})
        end = actions['Monitor_Retain_failed_status']
        self.assertEqual(end['inputs']['runStatus'], 'Failed')
        self.assertEqual(set(end['runAfter']['Monitor_Save_failure']), {'Succeeded', 'Failed', 'Skipped', 'TimedOut'})
        self.assertEqual(end['runAfter']['Export_Run'], ['Failed', 'TimedOut'])

    def test_health_waits_for_complete_export_and_does_not_claim_scheduled_trigger(self):
        actions = build(self.baseline())['properties']['definition']['actions']
        receipt = actions['Monitor_Success_receipt']
        self.assertEqual(receipt['runAfter'], {'Export_Run': ['Succeeded']})
        self.assertFalse(receipt['inputs']['scheduled_trigger_proved'])
        self.assertEqual(actions['Monitor_Save_success']['runAfter'],
                         {'Monitor_Success_receipt': ['Succeeded']})

    def test_rejects_duplicate_monitor_and_unsupported_existing_termination(self):
        with self.assertRaises(ValueError): build(build(self.baseline()))
        before = self.baseline()
        before['properties']['definition']['actions']['Stop'] = {'type': 'Terminate'}
        with self.assertRaises(ValueError): build(before)

    def test_failure_probe_blocks_export_roots_and_preserves_real_handler(self):
        normal = build(self.baseline()); saved = copy.deepcopy(normal)
        probe = prepare_failure_probe(normal)
        self.assertEqual(normal, saved)
        old = normal['properties']['definition']['actions']
        new = probe['properties']['definition']['actions']
        for name in old.keys() - {'Export_Run'}:
            self.assertEqual(old[name], new[name])
        inner = new['Export_Run']['actions']
        self.assertEqual(inner['Save_Registered_Publications_CSV']['runAfter'],
                         {'Monitor_Controlled_failure': ['Succeeded']})
        self.assertEqual(inner['Monitor_Controlled_failure']['type'], 'Compose')
        self.assertNotIn('OpenApiConnection', str(inner['Monitor_Controlled_failure']))
        with self.assertRaises(ValueError): prepare_failure_probe(probe)


    def test_empty_join_expression_preserves_other_inputs_and_source(self):
        before = self.baseline()
        joins = {'Empty': {'type': 'Join', 'inputs': {'from': ['a', 'b'], 'joinWith': ''}},
                 'Newline': {'type': 'Join', 'inputs': {'from': ['a', 'b'], 'joinWith': '\n'}}}
        before['properties']['definition']['actions']['Nested'] = {'type': 'Scope', 'actions': joins}
        saved = copy.deepcopy(before)
        after = normalise_empty_join_delimiters(before)
        self.assertEqual(before, saved)
        actual = after['properties']['definition']['actions']['Nested']['actions']
        self.assertEqual(actual['Empty']['inputs'], {'from': ['a', 'b'], 'joinWith': "@string('')"})
        self.assertEqual(actual['Newline'], joins['Newline'])
        self.assertEqual(normalise_empty_join_delimiters(after), after)


if __name__ == '__main__': unittest.main()
