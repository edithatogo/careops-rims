import base64
from argparse import Namespace
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.rims_operator import (bundle_plan, compare_flows, compare_receipts, failed_actions,
    list_export, main, monitor, recovery, render_text, retrieve, retrieve_bundle, retrieval_plan,
    run_summary, summarize_receipts)


class OperatorToolsTests(unittest.TestCase):
    def test_text_summary_and_recovery_keep_outcome_and_unknowns_visible(self):
        summary = render_text(run_summary({'status': 'Failed', 'run_id': 'r1', 'records': 4}))
        self.assertIn('Outcome: Failed', summary)
        self.assertIn('$.records = 4', summary)
        self.assertIn('Output: not recorded', summary)
        self.assertIn('No known cause matched', render_text(recovery({})))

    def test_manifest_listing_keeps_revision_and_metadata_and_printable_parts(self):
        manifest = {'run': 'run-1', 'files': [{'name': 'one.csv', 'native_version': '1.0'}],
                    'part_name_pattern': 'run-1-part-{zero-based-index}.html', 'part_count': 2}
        before = copy.deepcopy(manifest)
        result = list_export(manifest)
        self.assertEqual(result['run_identity'], {'run': 'run-1'})
        self.assertEqual(result['file_count'], 3)
        self.assertEqual(result['files'][0]['native_version'], '1.0')
        self.assertNotIn('sha256', result['files'][0])
        self.assertEqual(manifest, before)
        self.assertIn('not recorded', render_text(result))
        with self.assertRaises(ValueError): list_export({'statusCode': 403, 'body': manifest})

    def test_drilldown_handles_select_and_native_action_shapes_without_following_links(self):
        document = {'run_id': 'r1', 'status': 'Failed', 'actions': [
            {'action': 'Save', 'status': 'Failed', 'code': 'PreconditionFailed'},
            {'name': 'Fetch', 'type': 'Microsoft.ProcessSimple/environments/flows/runs/actions',
             'properties': {'status': 'TimedOut', 'error': {'code': 'Timeout'},
                            'inputsLink': {'uri': 'https://never-follow.invalid/'}}},
            {'action': 'Okay', 'status': 'Succeeded'}]}
        result = failed_actions(document)
        self.assertEqual(result['failed_action_count'], 2)
        self.assertEqual([x['action'] for x in result['failed_actions']], ['Save', 'Fetch'])
        self.assertEqual(result['failed_actions'][0]['error_codes'], ['PreconditionFailed'])
        self.assertEqual(result['failed_actions'][0]['recovery']['matched_causes'][0]['cause'], 'etag_conflict')
        self.assertNotIn('never-follow', json.dumps(result))

    def test_compare_receipts_reports_changed_outcome_count_warning_and_output(self):
        before = {'run_id': 'r1', 'status': 'Failed', 'records': 2,
                  'output_path': '/old', 'error': {'code': 'BadRequest'}}
        after = {'run_id': 'r2', 'status': 'Succeeded', 'records': 3, 'output_path': '/new'}
        result = compare_receipts(before, after)
        self.assertEqual({x['section'] for x in result['changes']}, {
            'reported_outcome', 'record_counts', 'output_locations', 'unresolved_errors_and_warnings'})
        self.assertIn('r1', json.dumps(result['before_identities']))
        self.assertIn('r2', json.dumps(result['after_identities']))
        self.assertTrue(compare_receipts(before, before)['equal'])

    def test_multiple_receipts_keep_order_identity_and_unreadable_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'first.json', root / 'second.json'
            first.write_text(json.dumps({'run_id': 'r1', 'status': 'Succeeded', 'records': 5}))
            second.write_text(json.dumps({'run_id': 'r2', 'status': 'Failed', 'records': 2}))
            result = summarize_receipts([second, root / 'missing.json', first])
            self.assertEqual([x['outcome'] for x in result['receipts']], ['Failed', 'UNREADABLE', 'Succeeded'])
            self.assertEqual(result['receipt_count'], 3)
            text = render_text(result)
            self.assertIn('r1', text)
            self.assertIn('r2', text)
            self.assertIn('Run identity', text)
            with patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(main(['summary', str(first), '--format', 'text']), 0)
                self.assertIn('Outcome: Succeeded', output.getvalue())

    def bundle_args(self, directory):
        root = Path(directory)
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps({'run': 'run-1', 'files': [
            {'name': name, 'sha256': hashlib.sha256(content).hexdigest()}
            for name, content in [('one.csv', b'first'), ('two.json', b'second')]]}))
        return Namespace(manifest=manifest, revision='run-1',
            site='https://example.sharepoint.com/sites/Research', folder='/Documents/run-1',
            reference_directory=None, destination=root / 'private/ops/bundle', execute=True)

    def test_bundle_preflights_all_hashes_before_first_download(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.bundle_args(directory)
            manifest = json.loads(args.manifest.read_text())
            del manifest['files'][1]['sha256']
            args.manifest.write_text(json.dumps(manifest))
            with patch('scripts.rims_operator.subprocess.run') as run:
                with self.assertRaises(ValueError): retrieve_bundle(args)
                run.assert_not_called()
            self.assertFalse(args.destination.exists())

    def test_bundle_failure_keeps_final_directory_absent(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.bundle_args(directory)
            def download(command, **kwargs):
                content = b'first' if command[command.index('--url') + 1].endswith('one.csv') else b'changed'
                Path(command[command.index('--path') + 1]).write_bytes(content)
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download):
                with self.assertRaises(ValueError): retrieve_bundle(args)
            self.assertFalse(args.destination.exists())
            receipt = next(args.destination.parent.glob('bundle-retrieval-*/receipt.json'))
            self.assertEqual(json.loads(receipt.read_text())['status'], 'FAILED_OR_UNVERIFIED')

    def test_bundle_success_verifies_every_file_and_completion_receipt(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.bundle_args(directory)
            def download(command, **kwargs):
                content = b'first' if command[command.index('--url') + 1].endswith('one.csv') else b'second'
                Path(command[command.index('--path') + 1]).write_bytes(content)
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download) as run:
                result = retrieve_bundle(args)
                self.assertEqual(run.call_count, 2)
            self.assertEqual(result['status'], 'VERIFIED_COMPLETE_EXPORT_BUNDLE')
            self.assertEqual((args.destination / 'one.csv').read_bytes(), b'first')
            self.assertEqual((args.destination / 'two.json').read_bytes(), b'second')
            self.assertEqual(json.loads((args.destination / '.rims-bundle-receipt.json').read_text())['file_count'], 2)
            with self.assertRaises(ValueError): bundle_plan(args)

    def test_bundle_reference_bytes_and_competing_directory_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.bundle_args(directory)
            manifest = json.loads(args.manifest.read_text())
            for entry in manifest['files']: entry.pop('sha256')
            args.manifest.write_text(json.dumps(manifest))
            args.reference_directory = Path(directory) / 'accepted'
            args.reference_directory.mkdir()
            (args.reference_directory / 'one.csv').write_bytes(b'first')
            (args.reference_directory / 'two.json').write_bytes(b'second')
            self.assertEqual(bundle_plan(args)['file_count'], 2)
            def download(command, **kwargs):
                content = b'first' if command[command.index('--url') + 1].endswith('one.csv') else b'second'
                Path(command[command.index('--path') + 1]).write_bytes(content)
                args.destination.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download):
                with self.assertRaises(FileExistsError): retrieve_bundle(args)
            self.assertEqual(list(args.destination.iterdir()), [])

    def test_completed_refresh_warning_is_visible(self):
        result = run_summary({'status_code': 200, 'text': {'status': 'Completed',
            'messages': [{'type': 'Warning', 'message': "The syntax for 'Typed' is incorrect."}]}})
        self.assertEqual(len(result['unresolved_errors_and_warnings']), 1)
        self.assertEqual(recovery(result)['matched_causes'][0]['cause'], 'dax_warning')

    def test_receipt_fields_are_reported_without_invented_counts(self):
        result = run_summary({'status': 'failed-or-timed-out', 'run_id': 'run-1',
            'actions': [{'name': 'Save', 'status': 'Failed', 'error': {'code': '412'}}]})
        self.assertEqual(result['record_counts'], [])
        self.assertTrue(result['unresolved_errors_and_warnings'])
        self.assertEqual(recovery(result)['matched_causes'][0]['cause'], 'etag_conflict')

    def test_connector_json_body(self):
        raw = json.dumps({'records': 12, 'manifest_file': '/Documents/run-1.json'}).encode()
        result = run_summary({'statusCode': 200, 'body': {'$content-type': 'application/json',
            '$content': base64.b64encode(raw).decode()}})
        self.assertEqual(result['record_counts'][0]['value'], 12)
        self.assertEqual(result['output_locations'][0]['value'], '/Documents/run-1.json')

    def test_numeric_noise_is_not_etag_failure_and_http_is_not_run_success(self):
        self.assertEqual(recovery({'rows': 412, 'hash': 'a412b'})['matched_causes'], [])
        self.assertEqual(run_summary({'status_code': 200})['reported_outcome'], 'UNKNOWN')

    def test_monthly_observation_is_explicit_and_incomplete_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            evidence = {'runtime_flow_id': 'flow-1', 'history_complete': True,
                        'reads_verified': True, 'runs': []}
            path.write_text(json.dumps(evidence))
            args = Namespace(month='2026-11', evidence=path, history=None,
                as_of='2026-11-01T12:01:00+10:00',
                observation_start='2026-11-01T08:00:00+10:00',
                observation_end='2026-11-01T12:01:00+10:00')
            self.assertEqual(monitor(args)['decision']['status'], 'MISSED')
            evidence['history_complete'] = False
            path.write_text(json.dumps(evidence))
            self.assertEqual(monitor(args)['decision']['status'], 'UNKNOWN')
            args.as_of = '2026-11-01T12:01:00'
            with self.assertRaises(ValueError): monitor(args)

    def test_native_history_cannot_infer_successful_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            path.write_text(json.dumps([{'name': 'run-1',
                'id': '/providers/Microsoft.ProcessSimple/environments/env/flows/dv/runs/run-1',
                'properties': {'status': 'Succeeded', 'startTime': '2026-11-01T09:00:00+10:00',
                    'endTime': '2026-11-01T09:01:00+10:00',
                    'trigger': {'name': 'Recurrence', 'scheduledTime': '2026-11-01T09:00:00+10:00'}}}]))
            args = Namespace(month='2026-11', evidence=None, history=path,
                as_of='2026-11-01T12:01:00+10:00', observation_start='2026-11-01T08:00:00+10:00',
                observation_end='2026-11-01T12:01:00+10:00', environment_id='env',
                dataverse_flow_id='dv', runtime_flow_id='runtime', history_complete=True, reads_verified=True)
            self.assertEqual(monitor(args)['decision']['status'], 'UNKNOWN')

    def test_compare_identifies_graph_binding_state_and_preserves_inputs(self):
        before = {'properties': {'state': 'Stopped', 'connectionReferences': {'sp': {'id': 'old'}},
            'definition': {'triggers': {'manual': {'type': 'Request'}},
                'actions': {'Save': {'type': 'Compose', 'inputs': 'one'}}}}}
        after = copy.deepcopy(before)
        after['properties']['state'] = 'Started'
        after['properties']['connectionReferences']['sp']['id'] = 'new'
        after['properties']['definition']['actions']['Save']['inputs'] = 'two'
        preserved = copy.deepcopy((before, after))
        result = compare_flows(before, after)
        self.assertEqual({c['path'] for c in result['changes']}, {
            '/state/state', '/connections/connectionReferences/sp/id', '/definition/actions/Save/inputs'})
        self.assertEqual((before, after), preserved)
        self.assertTrue(compare_flows(before, before)['equal'])
        with self.assertRaises(ValueError): compare_flows({}, {})

    def test_changed_secrets_are_detected_without_printing_values(self):
        before = {'definition': {'parameters': {'key': {'type': 'SecureString', 'defaultValue': 'secret-one'}}}}
        after = copy.deepcopy(before)
        after['definition']['parameters']['key']['defaultValue'] = 'secret-two'
        result = compare_flows(before, after)
        self.assertFalse(result['equal'])
        self.assertNotIn('secret-one', json.dumps(result))
        self.assertNotIn('secret-two', json.dumps(result))

    def retrieval_args(self, directory):
        root = Path(directory)
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps({'run': 'run-1', 'files': [{'name': 'export.csv',
            'sha256': hashlib.sha256(b'accepted').hexdigest()}]}))
        return Namespace(manifest=manifest, revision='run-1', file='export.csv',
            site='https://example.sharepoint.com/sites/Research', folder='/Documents/exports/run-1',
            sha256=None, reference=None, destination=root / 'private/ops/retrieved.csv', execute=True)

    def test_retrieval_checks_revision_before_invoking_cli(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.retrieval_args(directory)
            args.revision = 'different-run'
            with patch('scripts.rims_operator.subprocess.run') as run:
                with self.assertRaises(ValueError): retrieve(args)
                run.assert_not_called()

    def test_download_hash_mismatch_never_publishes_output(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.retrieval_args(directory)
            def download(command, **kwargs):
                Path(command[command.index('--path') + 1]).write_bytes(b'changed')
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download):
                with self.assertRaises(ValueError): retrieve(args)
            self.assertFalse(args.destination.exists())
            receipt = next(args.destination.parent.glob('retrieval-*/receipt.json'))
            self.assertEqual(json.loads(receipt.read_text())['status'], 'FAILED_OR_UNVERIFIED')

    def test_nonzero_download_gate_is_not_accepted_even_with_matching_bytes(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.retrieval_args(directory)
            def download(command, **kwargs):
                Path(command[command.index('--path') + 1]).write_bytes(b'accepted')
                return subprocess.CompletedProcess(command, 1, '', 'Denied')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download):
                with self.assertRaises(ValueError): retrieve(args)
            self.assertFalse(args.destination.exists())

    def test_retrieval_defaults_to_plan_without_contacting_cli(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.retrieval_args(directory)
            args.execute = False
            with patch('scripts.rims_operator.subprocess.run') as run:
                result = retrieve(args)
                run.assert_not_called()
            self.assertFalse(result['execute'])
            self.assertFalse(args.destination.parent.exists())

    def test_exact_download_and_existing_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.rims_operator.ROOT', Path(directory).resolve()):
            args = self.retrieval_args(directory)
            def download(command, **kwargs):
                Path(command[command.index('--path') + 1]).write_bytes(b'accepted')
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch('scripts.rims_operator.subprocess.run', side_effect=download):
                self.assertEqual(retrieve(args)['status'], 'VERIFIED_EXACT_EXPORT_REVISION')
            self.assertEqual(args.destination.read_bytes(), b'accepted')
            with self.assertRaises(ValueError): retrieval_plan(args)


if __name__ == '__main__':
    unittest.main()
