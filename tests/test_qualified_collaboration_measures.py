import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_qualified_collaboration_measures import PATH, MEASURES, prepare, reference_summaries


class QualifiedCollaborationTests(unittest.TestCase):
    def row(self, provider='PubMed', publication='publication:1', **changes):
        value = dict(RelationshipKind='coauthorship', AdmissionState='Source-supported',
                     CanonicalKey=publication, FromKey='orcid:0000-0001-5109-3700',
                     ToKey='orcid:0000-0002-1825-0097', SourceProvider=provider)
        value.update(changes)
        return value

    def test_corroboration_requires_same_publication_pair_and_distinct_provider(self):
        rows = [self.row(), self.row(), self.row('OpenAlex', 'publication:2')]
        self.assertEqual(list(reference_summaries(rows).values()), [1, 2, 0, 0])
        rows.append(self.row('OpenAlex'))
        self.assertEqual(list(reference_summaries(rows).values()), [1, 2, 1, 1])

    def test_unmapped_conflicting_and_provider_only_identities_are_excluded(self):
        rows = [self.row(AdmissionState='Ambiguous DOI'),
                self.row(AdmissionState='Conflicting identifiers'),
                self.row(FromKey='https://openalex.org/A123')]
        self.assertEqual(list(reference_summaries(rows).values()), [0, 0, 0, 0])
        with self.assertRaises(ValueError):
            reference_summaries([self.row(FromKey='orcid:0000-0001-5109-3701')])

    def test_model_preparation_preserves_partition_and_other_parts(self):
        source = "table SourceRelationshipEvidence\n\tmeasure Existing = 1\n\tpartition SourceRelationshipEvidence = m\n\t\tsource = unchanged\n"
        document = {'definition': {'parts': [dict(path=PATH, payload=base64.b64encode(source.encode()).decode()), dict(path='other', payload='unchanged')]}}
        candidate = prepare(document)
        text = base64.b64decode(candidate['definition']['parts'][0]['payload']).decode()
        self.assertTrue(text.endswith(source.split('\tpartition', 1)[1]))
        self.assertEqual(candidate['definition']['parts'][1], document['definition']['parts'][1])
        self.assertEqual(text.count('formatString: #,0'), len(MEASURES))
        with self.assertRaises(ValueError):
            prepare(candidate)

    def test_provider_selection_does_not_erase_other_provider_corroboration(self):
        rows = [self.row(), self.row('OpenAlex'), self.row('PubMed', 'publication:2')]
        self.assertEqual(list(reference_summaries(rows, {'PubMed'}).values()), [1, 2, 1, 1])
        self.assertEqual(list(reference_summaries(rows, {'OpenAlex'}).values()), [1, 1, 1, 1])
        self.assertEqual(list(reference_summaries(rows, {'Other'}).values()), [0, 0, 0, 0])
        self.assertEqual(list(reference_summaries(rows, set()).values()), [0, 0, 0, 0])
        for name in ['Cross-source corroborated researcher pairs', 'Cross-source corroborated publications']:
            self.assertIn('REMOVEFILTERS(SourceRelationshipEvidence[SourceProvider])', MEASURES[name])
            self.assertIn('INTERSECT(', MEASURES[name])
