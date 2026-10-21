import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from protocol_study_award_evidence import project_packet
from qualify_protocol_award_metadata import parse_cover

COVER = '''Clinical trials registration NCT00000001
Protocol version/date Version 1.0, dated 1 January 2026
Protocol number CT12345
Funding source Australia:
 NHMRC 2021 Clinical Trials and Cohort Studies
 (Application ID 1234567)
'''

class ProtocolStudyAwardTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        payloads = {'protocol.pdf': b'%PDF-fictional-fixture', 'protocol-page1.txt': COVER.encode(),
            'protocol-facts.json': json.dumps(parse_cover(COVER)).encode(),
            'study-source-envelope.json': json.dumps({'requested_id': 'NCT00000001', 'response': {'statusCode': 200, 'body': {
                'protocolSection': {'identificationModule': {'nctId': 'NCT00000001', 'orgStudyIdInfo': {'id': 'CT12345'}}}}}}).encode(),
            'authority-ror.json': json.dumps({'id': 'https://ror.org/fixture', 'links': [{'type': 'website', 'value': 'https://www.nhmrc.gov.au/'}]}).encode(),
            'ardc-grant.json': json.dumps({'status': 'OK', 'code': '200', 'data': {'offset': 0, 'numFound': 1, 'records': [
                {'type': 'grant', 'id': 'fixture-grant', 'purl': 'https://purl.org/au-research/grants/nhmrc/1234567', 'identifiers': ['1234567']}]}}).encode()}
        files = []
        for name, raw in payloads.items():
            (root / name).write_bytes(raw)
            files.append({'name': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        (root / 'manifest.json').write_text(json.dumps({'kind': 'protocol_study_award_retention_v1', 'batch': 'fixture', 'complete': True,
            'protocol_source_url': 'https://example.invalid/protocol.pdf', 'observed_utc': '2026-10-21T00:00:00Z', 'files': files}))
        studies = [{'SourceKey': 'clinicaltrials.gov:NCT00000001', 'NCTId': 'NCT00000001', 'SourcePayloadSHA256': hashlib.sha256(payloads['study-source-envelope.json']).hexdigest()}]
        refs = [{'RelationshipKind': 'publication_study_reference', 'ToKey': 'clinicaltrials.gov:NCT00000001',
                 'PublicationPMID': '123', 'SourceWorkID': 'pubmed:123', 'RawSHA256': '', 'SourceVersion': 'fixture-source', 'ReferenceType': 'PubMed DataBankList'}]
        return root, studies, refs

    def test_explicit_source_edge_and_chain_keep_assurance_and_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d); before = copy.deepcopy((studies, refs))
            rows = project_packet(root, studies, refs)
            self.assertEqual([r['RelationshipKind'] for r in rows], ['study_award_reference', 'publication_study_award_chain'])
            self.assertTrue(all(r['ReviewState'] == 'Not reviewed' and r['AuthenticationState'] == 'Not authenticated' for r in rows))
            self.assertEqual((studies, refs), before)

    def test_existing_study_identity_drift_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d); studies[0]['NCTId'] = 'NCT00000002'
            with self.assertRaises(ValueError):
                project_packet(root, studies, refs)

    def test_background_or_other_relationship_not_used_as_publication_edge(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d); refs[0]['RelationshipKind'] = 'background_reference'
            self.assertEqual(len(project_packet(root, studies, refs)), 1)

    def test_missing_publication_identity_does_not_invent_chain(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d); refs[0]['PublicationPMID'] = ''
            self.assertEqual(len(project_packet(root, studies, refs)), 1)

    def test_modified_protocol_metadata_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d); (root / 'protocol-facts.json').write_text('{}')
            with self.assertRaises(ValueError):
                project_packet(root, studies, refs)

    def test_routine_study_update_preserves_historical_qualification(self):
        with tempfile.TemporaryDirectory() as d:
            root, studies, refs = self.fixture(d)
            original = studies[0]['SourcePayloadSHA256']
            studies[0]['SourcePayloadSHA256'] = '1' * 64
            rows = project_packet(root, studies, refs)
            proof = json.loads(rows[0]['ReferenceType'])
            self.assertEqual(proof['studySourceRawSHA256'], original)
            self.assertEqual(proof['studyRegisterSourceSHA256'], '1' * 64)
            self.assertEqual(len(rows), 2)
