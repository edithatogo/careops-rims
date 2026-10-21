import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_qualified_collaboration_report import PAGE, prepare


class CollaborationReportTests(unittest.TestCase):
    def fixture(self, root):
        def write(path, value):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value))
        write(PAGE / 'page.json', dict(height=1824, width=1920))
        properties = {'title': [{'properties': {}}], 'general': [{'properties': {}}],
                      'visualHeaderTooltip': [{'properties': {}}]}
        write(PAGE / 'visuals/pairs/visual.json', dict(name='pairs', position=dict(tabOrder=1),
              visual=dict(visualType='cardVisual', visualContainerObjects=properties,
                          query=dict(queryState=dict(Data=dict(projections=[]))))))
        write(PAGE / 'visuals/limits/visual.json', dict(name='limits', position=dict(tabOrder=2),
              visual=dict(objects=dict(general=[dict(properties=dict(paragraphs=[
                  dict(textRuns=[dict(value='Existing limitations', textStyle={})])]))]),
                  visualContainerObjects=properties)))
        for i, name in enumerate(['provider-authors', 'researcher-pattern', 'institution-pattern']):
            write(PAGE / 'visuals' / name / 'visual.json', dict(name=name, position=dict(tabOrder=i+3)))
        write(Path('definition/report.json'), dict(preserved='unrelated report part'))
        return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_additive_layout_preserves_source_and_unrelated_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source'; before = self.fixture(source)
            target = root / 'candidate'; result = prepare(source, target)
            self.assertEqual(result['new_visuals'], 5)
            self.assertEqual(result['changed_existing_parts'], 4)
            self.assertEqual({p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}, before)
            changed = {PAGE / 'page.json'} | {PAGE / 'visuals' / n / 'visual.json' for n in
                       ['provider-authors', 'researcher-pattern', 'institution-pattern']}
            for path, content in before.items():
                if path not in changed:
                    self.assertEqual((target / path).read_bytes(), content)
            self.assertEqual(len(list((target / PAGE / 'visuals').glob('*/visual.json'))), 10)
            self.assertEqual(json.loads((target / PAGE / 'page.json').read_bytes())['height'], 2176)
            self.assertTrue(all(json.loads((target / path).read_bytes())['filterConfig']['filters']
                                for path in changed if path.name == 'visual.json'))
            with self.assertRaisesRegex(ValueError, 'New candidate'):
                prepare(source, target)
            with self.assertRaisesRegex(ValueError, 'layout'):
                prepare(target, root / 'retry')

    def test_existing_chart_filter_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source'; self.fixture(source)
            path = source / PAGE / 'visuals/provider-authors/visual.json'
            chart = json.loads(path.read_bytes()); chart['filterConfig'] = {'filters': ['retained']}
            path.write_text(json.dumps(chart))
            with self.assertRaisesRegex(ValueError, 'existing source chart filters'):
                prepare(source, root / 'candidate')
            self.assertEqual(json.loads(path.read_bytes())['filterConfig']['filters'], ['retained'])

    def test_candidate_cannot_be_created_inside_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source'; before = self.fixture(source)
            with self.assertRaisesRegex(ValueError, 'outside source'):
                prepare(source, source / 'candidate')
            self.assertEqual({p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}, before)
