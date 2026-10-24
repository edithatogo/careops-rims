import importlib.util
import os
import runpy
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
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
            result = subprocess.run([sys.executable, 'scripts/check_public_source.py', '--staged'], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('non-example account address', result.stderr)


class StagedBatchTests(unittest.TestCase):
    def test_many_staged_files_use_one_object_reader_and_keep_index_bytes(self):
        import contextlib
        import io
        real_popen = subprocess.Popen
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            names = ['plain.txt', 'spaced name.txt', 'line\nname.txt', 'empty.txt', 'unicode.txt', 'épreuve.txt']
            for index, name in enumerate(names):
                raw = 'naïve example'.encode('utf-8') if name == 'épreuve.txt' else ('example ' * index).encode()
                (root / name).write_bytes(raw)
            subprocess.run(['git', 'add', '--all'], cwd=root, check=True)
            # A working-file change must not replace the indexed input.
            (root / 'plain.txt').write_bytes(b'person@' + b'organization.org')
            calls = []
            def popen(command, *args, **kwargs):
                if command[:2] == ['git', 'cat-file']: calls.append(command)
                return real_popen(command, *args, **kwargs)
            with patch.object(guard, 'ROOT', root), patch.object(guard.subprocess, 'Popen', side_effect=popen), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(guard.main(['--staged']), 0)
            self.assertEqual(calls, [['git', 'cat-file', '--batch']])
            (root / 'plain.txt').write_text('example')
            for payload in [b'person@' + b'organization.org', b'example\x00binary', b'\xff']:
                with self.subTest(payload=payload):
                    (root / 'spaced name.txt').write_bytes(payload)
                    subprocess.run(['git', 'add', '--all'], cwd=root, check=True)
                    with patch.object(guard, 'ROOT', root), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(guard.main(['--staged']), 1)

    def test_object_protocol_refuses_missing_wrong_type_or_truncated_data(self):
        import io
        from types import SimpleNamespace
        identity = 'a' * 40
        wrong = 'b' * 40
        invalid = [
            b'', (identity + ' missing\n').encode(),
            (wrong + ' blob 3\nabc\n').encode(),
            (identity + ' commit 3\nabc\n').encode(),
            (identity + ' blob -1\n').encode(),
            (identity + ' blob invalid\n').encode(),
            (identity + ' blob ' + str(1 << 100) + '\n').encode(),
            (identity + ' blob 10\nabc\n').encode(),
            (identity + ' blob 3\nabcX').encode(),
        ]
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(ValueError):
                guard.read_index_blob(SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(response)), identity)
        reader = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO((identity + ' blob 3\nabc\n').encode()))
        self.assertEqual(guard.read_index_blob(reader, identity), b'abc')
        self.assertEqual(reader.stdin.getvalue(), (identity + '\n').encode())
        payload = b'a' * (1024 * 1024 + 3)
        reader = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO((identity + ' blob ' + str(len(payload)) + '\n').encode() + payload + b'\n'))
        self.assertEqual(guard.read_index_blob(reader, identity), payload)

    def test_nonzero_reader_exit_after_valid_blob_is_refused(self):
        import io
        from unittest.mock import MagicMock
        identity = 'a' * 40
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdin = io.BytesIO()
        process.stdout = io.BytesIO((identity + ' blob 3\nabc\n').encode())
        process.returncode = 23
        with patch.object(guard.subprocess, 'Popen', return_value=process), self.assertRaises(subprocess.CalledProcessError):
            with guard.index_reader() as reader:
                self.assertEqual(guard.read_index_blob(reader, identity), b'abc')
        self.assertTrue(process.stdin.closed)
        process.stdout.close()

    def test_unresolved_index_conflict_remains_a_failure(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            identity = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], input=b'example', cwd=root).decode().strip()
            records = ''.join('100644 ' + identity + ' ' + str(stage) + '\tconflict.txt\n' for stage in [1, 2, 3])
            subprocess.run(['git', 'update-index', '--index-info'], input=records.encode(), cwd=root, check=True)
            errors = io.StringIO()
            with patch.object(guard, 'ROOT', root), contextlib.redirect_stderr(errors):
                self.assertEqual(guard.main(['--staged']), 1)
            self.assertIn('unresolved index conflict', errors.getvalue())

if __name__ == '__main__':
    unittest.main()
