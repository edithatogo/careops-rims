import base64
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_award_crosswalk_model import prepare

class CrosswalkModelTests(unittest.TestCase):
    def document(self):
        text = ('table SourceRelationshipEvidence\n\tpartition SourceRelationshipEvidence = m\n'
                '\t\tsource =\n\t\t\t\tlet ReadStudy=each null, UniqueWorks={},\n'
                '\t\t\t\tRows=Table.Buffer(Table.FromRecords(Output & StudyEvidence & PubMedEvidence,Columns,MissingField.Error))\n'
                '\t\t\t\tin Rows\n')
        return {'definition': {'parts': [
            {'path': 'definition/tables/SourceRelationshipEvidence.tmdl', 'payload': base64.b64encode(text.encode()).decode(), 'payloadType': 'InlineBase64'},
            {'path': 'protected-review.tmdl', 'payload': base64.b64encode(b'HumanReview=retained').decode(), 'payloadType': 'InlineBase64'}]}}

    def test_preserves_original_and_unrelated_parts_and_refuses_duplicate_application(self):
        doc = self.document(); before = copy.deepcopy(doc)
        uri = 'https://example.sharepoint.com/Documents/award-crosswalk-fixture'
        result = prepare(doc, uri, 'fixture', '(A,B,C,D,E)=>{}')
        self.assertEqual(doc, before)
        self.assertEqual(result['definition']['parts'][1], before['definition']['parts'][1])
        with self.assertRaises(ValueError):
            prepare(result, uri, 'fixture', '(A,B,C,D,E)=>{}')

    def test_refuses_wrong_batch_url_and_source_contract(self):
        with self.assertRaises(ValueError):
            prepare(self.document(), 'https://example.sharepoint.com/award-crosswalk-other', 'fixture', 'x')
        doc = self.document(); doc['definition']['parts'][0]['payload'] = base64.b64encode(b'unknown partition').decode()
        with self.assertRaises(ValueError):
            prepare(doc, 'https://example.sharepoint.com/award-crosswalk-fixture', 'fixture', 'x')
