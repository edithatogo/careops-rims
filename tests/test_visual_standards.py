"""Unit tests for visual geometry validation and WCAG AA contrast standards."""
import unittest
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_visual_standards import (
    calculate_contrast_ratio,
    check_wcag_compliance,
    audit_visual_geometry,
    audit_all_report_visuals,
    audit_report_field_bindings,
)


class TestVisualStandards(unittest.TestCase):
    def test_wcag_contrast_black_white(self):
        ratio = calculate_contrast_ratio("#000000", "#FFFFFF")
        self.assertAlmostEqual(ratio, 21.0, places=1)

    def test_wcag_contrast_theme_palette(self):
        # Neutral Primary against White
        ratio, passed = check_wcag_compliance("#201F1E", "#FFFFFF")
        self.assertTrue(passed)
        self.assertGreaterEqual(ratio, 4.5)

        # Theme Teal against White
        ratio, passed = check_wcag_compliance("#00828A", "#FFFFFF")
        self.assertTrue(passed)
        self.assertGreaterEqual(ratio, 4.5)

    def test_report_visual_geometries_on_8px_grid(self):
        audits = audit_all_report_visuals()
        self.assertGreater(len(audits), 0)
        for visual in audits:
            self.assertTrue(
                visual["valid_grid_8px"],
                f"Visual {visual['name']} ({visual['file']}) failed 8px grid: {visual['violations']}"
            )

    def test_incomplete_geometry_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "visual.json"
            path.write_text(json.dumps({"name": "incomplete", "position": {"x": 0}}), encoding="utf-8")
            audit = audit_visual_geometry(path)
        self.assertFalse(audit["valid_grid_8px"])
        self.assertTrue(any("finite number" in violation for violation in audit["violations"]))

    def test_report_field_bindings_resolve_against_local_model(self):
        failures = audit_report_field_bindings()
        self.assertEqual([], failures, f"Unresolved PBIR bindings: {failures}")

    def test_missing_report_field_binding_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            pages = Path(folder) / "pages"
            pages.mkdir()
            visual_dir = pages / "Example" / "visuals" / "broken"
            visual_dir.mkdir(parents=True)
            (visual_dir / "visual.json").write_text(json.dumps({
                "name": "broken",
                "visual": {"query": {"queryState": {"Values": [{
                    "field": {"Column": {"Expression": {"SourceRef": {"Entity": "Publication"}}, "Property": "NotARealField"}}
                }]}}}
            }), encoding="utf-8")
            failures = audit_report_field_bindings(pages, ROOT / "powerbi/CHHHS Research Publications.SemanticModel/definition/tables")
        self.assertEqual(1, len(failures))
        self.assertEqual("NotARealField", failures[0]["property"])


if __name__ == "__main__":
    unittest.main()
