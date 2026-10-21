import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nhmrc_gnt_crosswalks as gnt
from prepare_nhmrc_gnt_model import prepare


class GNTRuleTests(unittest.TestCase):
    authority = {'namespace': 'nhmrc', 'ror': 'fixture:nhmrc'}

    def record(self, bare='1196396', **updates):
        return dict(type='grant', id='fixture', purl='https://purl.org/au-research/grants/nhmrc/' + bare,
                    identifiers=[bare], startDate=2020, endDate=2023, **updates)

    def qualify(self, number='GNT1196396', records=None, ror='fixture:nhmrc'):
        return gnt.qualify_gnt(number, ror, self.authority, records if records is not None else [self.record()])

    def test_explicit_code_and_six_digit_padding(self):
        self.assertEqual(self.qualify()['grant_number'], '1196396')
        self.assertEqual(self.qualify('GNT0123456', [self.record('123456')])['grant_number'], '123456')

    def test_other_namespaces_and_malformed_codes_rejected(self):
        for n in ['APP1196396', 'MRF1196396', 'gnt1196396', 'GNT 1196396', 'GNT1196396 ', 'GNT123456', 'GNT0012345', 'GNT１２３４５６７', '']:
            with self.subTest(n=n):
                self.assertEqual(self.qualify(n)['matches'], [])
        self.assertEqual(self.qualify(ror='fixture:other')['matches'], [])

    def test_unknown_or_boundary_years_do_not_establish_rgms_scope(self):
        for start, end in [(2021, 2023), (2020, 2021), (None, 2023), (2020, None), ('2020', 2023), (True, 2023)]:
            r = self.record(); r.update(startDate=start, endDate=end)
            self.assertEqual(self.qualify(records=[r])['state'], 'historical_scope_unproved')

    def test_duplicate_or_wrong_uri_remains_unresolved(self):
        r = self.record()
        self.assertEqual(self.qualify(records=[r, {**r, 'id': 'other'}])['state'], 'ambiguous_award_identifier')
        for uri in ['http://purl.org/au-research/grants/nhmrc/1196396', 'https://purl.org:443/au-research/grants/nhmrc/1196396', r['purl'] + '?x=1']:
            self.assertEqual(self.qualify(records=[{**r, 'purl': uri}])['matches'], [])

    def fixture(self, root):
        guide = b'fictional guide'; digest = hashlib.sha256(guide).hexdigest()
        migration = b'fictional migration readback'
        policy = dict(rule=gnt.RULE_ID, guide_url=gnt.GUIDE_URL, guide_sha256=digest, guide_page=43,
                      migration_url=gnt.MIGRATION_URL, migration_sha256=hashlib.sha256(migration).hexdigest())
        authority = dict(id='fixture:nhmrc', links=[dict(type='website', value='https://www.nhmrc.gov.au/')], external_ids=[dict(type='fundref', all=['1'])])
        objects = {'guide.pdf': guide, 'migration-web-readback.json': migration,
            'rule-authority.json': json.dumps(policy).encode(), 'authority-ror.json': json.dumps(authority).encode(),
            'crossref.json': json.dumps(dict(status='ok', message=dict(DOI='10.1234/test', funder=[dict(DOI='10.13039/1', award=['GNT1196396'])]))).encode(),
            'ardc.json': json.dumps(dict(status='OK', code='200', data=dict(offset=0, numFound=1, records=[self.record()]))).encode()}
        files = []
        for name, b in objects.items():
            (root / name).write_bytes(b); files.append(dict(name=name, bytes=len(b), sha256=hashlib.sha256(b).hexdigest()))
        hashes = {f['name']: f['sha256'] for f in files}
        m = dict(kind='nhmrc_gnt_crosswalk_retention_v1', namespace='nhmrc', complete=True, batch='fixture', files=files,
            crossref=[dict(filename='crossref.json', doi='10.1234/test', sha256=hashes['crossref.json'], url='https://api.crossref.org/works/10.1234/test', observed_utc='2026-10-21T00:00:00Z')],
            ardc=[dict(filename='ardc.json', original_identifier='GNT1196396', sha256=hashes['ardc.json'], complete=True, url='https://researchdata.edu.au/api/v2.0/registry/activities?identifier=1196396')])
        policy.update(source_files=[f for f in files if f['name'] != 'rule-authority.json'],
                      crossref=m['crossref'], ardc=m['ardc'])
        b = json.dumps(policy).encode(); (root / 'rule-authority.json').write_bytes(b)
        for f in files:
            if f['name'] == 'rule-authority.json':
                f.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
        hashes['rule-authority.json'] = hashlib.sha256(b).hexdigest()
        (root / 'manifest.json').write_text(json.dumps(m))
        return digest, hashes['rule-authority.json']

    def test_packet_derivation_preserves_original_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); guide, pin = self.fixture(root)
            with patch.object(gnt, 'GUIDE_SHA256', guide):
                rows = gnt.project_packet(root, [{'DOI': '10.1234/test', 'CanonicalKey': 'fixture:p'}], pin, expected_batch='fixture')
                self.assertEqual(rows[0]['ToLabel'], 'GNT1196396')
                self.assertTrue(rows[0]['ToKey'].endswith('/1196396'))
                self.assertEqual(rows[0]['AdmissionState'], 'Source-supported')
                self.assertEqual(json.loads(rows[0]['ReferenceType'])['ruleAuthoritySHA256'], pin)
                rows = gnt.project_packet(root, [{'DOI': '10.1234/test', 'CanonicalKey': k} for k in ['a', 'b']], pin, expected_batch='fixture')
                self.assertEqual(rows[0]['AdmissionState'], 'Ambiguous DOI')
                self.assertEqual(rows[0]['CanonicalKey'], '')

    def test_packet_tamper_and_wrong_external_pin_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); guide, pin = self.fixture(root)
            with patch.object(gnt, 'GUIDE_SHA256', guide):
                with self.assertRaisesRegex(ValueError, 'External rule'):
                    gnt.project_packet(root, [], '0' * 64, expected_batch='fixture')
                (root / 'guide.pdf').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'hash or length'):
                    gnt.project_packet(root, [], pin, expected_batch='fixture')

    def test_recomputed_outer_hash_cannot_replace_pinned_primary_guide(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); guide, pin = self.fixture(root)
            replacement = b'a replacement guide'
            (root / 'guide.pdf').write_bytes(replacement)
            m = json.loads((root / 'manifest.json').read_text())
            for f in m['files']:
                if f['name'] == 'guide.pdf':
                    f.update(bytes=len(replacement), sha256=hashlib.sha256(replacement).hexdigest())
            (root / 'manifest.json').write_text(json.dumps(m))
            with patch.object(gnt, 'GUIDE_SHA256', guide):
                with self.assertRaisesRegex(ValueError, 'pinned source identity'):
                    gnt.project_packet(root, [], pin, expected_batch='fixture')

    def test_recomputed_packet_cannot_replace_funding_assertion_or_observation_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); guide, pin = self.fixture(root)
            m = json.loads((root / 'manifest.json').read_text())
            m['crossref'][0]['observed_utc'] = '2099-01-01T00:00:00Z'
            (root / 'manifest.json').write_text(json.dumps(m))
            with patch.object(gnt, 'GUIDE_SHA256', guide):
                with self.assertRaisesRegex(ValueError, 'source catalogue'):
                    gnt.project_packet(root, [], pin, expected_batch='fixture')

    def test_outer_batch_cannot_relabel_pinned_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guide, pin = self.fixture(root)
            manifest = json.loads((root / 'manifest.json').read_bytes())
            manifest['batch'] = 'relabeled'
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'batch identity'):
                gnt.project_packet(root, [], pin, expected_batch='fixture')

    def test_model_preparer_preserves_all_prior_source_and_rejects_other_site(self):
        batch = '00000000-0000-4000-8000-000000000001'; site = 'https://example.sharepoint.com/sites/a'
        marker = 'Rows=Table.Buffer(Table.FromRecords(BeforeGovernment & GovernmentAwardEvidence,Columns,MissingField.Error))'
        text = 'StudySite="' + site + '",\nReadStudy=fixture,\n' + marker
        doc = {'definition': {'parts': [{'path': 'definition/tables/SourceRelationshipEvidence.tmdl', 'payload': base64.b64encode(text.encode()).decode()}, {'path': 'other', 'payload': 'unchanged'}]}}
        before = copy.deepcopy(doc); url = site + '/Documents/award-crosswalk-' + batch
        prepared = prepare(doc, url, batch, '(a,b,c,d)=>{}', 'a' * 64)
        self.assertEqual(doc, before)
        self.assertEqual(prepared['definition']['parts'][1], doc['definition']['parts'][1])
        after = base64.b64decode(prepared['definition']['parts'][0]['payload']).decode()
        self.assertTrue(after.startswith(text.split(marker)[0]))
        with self.assertRaises(ValueError):
            prepare(prepared, url, batch, '(a,b,c,d)=>{}', 'a' * 64)
        with self.assertRaisesRegex(ValueError, 'bound study'):
            prepare(doc, url.replace('/sites/a/', '/sites/b/'), batch, '(a,b,c,d)=>{}', 'a' * 64)

    def test_same_id_nonmatching_record_cannot_supply_dates(self):
        wrong = self.record()
        wrong.update(purl='https://purl.org/au-research/grants/nhmrc/9999999')
        exact = self.record(); exact.update(startDate=2021)
        for records in [[wrong, exact], [exact, wrong]]:
            self.assertEqual(self.qualify(records=records)['state'], 'historical_scope_unproved')
        wrong.update(startDate=2021); exact.update(startDate=2020)
        for records in [[wrong, exact], [exact, wrong]]:
            self.assertEqual(self.qualify(records=records)['state'], 'source_supported_alias')

    def test_absent_funder_identity_cannot_qualify_by_equal_empty_values(self):
        for missing in [None, '', '   ']:
            with self.subTest(missing=missing):
                result = gnt.qualify_gnt('GNT1196396', missing,
                                        {'namespace': 'nhmrc', 'ror': missing}, [self.record()])
                self.assertEqual(result['state'], 'unqualified_funder_namespace')
