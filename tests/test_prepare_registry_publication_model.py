import base64
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_registry_publication_model import prepare


class RegistryModelPreparationTests(unittest.TestCase):
    def document(self):
        source = '''table SourceRelationshipEvidence
\tmeasure 'Accepted' = 123
\tcolumn EvidenceKey
\tcolumn SourceProvider = SWITCH(TRUE(), LEFT([SourceWorkID],9) = "protocol:", "Trial protocol", "OpenAlex")
\tpartition SourceRelationshipEvidence = m
\t\tsource =
\t\t\t\tlet StudySite="https://example.sharepoint.com", ReadStudy=(S)=>S,
\t\t\t\tRows=Table.Buffer(Table.FromRecords(BeforeProtocol & ProtocolStudyAwardEvidence,Columns,MissingField.Error))
\t\t\t\tin Rows
'''
        return {'definition': {'parts': [dict(path='definition/tables/SourceRelationshipEvidence.tmdl',
            payload=base64.b64encode(source.encode()).decode(), payloadType='InlineBase64'),
            dict(path='definition/tables/Publication.tmdl', payload='unchanged', payloadType='InlineBase64')]}}

    def test_preserves_input_and_unrelated_model_and_refuses_reapplication(self):
        doc = self.document(); before = copy.deepcopy(doc)
        candidate = prepare(doc, 'https://example.sharepoint.com/Documents/award-crosswalk-fixture', 'fixture', '(A,B,C)=>{}')
        self.assertEqual(doc, before)
        self.assertEqual(candidate['definition']['parts'][1], before['definition']['parts'][1])
        self.assertIn("measure 'Accepted' = 123", base64.b64decode(candidate['definition']['parts'][0]['payload']).decode())
        with self.assertRaisesRegex(ValueError, 'requires reconciliation'):
            prepare(candidate, 'https://example.sharepoint.com/Documents/award-crosswalk-fixture', 'fixture', 'x')

    def test_rejects_credentials_ports_and_different_source_batch(self):
        from urllib.parse import urlunsplit
        urls = [urlunsplit(('https', ':test@' + 'example.sharepoint.com', '/Documents/award-crosswalk-fixture', '', '')),
                urlunsplit(('https', 'example.sharepoint.com' + ':443', '/Documents/award-crosswalk-fixture', '', '')),
                'https://example.sharepoint.com/Documents/award-crosswalk-other']
        for url in urls:
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'Exact retained registry batch URL'):
                prepare(self.document(), url, 'fixture', 'x')

    def test_bound_site_and_library_must_match_retained_reader(self):
        before = self.document(); original = copy.deepcopy(before)
        for uri in ['https://contoso.sharepoint.com/Documents/award-crosswalk-fixture',
                    'https://example.sharepoint.com/award-crosswalk-fixture']:
            with self.subTest(uri=uri), self.assertRaisesRegex(ValueError, 'bound study site'):
                prepare(before, uri, 'fixture', 'unused')
        self.assertEqual(before, original)

    def test_integrates_with_full_existing_protocol_preparation_chain(self):
        import test_prepare_protocol_study_award as fixture
        from prepare_protocol_study_award_model import prepare as protocol_prepare
        uri = 'https://example.sharepoint.com/sites/research/Documents/award-crosswalk-fixture'
        doc = protocol_prepare(fixture.ProtocolPreparationTests().model_fixture(), uri, 'fixture',
                               Path('config/protocol-study-award-evidence.m').read_text())
        before = copy.deepcopy(doc)
        result = prepare(doc, uri, 'fixture', Path('config/registry-publication-crosswalks.m').read_text())
        self.assertEqual(doc, before)
        changed = [a['path'] for a, b in zip(before['definition']['parts'], result['definition']['parts']) if a != b]
        self.assertEqual(changed, ['definition/tables/SourceRelationshipEvidence.tmdl'])
