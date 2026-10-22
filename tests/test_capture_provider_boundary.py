"""Native capture never invents or substitutes an authentication route."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import redirect_stderr
from io import StringIO
from scripts import capture_report_bound_source_union, capture_retained_canary_acceptance
from scripts.capture_retained_canary_acceptance import _token_for


class CaptureProviderBoundaryTests(unittest.TestCase):
    def test_missing_provider_refuses_before_any_authentication(self):
        with self.assertRaisesRegex(ValueError, 'already-qualified VS Code'):
            _token_for('https://api.fabric.microsoft.com')

    def test_exact_resource_is_forwarded_once_and_denial_is_not_retried(self):
        calls = []
        def provider(resource):
            calls.append(resource)
            raise PermissionError('qualified resource denial')
        with self.assertRaises(PermissionError):
            _token_for('https://api.fabric.microsoft.com', provider)
        self.assertEqual(calls, ['https://api.fabric.microsoft.com'])

    def test_empty_result_or_unlisted_resource_is_not_a_token(self):
        with self.assertRaises(ValueError):
            _token_for('https://api.fabric.microsoft.com', lambda _: '')
        calls = []
        with self.assertRaises(ValueError):
            _token_for('https://example.invalid', calls.append)
        self.assertEqual(calls, [])

    def test_token_is_returned_in_memory_only(self):
        supplied = 'fictional-provider-result'
        self.assertEqual(_token_for('https://api.fabric.microsoft.com', lambda _: supplied), supplied)

    def test_both_capture_entrypoints_refuse_before_reading_files_or_authentication(self):
        for module in [capture_report_bound_source_union, capture_retained_canary_acceptance]:
            with self.subTest(module=module.__name__), redirect_stderr(StringIO()), patch(
                    'argparse.ArgumentParser.parse_args', return_value=SimpleNamespace()):
                with self.assertRaises(SystemExit) as error:
                    module.main()
                self.assertEqual(error.exception.code, 2)
