import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publication_registry import Registry


def record(source='pubmed', key='1', doi='10.1234/test', pmid='1'):
    return {'source': source, 'source_record_id': key, 'pmid': pmid, 'doi': doi,
            'title': 'A publication', 'journal': 'Journal',
            'authors': [{'name': 'A Author', 'affiliations': ['Cairns Hospital']}],
            'publication_date_parts': {'Year': '2024'},
            'url': 'https://pubmed.ncbi.nlm.nih.gov/1/' if source == 'pubmed' else 'https://dora.health.qld.gov.au/item/1'}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Registry(self.root / 'registry.sqlite', data_kind='synthetic')
        self.addCleanup(self.db.close)

    def ingest(self, rows, run='r1', source='pubmed', kind='baseline'):
        return self.db.ingest(rows, run, source, '2026-01-01T00:00:00+00:00', kind)

    def test_rerun_preserves_identity_first_seen_and_exclusion(self):
        key = self.ingest([record()])[0]
        self.db.review(key, 'excluded', 'Outside scope', 'reviewer', '2026-01-02T00:00:00+00:00')
        self.assertEqual(self.ingest([record()], 'r2'), [key])
        row = self.db.records()[0]
        self.assertEqual(row['CanonicalKey'], key)
        self.assertEqual(row['ReviewStatus'], 'excluded')
        self.assertEqual(row['FirstObservedAt'], '2026-01-01T00:00:00+00:00')

    def test_source_only_enrichment_preserves_alias(self):
        original = self.ingest([record()])[0]
        dora = record('dora', 'd1', None, None)
        old = self.ingest([dora], 'r2', 'dora')[0]
        dora['pmid'] = '1'
        self.assertEqual(self.ingest([dora], 'r3', 'dora'), [original])
        self.assertEqual(len(self.db.records()), 1)
        alias = self.db.db.execute('SELECT canonical_id FROM publication_alias WHERE old_id=?', (old,)).fetchone()[0]
        self.assertEqual(alias, original)

    def test_exclusion_stays_in_audit_but_not_bibliography(self):
        key = self.ingest([record()])[0]
        self.db.review(key, 'excluded', 'Publisher confirmed duplicate', 'reviewer', '2026-01-02T00:00:00Z')
        folder = self.db.stage(self.root, 'excluded', {'pubmed': 'test'})
        self.assertEqual(json.loads((folder / 'all-publications.json').read_text())['records'], [])
        self.assertEqual(len(json.loads((folder / 'registry-metadata.json').read_text())), 1)

    def test_structured_attribution_exports_without_inventing_authors(self):
        key = self.ingest([record()])[0]
        self.db.record_attribution(key, ['A Author'], ['Cairns Hospital'], ['Cairns Hospital'])
        row = self.db.records()[0]
        self.assertEqual(row['CHHHSAffiliatedAuthors'], 'A Author')
        self.assertEqual(row['MatchedFacilities'], 'Cairns Hospital')
        with self.assertRaises(ValueError):
            self.db.record_attribution(key, [], [], [])

    def test_reviewed_merge_retains_history_and_refuses_unexplained_conflict(self):
        target = self.ingest([record()])[0]
        donor = self.ingest([record('dora', 'd1', '10.1234/wrong', None)], 'r2', 'dora')[0]
        proof = [{'source': 'archived-citation', 'sha256': 'a' * 64}]
        self.db.review(donor, 'needs_review', 'Identifier mismatch', 'reviewer', '2026-01-02T00:00:00Z')
        with self.assertRaises(ValueError):
            self.db.resolve_identity(donor, target, proof, 'Verified citation', 'reviewer', '2026-01-03T00:00:00Z')
        self.assertEqual(len(self.db.records()), 2)
        self.db.resolve_identity(donor, target, proof, 'Verified citation', 'reviewer', '2026-01-03T00:00:00Z', {'doi': {'old': '10.1234/wrong', 'new': '10.1234/test'}})
        self.assertEqual(len(self.db.records()), 1)
        self.assertEqual(self.db.records()[0]['SourceSet'], 'PubMed; DORA')
        self.assertEqual(self.db.db.execute('SELECT count(*) FROM review_event WHERE publication_id=?', (donor,)).fetchone()[0], 1)
        self.assertEqual(self.db.db.execute('SELECT count(*) FROM identity_decision').fetchone()[0], 1)
        self.assertEqual(self.ingest([record('dora', 'd1', '10.1234/wrong', None)], 'r3', 'dora'), [target])
        self.assertEqual(self.db.unresolved_conflicts(), 0)
        with self.assertRaises(ValueError):
            self.db.resolve_identity(donor, target, proof, 'Repeated', 'reviewer', '2026-01-03T00:00:00Z')

    def test_identifier_enrichment_retains_source_only_id(self):
        dora = record('dora', 'd1', None, None)
        key = self.ingest([dora], source='dora')[0]
        dora['doi'] = 'https://doi.org/10.1234/TEST'
        self.assertEqual(self.ingest([dora], 'r2', 'dora'), [key])
        self.assertEqual(self.ingest([record()], 'r3'), [key])
        self.assertEqual(len(self.db.records()), 1)
        self.assertEqual(self.db.records()[0]['SourceSet'], 'PubMed; DORA')

    def test_contradictory_identifiers_quarantined(self):
        self.ingest([record()])
        self.assertEqual(self.ingest([record(key='2', pmid='2')], 'r2'), [])
        self.assertEqual(len(self.db.records()), 1)
        self.assertEqual(self.db.unresolved_conflicts(), 1)

    def test_same_title_without_identifiers_not_merged(self):
        self.ingest([record()])
        self.ingest([record('dora', 'd1', None, None)], 'r2', 'dora')
        self.assertEqual(len(self.db.records()), 2)

    def test_duplicate_run_id_with_changed_content_rejected(self):
        self.ingest([record()])
        changed = record(); changed['title'] = 'Changed'
        with self.assertRaises(ValueError):
            self.ingest([changed])

    def test_old_run_replay_does_not_undo_latest_version(self):
        key = self.ingest([record()])[0]
        changed = record(); changed['title'] = 'Corrected title'
        self.ingest([changed], 'r2')
        self.assertEqual(self.ingest([record()]), [key])
        self.assertEqual(self.db.records()[0]['Title'], 'Corrected title')

    def test_missing_day_does_not_create_month(self):
        self.ingest([record()])
        row = self.db.records()[0]
        self.assertIsNone(row['PublicationMonth'])
        self.assertEqual(row['PublicationDatePrecision'], 'year')

    def test_monthly_and_all_exports_reconcile(self):
        a = record(); a['publication_date_parts'] = {'Year': '2024', 'Month': '2'}
        self.ingest([a, record(key='2', pmid='2', doi=None)])
        release = self.db.stage(self.root / 'releases', 'v1', {'pubmed': 'succeeded', 'dora': 'missing'})
        all_rows = json.loads((release / 'all-publications.json').read_text())
        month = json.loads((release / 'monthly/2024-02.json').read_text())
        self.assertEqual(all_rows['expected_canonical_count'], 2)
        self.assertEqual(month['expected_canonical_count'], 1)
        self.assertFalse((self.root / 'releases/current.json').exists())
        with self.assertRaises(ValueError):
            self.db.promote(release)

    def test_synthetic_registry_cannot_be_opened_as_live(self):
        with self.assertRaises(ValueError):
            Registry(self.root / 'registry.sqlite', data_kind='live_export')

    def test_openalex_enrichment_merges_with_pubmed(self):
        pub_key = self.ingest([record(source='pubmed', key='pm1', doi='10.1001/jama.2024.1', pmid='9901')], run='r_pm')[0]
        oa_rec = {
            'source': 'openalex',
            'source_record_id': 'W1234567890',
            'openalex_id': 'W1234567890',
            'doi': '10.1001/jama.2024.1',
            'pmid': '9901',
            'title': 'A publication',
            'journal': 'Journal',
            'authors': [{'name': 'A Author', 'affiliations': ['Cairns Hospital']}],
            'publication_date_parts': {'Year': '2024'},
            'url': 'https://openalex.org/W1234567890',
            'CitationCount_OpenAlex': 42,
            'OpenAccessStatus': 'Gold',
            'OAUrl': 'https://example.com/oa.pdf',
            'FunderNames': 'NHMRC; Queensland Health',
            'GrantIDs': 'G12345',
            'MeSHHeadings': 'Cardiology; Medicine',
            'AuthorKeywords': 'Health; Clinical Care'
        }
        res = self.ingest([oa_rec], run='r_oa', source='openalex')
        self.assertEqual(res, [pub_key])
        self.assertEqual(len(self.db.records()), 1)
        row = self.db.records()[0]
        self.assertIn('PubMed', row['SourceSet'])
        self.assertIn('OpenAlex', row['SourceSet'])
        self.assertEqual(row['CitationCount_OpenAlex'], 42)
        self.assertEqual(row['OpenAccessStatus'], 'Gold')
        self.assertEqual(row['OAUrl'], 'https://example.com/oa.pdf')
        self.assertEqual(row['FunderNames'], 'NHMRC; Queensland Health')
        self.assertEqual(row['GrantIDs'], 'G12345')

    def test_crossref_and_dimensions_ingestion_and_deduplication(self):
        doi = '10.1016/j.clin.2024.05'
        p1 = self.ingest([record(source='pubmed', key='p1', doi=doi, pmid='8888')], run='r1')[0]
        cr_rec = {
            'source': 'crossref',
            'source_record_id': doi,
            'doi': doi,
            'title': 'A publication',
            'journal': 'Journal',
            'authors': [{'name': 'A Author', 'affiliations': ['Cairns Hospital']}],
            'publication_date_parts': {'Year': '2024'},
            'url': f'https://doi.org/{doi}',
            'CitationCount_Crossref': 15,
            'FunderNames': 'Medical Research Future Fund'
        }
        self.assertEqual(self.ingest([cr_rec], run='r_cr', source='crossref'), [p1])
        dim_rec = {
            'source': 'dimensions',
            'source_record_id': 'pub.112233',
            'dimensions_id': 'pub.112233',
            'doi': doi,
            'title': 'A publication',
            'journal': 'Journal',
            'authors': [{'name': 'A Author', 'affiliations': ['Cairns Hospital']}],
            'publication_date_parts': {'Year': '2024'},
            'url': f'https://app.dimensions.ai/details/publication/pub.112233',
            'GrantIDs': 'MRFF-2024'
        }
        self.assertEqual(self.ingest([dim_rec], run='r_dim', source='dimensions'), [p1])
        row = self.db.records()[0]
        self.assertEqual(row['CitationCount_Crossref'], 15)
        self.assertIn('PubMed', row['SourceSet'])
        self.assertIn('Crossref', row['SourceSet'])
        self.assertIn('Dimensions', row['SourceSet'])
        self.assertIn('Medical Research Future Fund', row['FunderNames'])
        self.assertIn('MRFF-2024', row['GrantIDs'])


if __name__ == '__main__':
    unittest.main()

