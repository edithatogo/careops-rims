import unittest
from pathlib import Path

class CIWorkflowTests(unittest.TestCase):
    def test_public_checks_use_same_offline_entrypoint_as_fresh_clone(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/security.yml').read_text()
        for command in ('python3 scripts/run_public_tests.py', 'python3 scripts/check_public_docs.py', 'python3 scripts/check_public_source.py', 'gitleaks git', 'gitleaks dir'):
            self.assertIn(command, workflow)
        for mutation in ('pac solution import', 'm365 login', 'flow enable'):
            self.assertNotIn(mutation, workflow)
