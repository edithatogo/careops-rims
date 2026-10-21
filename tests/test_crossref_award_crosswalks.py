import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from crossref_award_crosswalks import project_packet


class CrossrefAwardCrosswalkTests(unittest.TestCase):
    def fixture(self, directory, number='123', funder='10.13039/1', duplicate=False):
        root = Path(directory)
        funding = {'DOI': funder, 'award': [number] * (2 if duplicate else 1)}
        crossref = {'status': 'ok', 'message': {'DOI': '10.1234/test', 'funder': [funding]}}
        ardc = {'status': 'OK', 'code': '200', 'data': {'offset': 0, 'numFound': 1, 'records': [
            {'type': 'grant', 'id': 'fixture-grant', 'purl': 'https://purl.org/au-research/grants/nhmrc/123', 'identifiers': ['123']}]}}
        authority = {'id': 'https://ror.org/fixture', 'links': [{'type': 'website', 'value': 'https://www.nhmrc.gov.au/'}],
                     'external_ids': [{'type': 'fundref', 'all': ['1']}]}
        files = []
        for name, value in [('crossref.json', crossref), ('ardc.json', ardc), ('authority.json', authority)]:
            raw = json.dumps(value).encode(); (root / name).write_bytes(raw)
            files.append({'name': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        manifest = {'kind': 'publication_award_crosswalk_retention_v1', 'batch': 'fixture-batch', 'namespace': 'nhmrc', 'complete': True,
            'files': files, 'authority': files[2],
            'crossref': [{'filename': 'crossref.json', 'doi': '10.1234/test', 'url': 'https://api.crossref.org/works/10.1234/test',
                          'observed_utc': '2026-10-21T00:00:00Z', 'sha256': files[0]['sha256']}],
            'ardc': [{'filename': 'ardc.json', 'original_identifier': number, 'complete': True,
                      'sha256': files[1]['sha256'], 'url': 'https://researchdata.edu.au/api/v2.0/registry/activities?identifier=' + number}]}
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return root

    def test_typed_identifier_edge_deduplicates_and_retains_both_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d, duplicate=True)
            rows = project_packet(root, [{'DOI': '10.1234/test', 'CanonicalKey': 'fixture:publication'}])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['CanonicalKey'], 'fixture:publication')
            self.assertEqual(rows[0]['ReviewState'], 'Not reviewed')
            self.assertEqual(rows[0]['AuthenticationState'], 'Not authenticated')
            self.assertIn('ardcRawSHA256', json.loads(rows[0]['ReferenceType']))

    def test_funder_collision_not_admitted(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(project_packet(self.fixture(d, funder='10.13039/2'), []), [])

    def test_prefix_variant_not_silently_normalized(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(project_packet(self.fixture(d, number='APP123'), []), [])

    def test_ambiguous_canonical_assignment_retained_unadmitted(self):
        with tempfile.TemporaryDirectory() as d:
            rows = project_packet(self.fixture(d), [{'DOI': '10.1234/test', 'CanonicalKey': k} for k in ['fixture:a', 'fixture:b']])
            self.assertEqual(rows[0]['AdmissionState'], 'Ambiguous DOI')
            self.assertEqual(rows[0]['CanonicalKey'], '')

    def test_raw_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d); (root / 'crossref.json').write_text('{}')
            with self.assertRaises(ValueError):
                project_packet(root, [])

    def test_provenance_hash_cannot_differ_from_verified_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['crossref'][0]['sha256'] = '0' * 64
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                project_packet(root, [])

    def test_authority_provenance_hash_must_match_verified_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['authority']['sha256'] = '0' * 64
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Authority provenance hash drift'):
                project_packet(root, [])
