import importlib.util
import os
import runpy
from unittest.mock import patch
from pathlib import Path
import subprocess
import tempfile
import unittest

GUARD = Path(__file__).parents[1] / 'scripts/check_public_source.py'
spec = importlib.util.spec_from_file_location('public_guard', GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class PublicSourceGuardTests(unittest.TestCase):
    def test_private_files_binary_and_symlinks_are_rejected(self):
        for name in ['.local/candidate.json', 'nested/.local/candidate.json', 'private/receipt.json', 'nested/private/receipt.json', 'reports/output.txt', '.env', 'keys.pem', 'bundle.zip']:
            self.assertTrue(guard.inspect(name, b'example'))
        self.assertTrue(guard.inspect('source.txt', b'\x00example'))
        self.assertTrue(guard.inspect('source.txt', b'example', '120000'))
        self.assertFalse(guard.inspect('.env.example', b'KEY=configure-locally'))

    def test_native_helpers_refuse_missing_target_before_any_cli_call(self):
        for name in ['create_sharepoint_columns.py', 'retry_failed.py', 'sync_sharepoint_seed.py']:
            with self.subTest(script=name), patch.dict(os.environ, {'SHAREPOINT_WEB_URL': ''}), patch('subprocess.run', side_effect=AssertionError('No native CLI calls permitted')):
                with self.assertRaisesRegex(RuntimeError, 'Set SHAREPOINT_WEB_URL'):
                    runpy.run_path(str(GUARD.parent / name), run_name='__main__')

    def test_real_identity_shapes_fail_while_examples_pass(self):
        samples = [b'person@' + b'organization.org', b'https://' + b'actual-tenant.sharepoint.com/site',
                   b'/Users/' + b'someone/project', b'/personal/' + b'actual_account',
                   ('12345678-' + '1234-4321-8765-123456789abc').encode()]
        for sample in samples:
            self.assertTrue(guard.inspect('source.txt', sample))
        self.assertFalse(guard.inspect('source.txt', b'contact@example.invalid https://example.sharepoint.com/personal/example_operator'))
        self.assertFalse(guard.inspect('source.txt', b'00000000-0000-4000-8000-0123456789ab'))

    def test_staged_bytes_cannot_be_hidden_by_clean_working_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'scripts').mkdir()
            (root/'scripts/check_public_source.py').write_bytes(GUARD.read_bytes())
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            source = root/'example.txt'
            source.write_bytes(b'person@' + b'organization.org')
            subprocess.run(['git', 'add', 'example.txt'], cwd=root, check=True)
            source.write_text('clean working bytes')
            result = subprocess.run(['python3', 'scripts/check_public_source.py', '--staged'], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('non-example account address', result.stderr)

if __name__ == '__main__':
    unittest.main()
