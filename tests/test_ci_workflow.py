import unittest
from pathlib import Path


class CIWorkflowTests(unittest.TestCase):
    def test_source_only_quality_workflow_runs_required_gates(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/local-quality.yml").read_text()
        for command in (
            "python -m unittest discover -s tests -v",
            "python scripts/validate_project.py",
            "python scripts/webfirst_contracts.py validate",
            "python scripts/validate_conductor.py",
            "python scripts/powerplatform_tooling.py check",
            "python scripts/validate_visual_standards.py",
            "python scripts/validate_publication_platform_contract.py",
            "python scripts/validate_grants_flow_contract.py",
            "python scripts/validate_dora_activity_flow_contract.py",
        ):
            self.assertIn(command, workflow)
        self.assertNotIn("pac solution import", workflow)
        self.assertNotIn("powerplatform-actions", workflow)


if __name__ == "__main__":
    unittest.main()
