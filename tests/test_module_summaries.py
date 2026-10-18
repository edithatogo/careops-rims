import re
import unittest
from pathlib import Path


SUMMARY = Path(__file__).parents[1] / "docs" / "RIMS_MODULE_SUMMARIES.md"


class ModuleSummaryDocumentationTests(unittest.TestCase):
    def test_all_rims_modules_have_requirements_design_and_mermaid(self):
        text = SUMMARY.read_text(encoding="utf-8")
        expected = [
            "Publications registry",
            "DORA activity registry",
            "Author and organisation enrichment",
            "Grants and funding opportunities",
            "RIMS dashboard and user experience",
            "Platform operations, versioning and CI/CD",
        ]
        for heading in expected:
            self.assertIn("## ", text)
            self.assertRegex(text, rf"## \d+\. {re.escape(heading)}")

        blocks = re.findall(r"```mermaid\n(.*?)\n```", text, flags=re.DOTALL)
        self.assertIn("## Horizontal and vertical schema", text)
        expected_diagrams = len(expected) + 1  # overview plus one per module
        self.assertEqual(len(blocks), expected_diagrams)
        for block in blocks:
            self.assertRegex(block, r"(?m)^flowchart (LR|TD|RL|BT)\s*$")
            self.assertGreaterEqual(len(re.findall(r"(?m)^\s*\S+.*-->.*$", block)), 2)

        self.assertEqual(text.count("\n```"), expected_diagrams * 2)


if __name__ == "__main__":
    unittest.main()
