import subprocess
import json
import tempfile
from pathlib import Path
import unittest

from scripts.powerplatform_tooling import check, summarize_flowagent


class FlowAgentSummaryTests(unittest.TestCase):
    def envelope(self, data, **extra):
        return {'result': {'content': [{'type': 'text', 'text': json.dumps(data)}], **extra}}

    def test_terminal_status_is_retained_without_links_or_payloads(self):
        result = summarize_flowagent(self.envelope({
            'name': 'private-run-id',
            'properties': {'status': 'Succeeded', 'startTime': '2026-10-13T13:33:44Z',
                           'endTime': '2026-10-13T13:43:24Z',
                           'trigger': {'outputsLink': {'uri': 'https://example.invalid/?sig=SECRET'},
                                       'outputs': {'patient': 'PRIVATE_CONTENT'}}}}))
        self.assertEqual(result['observations'][0]['status'], 'Succeeded')
        self.assertTrue(result['observations'][0]['terminal'])
        self.assertFalse(result['native_acceptance'])
        serialized = json.dumps(result)
        for private in ['SECRET', 'PRIVATE_CONTENT', 'private-run-id', 'example.invalid']:
            self.assertNotIn(private, serialized)

    def test_running_receipt_remains_nonterminal(self):
        result = summarize_flowagent({'properties': {'status': 'Running'}})
        self.assertFalse(result['observations'][0]['terminal'])
        self.assertEqual(result['scope'], 'RECORDED_RECEIPT_ONLY')

    def test_combined_run_and_paginated_actions_observation_is_not_lost(self):
        result = summarize_flowagent({'run': {'name': 'PRIVATE_RUN',
            'properties': {'status': 'Succeeded'}}, 'actions': {'value': [
                {'name': 'Verify_commit_readback', 'properties': {'status': 'Succeeded'}},
                {'name': 'Parse_source_schema', 'properties': {'status': 'Failed',
                    'error': {'message': 'PRIVATE_DATA https://example.invalid/?sig=SECRET'}}},
            ]}})
        self.assertEqual(result['observations'][0]['status'], 'Succeeded')
        self.assertTrue(result['observations'][0]['terminal'])
        actions = result['observations'][1]
        self.assertEqual(actions['status_counts'], {'Succeeded': 1, 'Failed': 1})
        self.assertIn({'action': 'Parse_source_schema', 'status': 'Failed'},
                      actions['control_and_failed_actions'])
        for withheld in ('PRIVATE_RUN', 'PRIVATE_DATA', 'SECRET', 'example.invalid'):
            self.assertNotIn(withheld, json.dumps(result))
        self.assertFalse(result['native_acceptance'])

    def test_combined_observation_inside_tool_content_and_direct_action_list(self):
        result = summarize_flowagent(self.envelope({'run': {'properties': {'status': 'Running'}},
            'actions': [{'name': 'Pending', 'status': 'Waiting'}]}))
        self.assertEqual(len(result['observations']), 2)
        self.assertFalse(result['observations'][0]['terminal'])
        self.assertEqual(result['observations'][1]['status_counts'], {'Waiting': 1})

    def test_tool_failure_with_success_shaped_body_does_not_report_success(self):
        result = summarize_flowagent(self.envelope({'run': {'properties': {'status': 'Succeeded'}},
            'actions': {'value': []}}, isError=True))
        self.assertTrue(result['is_error'])
        self.assertEqual(result['observations'], [])

    def test_business_payload_status_is_not_recursively_interpreted(self):
        result = summarize_flowagent({'inputs': {'run': {'properties': {'status': 'Succeeded'}}},
            'outputs': {'actions': {'value': [{'name': 'Secret', 'status': 'Failed'}]}}})
        self.assertEqual(result['observations'], [])

    def test_direct_run_with_action_list_keeps_its_run_status(self):
        result = summarize_flowagent({'properties': {'status': 'Failed'},
            'actions': [{'name': 'Parse_source_schema', 'status': 'Failed'}]})
        self.assertEqual(result['observations'][0]['kind'], 'run')
        self.assertEqual(result['observations'][0]['status'], 'Failed')
        self.assertEqual(result['observations'][1]['status_counts'], {'Failed': 1})

    def test_failed_actions_are_visible_without_error_bodies(self):
        result = summarize_flowagent(self.envelope({'actions': [
            {'name': 'Require_archive_persisted', 'status': 'Succeeded'},
            {'name': 'Get_existing_commit_marker', 'status': 'Failed',
             'error': {'message': 'sensitive https://example.invalid/?sig=SECRET'}},
            {'name': 'Other_action', 'status': 'Skipped', 'inputs': 'PRIVATE_CONTENT'}]}))
        observation = result['observations'][0]
        self.assertEqual(observation['status_counts'], {'Succeeded': 1, 'Failed': 1, 'Skipped': 1})
        self.assertIn({'action': 'Get_existing_commit_marker', 'status': 'Failed'},
                      observation['control_and_failed_actions'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('PRIVATE_CONTENT', json.dumps(result))

    def test_only_exact_known_guard_outcomes_are_reported(self):
        data = {'action': 'Verify_commit_readback', 'which': 'outputs', 'contentSize': 26,
                'content': 'COMMIT_READBACK_VERIFIED'}
        result = summarize_flowagent(self.envelope(data))
        self.assertTrue(result['observations'][0]['reported_commit_readback_verified'])
        data['content'] = 'COMMIT_READBACK_VERIFIED https://example.invalid/?sig=SECRET'
        result = summarize_flowagent(self.envelope(data))
        self.assertNotIn('reported_commit_readback_verified', result['observations'][0])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertTrue(result['observations'][0]['payload_withheld'])

    def test_many_failures_remain_bounded_and_unknown_status_is_counted(self):
        rows = [{'name': f'Failed_action_{i}', 'status': 'Failed'} for i in range(25)]
        rows += [{'name': 'Verify_commit_readback', 'status': 'Succeeded'},
                 {'name': 'Unclassified', 'status': 'unexpected'}]
        observation = summarize_flowagent(self.envelope(rows))['observations'][0]
        self.assertEqual(observation['status_counts'], {'Failed': 25, 'Succeeded': 1})
        self.assertEqual(observation['unclassified_actions'], 1)
        self.assertEqual(observation['selected_actions_omitted'], 6)
        self.assertEqual(len(observation['control_and_failed_actions']), 20)
        self.assertEqual(observation['control_and_failed_actions'][0]['action'], 'Verify_commit_readback')

    def test_error_and_malformed_status_cannot_become_success(self):
        result = summarize_flowagent({'result': {'isError': True,
            'content': [{'type': 'text', 'text': 'Failed sign-in: SECRET'}]}})
        self.assertTrue(result['is_error'])
        self.assertEqual(result['observations'], [])
        self.assertNotIn('SECRET', json.dumps(result))
        result = summarize_flowagent({'properties': {'status': {'untrusted': 'Succeeded'}}})
        self.assertEqual(result['observations'], [])


class PowerPlatformToolingTests(unittest.TestCase):
    def test_preflight_separates_installation_from_authentication_and_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            solution = root / "src/Other/Solution.xml"
            solution.parent.mkdir(parents=True)
            solution.write_text("<Solution />", encoding="utf-8")

            def locate(name):
                return "/usr/bin/" + name if name != "gh" else None

            def execute(command):
                return (0, "local command ok") if command[0] in {"pac", "pwsh"} else (1, "extension absent")

            result = check(locator=locate, executor=execute, root=root)
            self.assertEqual(result["status"], "PASS_LOCAL_ONLY")
            self.assertEqual(result["solution_projects"], ["src/Other/Solution.xml"])
            for name, tool in result["tools"].items():
                with self.subTest(tool=name):
                    self.assertEqual(tool["authentication"], "NOT_CHECKED")
                    self.assertFalse(tool["operation_proven"])
            self.assertEqual(result["tools"]["pac"]["installed"], True)
            self.assertEqual(result["tools"]["pac"]["locally_runnable"], True)
            self.assertEqual(result["tools"]["az"]["installed"], True)
            self.assertEqual(result["tools"]["az"]["locally_runnable"], False)
            self.assertEqual(result["tools"]["gh"]["status"], "SKIP")
            self.assertFalse(result["tools"]["gh"]["installed"])

    def test_preflight_reports_timeout_and_executable_race_as_not_runnable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def timeout(_command):
                raise subprocess.TimeoutExpired(["pac"], 15)

            result = check(locator=lambda _name: "/usr/bin/tool", executor=timeout, root=root)
            self.assertEqual(result["tools"]["pac"]["status"], "WARN")
            self.assertFalse(result["tools"]["pac"]["locally_runnable"])
            self.assertEqual(result["tools"]["pac"]["summary"], "command timed out")

            def missing(_command):
                raise FileNotFoundError("gone")

            result = check(locator=lambda _name: "/usr/bin/tool", executor=missing, root=root)
            self.assertEqual(result["tools"]["az"]["status"], "WARN")
            self.assertFalse(result["tools"]["az"]["locally_runnable"])
            self.assertEqual(result["tools"]["az"]["summary"], "executable disappeared after discovery")


if __name__ == "__main__":
    unittest.main()

class ReportValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name)
        (self.report / 'definition.json').write_text('{}')

    def validate(self, executor):
        from scripts.powerplatform_tooling import validate_report
        return validate_report(self.report, executor=executor)

    def test_modes_exit_codes_and_no_native_claim(self):
        calls = []
        def executor(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, 'no errors', '')
        result = self.validate(executor)
        self.assertEqual(result['status'], 'PASS_LOCAL_ONLY')
        self.assertIn('--no-schema', calls[0])
        self.assertNotIn('--no-schema', calls[1])
        self.assertEqual(result['native']['status'], 'NOT_ASSESSED')
        self.assertFalse(result['native_acceptance'])

    def test_child_failure_preserved(self):
        result = self.validate(lambda command, **kwargs: subprocess.CompletedProcess(command, 7, 'binding error', 'detail'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['checks'][0]['exit_code'], 7)
        self.assertEqual(result['checks'][0]['stderr'], 'detail')

    def test_missing_tool_and_timeout_are_incomplete(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('validator', 60, output=b'partial', stderr=b'detail')):
            def executor(command, **kwargs): raise error
            result = self.validate(executor)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertIsNone(result['checks'][0]['exit_code'])
        self.assertEqual(result['checks'][0]['stdout'], 'partial')

    def test_source_drift_cannot_pass(self):
        def executor(command, **kwargs):
            (self.report / 'definition.json').write_text(str(len(command)))
            return subprocess.CompletedProcess(command, 0, '', '')
        result = self.validate(executor)
        self.assertFalse(result['source_unchanged'])
        self.assertEqual(result['status'], 'INCOMPLETE')
