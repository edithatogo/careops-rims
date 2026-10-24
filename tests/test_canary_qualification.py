"""Run the actual workflow receipt; failures and missing evidence never qualify."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['source', 'policy', 'python', 'helper', 'bootstrap', 'resolve', 'qualification']


class CanaryQualificationTests(unittest.TestCase):
    def test_actual_receipt_preserves_failures_and_requires_bound_runtime_evidence(self):
        workflow = (ROOT / '.github/workflows/development-canary.yml').read_text()
        step = workflow.split('      - name: Record actual tool qualification outcomes\n', 1)[1].split('\n      - ', 1)[0]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1]).replace('python3', shlex.quote(sys.executable), 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); evidence = root / '.local/tool-canary'; evidence.mkdir(parents=True)
            helper = root / '.local/rims-canary-helper/bin/python'
            helper.parent.mkdir(parents=True); helper.symlink_to(sys.executable)
            def execute(outcomes, expect_failure=False):
                env = dict(os.environ, GITHUB_WORKSPACE=str(root), GITHUB_SHA='a' * 40, **{name.upper() + '_OUTCOME': outcomes.get(name, 'success') for name in STAGES})
                result = subprocess.run(['/bin/bash', '-euc', script], cwd=root, env=env, check=False, capture_output=True)
                self.assertEqual(result.returncode != 0, expect_failure, result.stderr.decode())
                receipt = json.loads((evidence / 'qualification.json').read_text())
                self.assertFalse(receipt['promoted']); self.assertFalse(receipt['nativeWrites'])
                return receipt
            for position, stage in enumerate(STAGES):
                if stage == 'helper':
                    continue  # Refused helpers use the independent shell receipt below.
                outcomes = {name: 'success' if i < position else 'failure' if i == position else 'skipped' for i, name in enumerate(STAGES)}
                receipt = execute({**outcomes, 'helper': 'success'})
                self.assertEqual(receipt['stages'], {**outcomes, 'helper': 'success'})
                self.assertEqual(receipt['failedStage'], stage)
                self.assertEqual(receipt['state'], 'setup-blocked' if position < 5 else 'executed-failure')
            self.assertEqual(execute({'qualification': 'cancelled'})['state'], 'cancelled')
            self.assertEqual(execute({'qualification': 'skipped'})['state'], 'not-executed')
            self.assertEqual(execute({}, expect_failure=True)['state'], 'evidence-mismatch')
            lock = b'fictional==1.0 --hash=sha256:fixture\n'
            (evidence / 'requirements.lock').write_bytes(lock)
            (evidence / 'candidate.json').write_text(json.dumps({'lockSha256': hashlib.sha256(lock).hexdigest()}))
            for name, value in [('python-version', 'Python 3.15.1 (fixture)'), ('tool-python-version', 'Python 3.15.1 (fixture)')]:
                (evidence / (name + '.txt')).write_text(value)
            self.assertEqual(execute({})['state'], 'qualified-tool-candidate')
            (evidence / 'tool-python-version.txt').write_text('Python 3.13.0 (fixture)')
            self.assertEqual(execute({}, expect_failure=True)['state'], 'runtime-mismatch')
            (evidence / 'candidate.json').write_text('{broken')
            self.assertEqual(execute({}, expect_failure=True)['state'], 'evidence-invalid')


class CanaryHelperFailureTests(unittest.TestCase):
    def test_unverified_helper_is_never_executed_by_either_terminal_receipt(self):
        workflow = (ROOT / '.github/workflows/development-canary.yml').read_text()
        cases = [
            ('Record actual tool qualification outcomes', '.local/tool-canary/qualification.json'),
            ('Record actual qualification or explicit unavailability', '.local/runtime-canary/helper-failure.json'),
        ]
        for name, receipt_path in cases:
            with self.subTest(step=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                helper = root / '.local/rims-canary-helper/bin/python'
                helper.parent.mkdir(parents=True)
                discovery = root / '.local/runtime-canary/discovery.json'
                discovery.parent.mkdir(parents=True)
                discovery.write_text('{"preserve":"existing-discovery"}')
                marker = root / 'unverified-executed'
                helper.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 0\n')
                helper.chmod(0o700)
                step = workflow.split('      - name: ' + name + '\n', 1)[1].split('\n      - ', 1)[0]
                shell = textwrap.dedent(step.split('        run: |\n', 1)[1])
                for present in [True, False]:
                    if not present: helper.unlink()
                    env = dict(os.environ, GITHUB_WORKSPACE=str(root), HELPER_OUTCOME='failure')
                    result = subprocess.run(['/bin/bash', '-euc', shell], cwd=root, env=env, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    receipt = json.loads((root / receipt_path).read_text())
                    self.assertEqual(receipt['state'], 'setup-blocked')
                    self.assertFalse(receipt['promoted']); self.assertFalse(receipt['nativeWrites'])
                    self.assertFalse(marker.exists())
                    self.assertEqual(discovery.read_text(), '{"preserve":"existing-discovery"}')
