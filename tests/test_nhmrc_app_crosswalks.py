import sys
import unittest
import base64
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nhmrc_app_crosswalks import qualify_app
import nhmrc_app_crosswalks as app
from prepare_nhmrc_app_model import prepare


class ApplicationRepresentationTests(unittest.TestCase):
    authority = {'namespace': 'nhmrc', 'ror': 'fixture:nhmrc'}

    def record(self, **changes):
        return dict({'id': 'fixture', 'type': 'grant',
                     'purl': 'https://purl.org/au-research/grants/nhmrc/1092957',
                     'identifiers': ['1092957']}, **changes)

    def qualify(self, number='APP1092957', records=None, authority=None):
        return qualify_app(number, 'fixture:nhmrc', authority or self.authority,
                           [self.record()] if records is None else records)

    def test_original_preserved_and_application_field_used(self):
        result = self.qualify()
        self.assertEqual(result['original_identifier'], 'APP1092957')
        self.assertEqual(result['application_number'], '1092957')
        self.assertEqual(result['matches'][0]['record_id'], 'fixture')

    def test_no_whitespace_unicode_padding_or_other_prefix_conversion(self):
        for number in ['APP0109295', 'APP1092957 ', 'app1092957', 'APP 1092957',
                       'APP１０９２９５７', 'MRF1092957', 'GNT1092957', '1092957', None]:
            with self.subTest(number=number):
                self.assertEqual(self.qualify(number)['matches'], [])

    def test_administrator_is_not_funding_namespace(self):
        self.assertEqual(self.qualify(authority={'namespace': 'mrff',
                                                'ror': 'fixture:nhmrc'})['matches'], [])
        self.assertEqual(qualify_app('APP1092957', None,
                                    {'namespace': 'nhmrc'}, [self.record()])['matches'], [])

    def test_duplicate_exact_record_is_ambiguous(self):
        self.assertEqual(self.qualify(records=[self.record(), self.record(id='other')])['state'],
                         'ambiguous_award_identifier')

    def test_discovery_number_or_gnt_record_does_not_override_exact_identity(self):
        other = self.record(id='gnt', purl='https://purl.org/au-research/grants/nhmrc/GNT1092957',
                            identifiers=['GNT1092957'])
        nongrant = self.record(id='project', type='project')
        self.assertEqual(self.qualify(records=[other, nongrant])['state'], 'no_exact_identifier')
        self.assertEqual(self.qualify(records=[other, nongrant, self.record()])['matches'],
                         self.qualify()['matches'])

    def test_namespace_uri_and_identifier_must_all_agree(self):
        for changes in [dict(purl='https://purl.org/au-research/grants/mrff/1092957'),
                        dict(purl='https://purl.org/au-research/grants/nhmrc/1092957?x=1'),
                        dict(identifiers=['APP1092957'])]:
            self.assertEqual(self.qualify(records=[self.record(**changes)])['matches'], [])

    def test_institutional_path_requires_each_explicit_identifier_link(self):
        project_url = 'https://institution.example/projects/fixture/'
        publication = ('<meta name="citation_doi" content="10.1234/fixture">'
            '<table class="funders_informations_table"><tr><td>NHMRC National Health and Medical Research Council</td>'
            '<td>1092957</td></tr></table><a rel="UPMProject" href="' + project_url + '">Project</a>')
        uri = 'http://purl.org/au-research/grants/nhmrc/1092957'
        project = '<a href="' + uri + '">Grant</a>'
        check = lambda pub=publication, prj=project: app.institutional_application_uri(
            pub, prj, '10.1234/fixture', '1092957', project_url)
        self.assertEqual(check(), uri)
        for old, new in [('10.1234/fixture', '10.1234/other'), ('UPMProject', 'untyped'),
                         ('1092957', 'APP1092957'), ('NHMRC National Health and Medical Research Council', 'MRFF')]:
            self.assertIsNone(check(publication.replace(old, new)))
        self.assertIsNone(check(prj=project + project))

    def fixture(self, root):
        objects = {name: ('fictional ' + name).encode() for name in app.AUTHORITY_SHA256}
        objects.update({
            'authority-ror.json': json.dumps(dict(id='fixture:nhmrc', links=[dict(type='website', value='https://www.nhmrc.gov.au/')], external_ids=[dict(type='fundref', all=['1'])])).encode(),
            'crossref.json': json.dumps(dict(status='ok', message=dict(DOI='10.1234/fixture', funder=[dict(DOI='10.13039/1', award=['APP1092957'])]))).encode(),
            'ardc.json': json.dumps(dict(status='OK', code='200', data=dict(offset=0, numFound=1, records=[self.record()]))).encode()})
        files = []
        for name, data in objects.items():
            (root / name).write_bytes(data)
            files.append(dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        hashes = {f['name']: f['sha256'] for f in files}
        manifest = dict(kind='nhmrc_app_crosswalk_retention_v1', complete=True, namespace='nhmrc', batch='fixture', files=files,
            crossref=[dict(filename='crossref.json', doi='10.1234/fixture', sha256=hashes['crossref.json'], url='https://api.crossref.org/works/10.1234/fixture', observed_utc='2026-10-21T00:00:00Z')],
            ardc=[dict(filename='ardc.json', original_identifier='APP1092957', sha256=hashes['ardc.json'], complete=True, url='https://researchdata.edu.au/api/v2.0/registry/activities?identifier=1092957')])
        policy = dict(rule=app.RULE_ID, guide_page=21, source_files=copy.deepcopy(files), crossref=manifest['crossref'], ardc=manifest['ardc'])
        data = json.dumps(policy).encode(); (root / 'rule-authority.json').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest();files.append(dict(name='rule-authority.json', bytes=len(data), sha256=digest))
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return manifest, digest, {name: hashes[name] for name in app.AUTHORITY_SHA256}

    def test_packet_binds_originals_queries_and_canonical_ambiguity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest, pin, authorities = self.fixture(root)
            pubs = [dict(DOI='10.1234/fixture', CanonicalKey='fixture:1')]
            with patch.object(app, 'AUTHORITY_SHA256', authorities):
                rows = app.project_packet(root, pubs, pin)
                self.assertEqual(rows[0]['ToLabel'], 'APP1092957')
                self.assertEqual(rows[0]['AdmissionState'], 'Source-supported')
                ambiguous = app.project_packet(root, pubs + [dict(DOI='10.1234/fixture', CanonicalKey='fixture:2')], pin)
                self.assertEqual(ambiguous[0]['AdmissionState'], 'Ambiguous DOI')
                # A reconstructed outer manifest cannot replace pinned query provenance.
                manifest['crossref'][0]['observed_utc'] = '2099-01-01T00:00:00Z'
                (root / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'catalogue drift'):
                    app.project_packet(root, pubs, pin)

    def test_packet_rejects_rehashed_source_substitution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest, pin, authorities = self.fixture(root)
            data = (root / 'crossref.json').read_bytes().replace(b'APP1092957', b'APP1192957')
            (root / 'crossref.json').write_bytes(data)
            entry = next(f for f in manifest['files'] if f['name'] == 'crossref.json')
            entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            manifest['crossref'][0]['sha256'] = entry['sha256']
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with patch.object(app, 'AUTHORITY_SHA256', authorities):
                with self.assertRaises(ValueError):
                    app.project_packet(root, [], pin)

    def test_model_preparation_changes_only_current_evidence_expression(self):
        text = ('table SourceRelationshipEvidence\n\tpartition SourceRelationshipEvidence = m\n'
                '\t\tsource =\n\t\t\tlet StudySite="https://example.sharepoint.com/sites/dev",\n'
                '\t\t\tReadStudy=()=>null,\n'
                '\t\t\tRows=Table.Buffer(Table.FromRecords(BeforeGNT & GNTEvidence,Columns,MissingField.Error))\n'
                '\t\t\tin Rows')
        doc = dict(definition=dict(parts=[dict(path='definition/tables/SourceRelationshipEvidence.tmdl', payload=base64.b64encode(text.encode()).decode()),
                                         dict(path='definition/model.tmdl', payload='unchanged')]))
        batch = '00000000-0000-4000-8000-000000000001'
        candidate = prepare(doc, 'https://example.sharepoint.com/sites/dev/Documents/award-crosswalk-' + batch,
                            batch, '(R,A,B,H)=>{}', 'a' * 64)
        self.assertEqual(candidate['definition']['parts'][1], doc['definition']['parts'][1])
        decoded = base64.b64decode(candidate['definition']['parts'][0]['payload']).decode()
        self.assertIn('BeforeAPP=List.Buffer(BeforeGNT & GNTEvidence)', decoded)
        self.assertNotIn('APPProjector=', text)
        with self.assertRaises(ValueError):
            prepare(candidate, 'https://example.sharepoint.com/sites/dev/Documents/award-crosswalk-' + batch,
                    batch, '(R,A,B,H)=>{}', 'a' * 64)
