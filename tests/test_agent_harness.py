import contextlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.agent_harness import commands, load_config, public_file, run_checks


class HarnessTests(unittest.TestCase):
    def test_failure_survives_later_success_and_all_checks_run(self):
        seen = []
        def runner(command, **kwargs):
            seen.append(command)
            return SimpleNamespace(returncode=1 if len(seen) == 1 else 0)
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_checks([['first'], ['second'], ['third']], runner)
        self.assertEqual(result, 1)
        self.assertEqual(len(seen), 3)

    def test_context_rejects_private_and_escaping_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ['private/receipt.json', '../secret', 'downloads/raw.json']:
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    public_file(root, relative)

    def test_all_route_includes_required_checks(self):
        checks = commands(load_config(), 'all')
        self.assertEqual(len(checks), 5)
        self.assertIn('scripts/validate_project.py', checks[1])
        self.assertIn('scripts/webfirst_contracts.py', checks[2])
        self.assertIn('scripts/validate_conductor.py', checks[3])
        self.assertIn('scripts/powerplatform_tooling.py', checks[4])
