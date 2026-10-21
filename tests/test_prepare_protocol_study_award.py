import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlunsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_protocol_study_award_model import prepare as prepare_model
from prepare_protocol_study_award_report import (
    prepare, PAGE, EXPECTED_STATUS_TEXT, EXPECTED_STATUS_TOOLTIP)
from prepare_dashboard_relationship_summary import text_literal


class ProtocolPreparationTests(unittest.TestCase):
    def fixture(self, root):
        page = root / PAGE
        page.mkdir(parents=True)
        (page / 'page.json').write_text(json.dumps({'height': 2400}))
        visual = {'visual': {'objects': {'general': [{'properties': {'paragraphs': [
            {'textRuns': [{'value': 'template'}]}]}}]}, 'visualContainerObjects': {}}}
        for name in ['award-crosswalk-heading', 'award-crosswalk-count', 'award-crosswalk-evidence', 'chain-status']:
            value = copy.deepcopy(visual)
            if name == 'chain-status':
                value['visual']['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = EXPECTED_STATUS_TEXT
                value['visual']['visualContainerObjects']['visualHeaderTooltip'] = [
                    {'properties': {'text': text_literal(EXPECTED_STATUS_TOOLTIP)}}]
            target = page / 'visuals' / name / 'visual.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(value))
        (root / 'retained-human-note.txt').write_text('Human note remains unchanged')
        return root

    def test_additive_report_retains_source_and_other_content_and_refuses_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = self.fixture(root / 'source'); output = root / 'output'
            before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            self.assertEqual(prepare(source, output)['added_visuals'], 4)
            for name, value in before.items():
                self.assertEqual((source / name).read_bytes(), value)
                if name not in {PAGE / 'page.json', PAGE / 'visuals/chain-status/visual.json'}:
                    self.assertEqual((output / name).read_bytes(), value)
            with self.assertRaises(ValueError):
                prepare(source, output)

    def test_human_modified_status_or_tooltip_refused_before_output_creation(self):
        for field in ['text', 'tooltip']:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as d:
                root = Path(d); source = self.fixture(root / 'source'); output = root / 'output'
                path = source / PAGE / 'visuals/chain-status/visual.json'; value = json.loads(path.read_text())
                if field == 'text':
                    value['visual']['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = 'Human-edited unresolved concern'
                else:
                    value['visual']['visualContainerObjects']['visualHeaderTooltip'][0]['properties']['text'] = text_literal('Human caveat')
                path.write_text(json.dumps(value)); before = path.read_bytes()
                with self.assertRaisesRegex(ValueError, 'Human-modified'):
                    prepare(source, output)
                self.assertFalse(output.exists()); self.assertEqual(path.read_bytes(), before)

    def test_model_refuses_any_archive_userinfo_before_reading_preimage(self):
        for userinfo in [':test@', '@']:
            uri = urlunsplit(('https', userinfo + 'example.sharepoint.com', '/Documents/award-crosswalk-fixture', '', ''))
            with self.subTest(userinfo=userinfo), self.assertRaisesRegex(ValueError, 'Exact retained protocol batch'):
                prepare_model({}, uri, 'fixture', 'unused')
