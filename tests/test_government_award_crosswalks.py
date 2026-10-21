import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from government_award_crosswalks import project_packet


class GovernmentCrosswalkTests(unittest.TestCase):
    def fixture(self, folder, duplicate=False):
        root = Path(folder)
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = 'GRANTS DATA'
        sheet.append(['APP ID', 'Grant Title'])
        sheet.append([1234567, 'Fictional historical award'])
        if duplicate:
            sheet.append([1234567, 'Conflicting historical award'])
        workbook.save(root / 'historical.xlsx')
        workbook.close()
        url = 'https://www.nhmrc.gov.au/sites/default/files/fictional.xlsx'
        source = dict(format='rims-funding-native-workbook-commit-v1', source='nhmrc', complete=True,
                      fidelity='original_binary_content_exact_saved_readback',
                      files=[dict(name='historical.xlsx', source_url=url)])
        authority = dict(id='https://ror.org/fictional', links=[dict(type='website', value='https://www.nhmrc.gov.au/')],
                         external_ids=[dict(type='fundref', all=['501100000925'])])
        crossref = dict(status='ok', message={'DOI': '10.1234/fictional',
                            'funder': [{'DOI': '10.13039/501100000925', 'award': ['1234567']}]})
        for name, value in [('source.json', source), ('authority.json', authority), ('crossref.json', crossref)]:
            (root / name).write_text(json.dumps(value))
        files = [dict(name=p.name, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(root.iterdir())]
        by_name = {r['name']: r for r in files}
        manifest = dict(kind='historical_nhmrc_crossref_retention_v1', namespace='nhmrc', batch='fixture',
                        complete=True, files=files, authority=by_name['authority.json'],
                        source_manifest=by_name['source.json'],
                        workbook=dict(by_name['historical.xlsx'], source_url=url, sheet='GRANTS DATA', id_column='APP ID'),
                        crossref=[dict(by_name['crossref.json'], doi='10.1234/fictional',
                                       url='https://api.crossref.org/works/10.1234/fictional', observed_utc='2026-01-01T00:00:00Z')])
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return root

    def replace(self, root, filename, value):
        (root / filename).write_text(json.dumps(value))
        manifest = json.loads((root / 'manifest.json').read_text())
        data = (root / filename).read_bytes()
        def visit(v):
            if isinstance(v, dict):
                if v.get('name') == filename:
                    v.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                for x in v.values():
                    visit(x)
            elif isinstance(v, list):
                for x in v:
                    visit(x)
        visit(manifest)
        (root / 'manifest.json').write_text(json.dumps(manifest))

    def test_exact_funding_number_retains_coordinate_and_separate_historical_semantics(self):
        with tempfile.TemporaryDirectory() as d:
            rows = project_packet(self.fixture(d))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['ToKey'], 'nhmrc:1234567')
            self.assertEqual(row['RelationshipKind'], 'publication_government_award_reference')
            self.assertEqual(row['ReviewState'], 'Not reviewed')
            proof = json.loads(row['ReferenceType'])
            self.assertEqual(proof['workbookRow'], 2)
            self.assertEqual(proof['identifierColumn'], 'APP ID')
            self.assertNotIn('purl.org', json.dumps(rows))

    def test_prefixes_and_other_funder_namespaces_are_not_joined(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            doc = json.loads((root / 'crossref.json').read_bytes())
            doc['message']['funder'] = [dict(DOI='10.13039/501100000925', award=['APP1234567', 'GNT1234567']),
                                         dict(DOI='10.13039/999999', award=['1234567'])]
            self.replace(root, 'crossref.json', doc)
            self.assertEqual(project_packet(root), [])

    def test_duplicate_government_identifier_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'Ambiguous historical'):
                project_packet(self.fixture(d, duplicate=True))

    def test_source_hash_and_official_source_manifest_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            data = (root / 'historical.xlsx').read_bytes()
            (root / 'historical.xlsx').write_bytes(data + b'drift')
            with self.assertRaisesRegex(ValueError, 'hash or length drift'):
                project_packet(root)
            (root / 'historical.xlsx').write_bytes(data)
            source = json.loads((root / 'source.json').read_text())
            source['source'] = 'mrff'
            self.replace(root, 'source.json', source)
            with self.assertRaisesRegex(ValueError, 'official NHMRC'):
                project_packet(root)

    def test_crossref_work_identity_and_independent_namespace_authority_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            doc = json.loads((root / 'crossref.json').read_text())
            doc['message']['DOI'] = '10.1234/other'
            self.replace(root, 'crossref.json', doc)
            with self.assertRaisesRegex(ValueError, 'Crossref publication identity'):
                project_packet(root)

