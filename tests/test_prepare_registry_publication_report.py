import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_registry_publication_report import prepare, PAGE


class RegistryReportTests(unittest.TestCase):
    def fixture(self, root):
        import test_prepare_protocol_study_award as fixture
        from prepare_protocol_study_award_report import prepare as protocol_prepare
        previous = fixture.ProtocolPreparationTests().fixture(root / 'previous')
        source = root / 'source'; protocol_prepare(previous, source)
        return source

    def test_append_preserves_all_visual_bytes_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = self.fixture(root); output = root / 'output'
            before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            self.assertEqual(prepare(source, output)['added_visuals'], 4)
            for name, raw in before.items():
                self.assertEqual((source / name).read_bytes(), raw)
                if name != PAGE / 'page.json':
                    self.assertEqual((output / name).read_bytes(), raw)
            self.assertEqual(json.loads((output / PAGE / 'page.json').read_text())['height'], 3600)
            with self.assertRaises(ValueError):
                prepare(source, output)

    def test_human_named_visual_collision_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = self.fixture(root); output = root / 'output'
            target = source / PAGE / 'visuals/registry-publication-heading/visual.json'
            target.parent.mkdir(); target.write_text('Human-owned visual')
            with self.assertRaisesRegex(ValueError, 'require reconciliation'):
                prepare(source, output)
            self.assertFalse(output.exists()); self.assertEqual(target.read_text(), 'Human-owned visual')
