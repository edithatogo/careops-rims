import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_government_award_model import prepare as model_prepare
from prepare_government_award_report import prepare as report_prepare, PAGE


class GovernmentPreparationTests(unittest.TestCase):
    def model_fixture(self):
        from test_prepare_registry_publication_model import RegistryModelPreparationTests
        from prepare_registry_publication_model import prepare
        return prepare(RegistryModelPreparationTests().document(),
                       'https://example.sharepoint.com/Documents/award-crosswalk-fixture', 'fixture', '(A,B,C)=>{}')

    def test_preserves_other_model_parts_input_and_existing_measures(self):
        doc = self.model_fixture()
        before = copy.deepcopy(doc)
        after = model_prepare(doc, 'https://example.sharepoint.com/Documents/award-crosswalk-fixture',
                              'fixture', '(A,B,C)=>{}')
        self.assertEqual(doc, before)
        self.assertEqual(after['definition']['parts'][1:], before['definition']['parts'][1:])
        text = base64.b64decode(after['definition']['parts'][0]['payload']).decode()
        self.assertIn("measure 'Accepted' = 123", text)
        self.assertIn("measure 'Registry related publication links'", text)
        with self.assertRaisesRegex(ValueError, 'requires reconciliation'):
            model_prepare(after, 'https://example.sharepoint.com/Documents/award-crosswalk-fixture', 'fixture', '')

    def test_other_site_library_credentials_and_batch_are_refused(self):
        doc = self.model_fixture()
        for uri in ['https://contoso.sharepoint.com/Documents/award-crosswalk-fixture',
                    'https://example.sharepoint.com/Other/award-crosswalk-fixture',
                    'https://example.sharepoint.com/Documents/award-crosswalk-other',
                    'https://' + 'name' + '@' + 'example.sharepoint.com/Documents/award-crosswalk-fixture']:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                model_prepare(doc, uri, 'fixture', '')

    def report_fixture(self, root):
        page = root / PAGE
        page.mkdir(parents=True)
        (page / 'page.json').write_text(json.dumps(dict(height=3600)))
        template = {'name': 'fixture', 'position': {}, 'visual': {'visualContainerObjects': {},
                    'objects': {'general': [{'properties': {'paragraphs': [{'textRuns': [{'value': 'old'}]}]}}]}}}
        for name in ['registry-publication-heading', 'registry-publication-count',
                     'registry-reference-count', 'registry-publication-evidence']:
            target = page / 'visuals' / name / 'visual.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(template))
        return root

    def test_report_preserves_visual_bytes_and_refuses_human_owned_name_collision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = self.report_fixture(root / 'source')
            originals = {p.relative_to(source): p.read_bytes() for p in source.rglob('visual.json')}
            output = root / 'output'
            self.assertEqual(report_prepare(source, output)['added_visuals'], 4)
            for name, data in originals.items():
                self.assertEqual((output / name).read_bytes(), data)
                self.assertEqual((source / name).read_bytes(), data)
            target = source / PAGE / 'visuals/government-award-heading'
            target.mkdir()
            (target / 'visual.json').write_text('Human edit')
            blocked = root / 'blocked'
            with self.assertRaisesRegex(ValueError, 'require reconciliation'):
                report_prepare(source, blocked)
            self.assertFalse(blocked.exists())
