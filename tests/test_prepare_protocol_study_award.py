import copy
import base64
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

    def model_fixture(self):
        from prepare_source_relationship_model import prepare as source_prepare
        from prepare_award_crosswalk_model import prepare as alias_prepare
        from prepare_crossref_award_model import prepare as crossref_prepare
        def part(path, value):
            return {'path': path, 'payload': base64.b64encode(value.encode()).decode(), 'payloadType': 'InlineBase64'}
        document = {'definition': {'parts': [
            part('definition/model.tmdl', 'model Model'),
            part('definition/relationships.tmdl', ''),
            part('definition/tables/Study register.tmdl', 'table Study\n\tpartition Study = m\n\t\tsource = SharePoint.Tables("https://example.sharepoint.com/sites/research",[ApiVersion=15])'),
            part('definition/tables/Publication.tmdl', 'table Publication\n\tcolumn DOI\n\tpartition Publication = m\n\t\tsource = ExistingAcceptedSource'),
            part('human-review.txt', 'Retain human review and unresolved concern')]}}
        document = source_prepare(document, Path('config/source-relationship-evidence.m').read_text())
        document = alias_prepare(document, 'https://example.sharepoint.com/sites/research/Documents/award-crosswalk-fixture', 'fixture', Path('config/award-identifier-crosswalks.m').read_text())
        return crossref_prepare(document, 'https://example.sharepoint.com/sites/research/Documents/award-crosswalk-fixture', 'fixture', Path('config/crossref-award-crosswalks.m').read_text())

    def test_protocol_model_integrates_with_existing_preparers_and_preserves_other_parts(self):
        before = self.model_fixture(); original = copy.deepcopy(before)
        result = prepare_model(before, 'https://example.sharepoint.com/sites/research/Documents/award-crosswalk-fixture', 'fixture', Path('config/protocol-study-award-evidence.m').read_text())
        self.assertEqual(before, original)
        a = {p['path']: p['payload'] for p in before['definition']['parts']}
        b = {p['path']: p['payload'] for p in result['definition']['parts']}
        self.assertEqual([k for k in a if a[k] != b[k]], ['definition/tables/SourceRelationshipEvidence.tmdl'])
        with self.assertRaises(ValueError):
            prepare_model(result, 'https://example.sharepoint.com/sites/research/Documents/award-crosswalk-fixture', 'fixture', 'unused')

    def test_protocol_archive_wrong_tenant_site_or_library_refused_without_mutating_input(self):
        before = self.model_fixture(); original = copy.deepcopy(before)
        for uri in ['https://contoso.sharepoint.com/sites/research/Documents/award-crosswalk-fixture',
                    'https://example.sharepoint.com/sites/other/Documents/award-crosswalk-fixture',
                    'https://example.sharepoint.com/sites/research/award-crosswalk-fixture']:
            with self.subTest(uri=uri), self.assertRaisesRegex(ValueError, 'bound study site'):
                prepare_model(before, uri, 'fixture', 'unused')
        self.assertEqual(before, original)

    def test_model_refuses_any_archive_userinfo_before_reading_preimage(self):
        for userinfo in [':test@', '@']:
            uri = urlunsplit(('https', userinfo + 'example.sharepoint.com', '/Documents/award-crosswalk-fixture', '', ''))
            with self.subTest(userinfo=userinfo), self.assertRaisesRegex(ValueError, 'Exact retained protocol batch'):
                prepare_model({}, uri, 'fixture', 'unused')
