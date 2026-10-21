import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from registry_publication_crosswalks import project_packet


class RegistryPublicationTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        xml = '''<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
          <GetRecord><record><header><identifier>oai:ands.org.au::1</identifier><datestamp>2026-01-01</datestamp></header>
          <metadata><registryObjects xmlns="http://ands.org.au/standards/rif-cs/registryObjects"><registryObject>
          <activity type="grant"><identifier type="nhmrc">1234567</identifier>
          <relatedObject><key>https://doi.org/10.13039/12345</key><relation type="isFundedBy"/></relatedObject>
          <relatedInfo type="publication"><identifier type="URI">http://hdl.handle.net/1234/56</identifier></relatedInfo>
          </activity></registryObject></registryObjects></metadata></record></GetRecord></OAI-PMH>'''
        payloads = {
            'authority.json': dict(id='https://ror.org/fixture', links=[dict(type='website', value='https://www.nhmrc.gov.au/')],
                                   external_ids=[dict(type='fundref', all=['12345'])]),
            'ardc.json': dict(status='OK', code='200', data=dict(offset=0, numFound=1, records=[dict(type='grant',
                purl='https://purl.org/au-research/grants/nhmrc/1234567', identifiers=['1234567'])])),
            'item.json': dict(type='item', id='fixture-item', handle='1234/56',
                              metadata={'dc.identifier.doi': [dict(value='https://doi.org/10.1234/fixture')]}),
            'rifcs.xml': xml}
        files = []
        for name, value in payloads.items():
            raw = value.encode() if isinstance(value, str) else json.dumps(value).encode()
            (root / name).write_bytes(raw)
            files.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        manifest = dict(kind='ardc_publication_handle_retention_v1', namespace='nhmrc', complete=True,
            batch='fixture', qualified_utc='2026-01-02T00:00:00Z', files=files, authority=files[0],
            grants=[dict(record_id='1', original_identifier='1234567',
                         grant_uri='https://purl.org/au-research/grants/nhmrc/1234567',
                         ardc_name='ardc.json', rifcs_name='rifcs.xml', rifcs_url='https://example.invalid/oai')],
            publications=[dict(record_id='1', name='item.json', publication_uri='http://hdl.handle.net/1234/56',
                               handle='1234/56', item_id='fixture-item', final_url='https://example.invalid/api/item')])
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return root

    def replace(self, root, name, value):
        raw = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        (root / name).write_bytes(raw)
        manifest = json.loads((root / 'manifest.json').read_text())
        entry = next(r for r in manifest['files'] if r['name'] == name)
        entry.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        (root / 'manifest.json').write_text(json.dumps(manifest))

    def test_related_publication_is_not_promoted_to_funding_or_review(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            rows = project_packet(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['RelationshipKind'], 'grant_related_publication')
            self.assertEqual(rows[0]['ReviewState'], 'Not reviewed')
            self.assertEqual(rows[0]['AuthenticationState'], 'Not authenticated')
            self.assertEqual(json.loads(rows[0]['ReferenceType'])['relationship'], 'RIF-CS relatedInfo publication')

    def test_title_similarity_cannot_replace_explicit_handle(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            xml = (root / 'rifcs.xml').read_text().replace('<identifier type="URI">http://hdl.handle.net/1234/56</identifier>',
                                                          '<title>http://hdl.handle.net/1234/56</title>')
            self.replace(root, 'rifcs.xml', xml)
            with self.assertRaisesRegex(ValueError, 'Exact typed publication handle'):
                project_packet(root)

    def test_unrelated_info_is_not_a_publication_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            self.replace(root, 'rifcs.xml', (root / 'rifcs.xml').read_text().replace('relatedInfo type="publication"', 'relatedInfo type="website"'))
            with self.assertRaises(ValueError):
                project_packet(root)

    def test_resolved_handle_identity_drift_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            item = json.loads((root / 'item.json').read_text()); item['handle'] = '1234/57'
            self.replace(root, 'item.json', item)
            with self.assertRaisesRegex(ValueError, 'repository identity drift'):
                project_packet(root)

    def test_ambiguous_or_missing_explicit_doi_is_refused(self):
        for values in ([], [dict(value='10.1234/fixture'), dict(value='10.1234/other')]):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as d:
                root = self.fixture(d)
                item = json.loads((root / 'item.json').read_text()); item['metadata'] = {'dc.identifier.doi': values}
                self.replace(root, 'item.json', item)
                with self.assertRaisesRegex(ValueError, 'One explicit repository DOI'):
                    project_packet(root)

    def test_grant_funder_namespace_cannot_be_inferred_from_names(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            self.replace(root, 'rifcs.xml', (root / 'rifcs.xml').read_text().replace('10.13039/12345', '10.13039/99999'))
            with self.assertRaisesRegex(ValueError, 'grant funder namespace'):
                project_packet(root)

    def test_changed_raw_source_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d); (root / 'item.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'byte/hash drift'):
                project_packet(root)

    def test_duplicate_qualified_manifest_mapping_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['publications'] *= 2
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Duplicate registry publication mapping'):
                project_packet(root)

    def test_figshare_published_in_relation_does_not_become_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['publications'][0].update(metadata_kind='figshare', item_id='123')
            (root / 'manifest.json').write_text(json.dumps(manifest))
            item = dict(id=123, handle='1234/56', is_public=True, is_confidential=False,
                defined_type_name='journal contribution', related_materials=[dict(identifier_type='DOI',
                relation='IsPublishedIn', identifier='10.1234/parent')])
            self.replace(root, 'item.json', item)
            row = project_packet(root)[0]
            self.assertEqual(row['PublicationDOI'], '')
            self.assertEqual(row['FromKey'], 'handle:1234/56')
            self.assertEqual(json.loads(row['ReferenceType'])['repositoryRelatedMaterials'], item['related_materials'])

    def test_figshare_identity_requires_public_exact_handle_and_article_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['publications'][0].update(metadata_kind='figshare', item_id='123')
            (root / 'manifest.json').write_text(json.dumps(manifest))
            item = dict(id=123, handle='1234/57', is_public=True, is_confidential=False,
                        defined_type_name='journal contribution', related_materials=[])
            self.replace(root, 'item.json', item)
            with self.assertRaisesRegex(ValueError, 'repository identity drift'):
                project_packet(root)

    def test_oai_root_identity_cannot_be_replaced_by_unrelated_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            xml = (root / 'rifcs.xml').read_text().replace('<OAI-PMH ', '<unrelated ').replace('</OAI-PMH>', '</unrelated>')
            self.replace(root, 'rifcs.xml', xml)
            with self.assertRaisesRegex(ValueError, 'successful OAI record'):
                project_packet(root)
