import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from award_identifier_crosswalks import qualify_award_alias


class AwardIdentifierCrosswalkTests(unittest.TestCase):
    authority = {'ror': 'https://ror.org/fixture', 'namespace': 'fixture'}

    def record(self, number='123', record_id='1'):
        return {'type': 'grant', 'id': record_id,
                'purl': 'https://purl.org/au-research/grants/fixture/' + number,
                'identifiers': [number]}

    def qualify(self, records, ror='https://ror.org/fixture'):
        return qualify_award_alias({'funder_award_id': '123'}, ror,
                                   self.authority, records)

    def test_exact_namespace_and_identifier_admitted(self):
        self.assertEqual(self.qualify([self.record()])['state'], 'source_supported_alias')

    def test_number_collision_different_funder_rejected(self):
        self.assertEqual(self.qualify([self.record()], 'https://ror.org/other')['state'],
                         'unqualified_funder_namespace')

    def test_prefix_variants_and_title_similarity_do_not_establish_alias(self):
        record = self.record('GNT123')
        record['title'] = 'Same title'
        self.assertEqual(self.qualify([record])['state'], 'no_exact_identifier')

    def test_two_distinct_records_are_ambiguous(self):
        self.assertEqual(self.qualify([self.record(), self.record(record_id='2')])['state'],
                         'ambiguous_award_identifier')

    def test_search_result_without_explicit_identifier_rejected(self):
        record = self.record()
        record['identifiers'] = []
        self.assertEqual(self.qualify([record])['state'], 'no_exact_identifier')

    def test_untrusted_purl_host_rejected(self):
        record = self.record()
        record['purl'] = record['purl'].replace('purl.org', 'purl.org.invalid')
        self.assertEqual(self.qualify([record])['state'], 'no_exact_identifier')

    def test_alternate_ports_are_not_exact_grant_uris(self):
        for host in ['purl.org:443', 'purl.org:8443']:
            with self.subTest(host=host):
                record = self.record()
                record['purl'] = record['purl'].replace('purl.org', host)
                self.assertEqual(self.qualify([record])['state'], 'no_exact_identifier')
