"""Scientific identity regressions for the legacy model reference implementation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from canonical_reference import reconcile_sources

class ConservativeIdentityTests(unittest.TestCase):
    def rows(self, **extra):
        return reconcile_sources([{'PMID':'123', 'Title':'Same title', 'PublicationYear':2020, 'DOI':'10.1234/a'}],
            [{'DORAKey':'DORA:1', 'Title':'Same title', 'PublicationYear':2020, **extra}])

    def test_unique_title_is_only_a_review_candidate(self):
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['DedupMethod'], 'possible-title+year-needs-review')

    def test_exact_doi_can_merge_despite_title_variation(self):
        rows = self.rows(DOI='https://doi.org/10.1234/A', Title='Variant title')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['DedupMethod'], 'DOI')

    def test_exact_pmid_with_conflicting_doi_is_not_merged(self):
        rows = self.rows(PMID='123', DOI='10.1234/b')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['DedupMethod'], 'conflicting-identifiers-needs-review')

    def test_exact_doi_with_conflicting_pmid_is_not_merged(self):
        self.assertEqual(len(self.rows(PMID='124', DOI='10.1234/a')), 2)

    def test_invalid_identifier_does_not_merge(self):
        self.assertEqual(len(self.rows(DOI='not a doi')), 2)

    def test_missing_titles_and_years_are_not_match_evidence(self):
        rows = reconcile_sources([{'PMID':'123'}], [{'DORAKey':'DORA:1'}])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['CandidateCount'], 0)

    def test_multiple_exact_identifier_matches_need_review(self):
        rows = reconcile_sources([{'PMID':'123','DOI':'10.1234/a'}, {'PMID':'124','DOI':'10.1234/a'}],
                                 [{'DORAKey':'DORA:1','DOI':'10.1234/a'}])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]['DedupMethod'], 'ambiguous-identifiers-needs-review')

    def test_exact_pmid_with_malformed_doi_stays_under_review(self):
        rows = self.rows(PMID='123', DOI='malformed')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['DedupMethod'], 'invalid-identifiers-needs-review')

    def test_empty_sources_keep_dora_records(self):
        self.assertEqual(reconcile_sources([], []), [])
        rows = reconcile_sources([], [{'DORAKey':'DORA:1', 'Title':'Repository record'}])
        self.assertEqual([r['CanonicalKey'] for r in rows], ['DORA:1'])
