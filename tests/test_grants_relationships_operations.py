import unittest
import json
from pathlib import Path

from scripts.grants_operations import evaluate_run, reconcile_registry_keys, reconcile_registry_records
from scripts.grants_planning import delivery_event_key, validate_policy
from scripts.grants_relationships import normalize_relationship


class GrantsRelationshipTests(unittest.TestCase):
    def test_relationship_schema_matches_normalized_projection(self):
        schema = json.loads((Path(__file__).parents[1] / 'config/grant-relationships.schema.json').read_text())
        row = normalize_relationship({'RelationshipType':'funded_by_award','FromKey':'GRANT:1','ToKey':'PUB:1','AwardID':'MRFF-1','EvidenceURL':'https://evidence','Confidence':'confirmed'})
        self.assertEqual(schema['identity_field'], 'RelationshipKey')
        identity = next(field for field in schema['fields'] if field['display_name'] == 'RelationshipKey')
        self.assertTrue(identity['required'] and identity['indexed'] and identity['unique'])
        self.assertEqual({f['display_name'] for f in schema['fields']}, set(row))
        self.assertEqual(schema['list_name'], 'Grant Relationships')

    def test_confirmed_award_requires_exact_award_id(self):
        with self.assertRaises(ValueError):
            normalize_relationship({'RelationshipType':'funded_by_award','FromKey':'GRANT:1','ToKey':'PUB:1','EvidenceURL':'https://evidence','Confidence':'confirmed'})
        with self.assertRaises(ValueError):
            normalize_relationship({'RelationshipType':'funded_by_award','FromKey':'GRANT:1','ToKey':'PUB:1','AwardID':'   ','EvidenceURL':'https://evidence','Confidence':'confirmed'})
        row = normalize_relationship({'RelationshipType':'funded_by_award','FromKey':'GRANT:1','ToKey':'PUB:1','AwardID':'MRFF-1','EvidenceURL':'https://evidence','Confidence':'confirmed'})
        self.assertTrue(row['RelationshipKey'].startswith('REL:'))

    def test_topic_relevance_is_not_promoted_to_funding(self):
        row = normalize_relationship({'RelationshipType':'relevant_to_opportunity','FromKey':'PUB:1','ToKey':'GRANT:1','EvidenceURL':'https://evidence','Confidence':'candidate'})
        self.assertEqual(row['RelationshipType'], 'relevant_to_opportunity')
        self.assertEqual(row['Confidence'], 'candidate')

    def test_relationship_requires_http_evidence_url(self):
        with self.assertRaisesRegex(ValueError, 'requires from/to keys and evidence'):
            normalize_relationship({'RelationshipType':'relevant_to_opportunity','FromKey':'PUB:1','ToKey':'GRANT:1','EvidenceURL':'evidence','Confidence':'candidate'})

    def test_relationship_rejects_surrounding_whitespace(self):
        base = {
            'RelationshipType': 'relevant_to_opportunity',
            'FromKey': 'PUB:1',
            'ToKey': 'GRANT:1',
            'EvidenceURL': 'https://evidence',
            'Confidence': 'candidate',
            'AwardID': '',
            'ReviewStatus': 'Needs Review',
        }
        for field in base:
            with self.subTest(field=field):
                row = dict(base)
                row[field] = f" {row[field]} "
                with self.assertRaises(ValueError):
                    normalize_relationship(row)

    def test_relationship_review_status_is_constrained(self):
        with self.assertRaisesRegex(ValueError, 'unsupported review status'):
            normalize_relationship({'RelationshipType':'relevant_to_opportunity','FromKey':'PUB:1','ToKey':'GRANT:1','EvidenceURL':'https://evidence','Confidence':'candidate','ReviewStatus':'Reviewed'})

    def test_relationship_inputs_are_not_coerced(self):
        invalid_rows = [
            {'RelationshipType': 7, 'FromKey': 'PUB:1', 'ToKey': 'GRANT:1', 'EvidenceURL': 'https://evidence'},
            {'RelationshipType': 'relevant_to_opportunity', 'FromKey': ['PUB:1'], 'ToKey': 'GRANT:1', 'EvidenceURL': 'https://evidence'},
            {'RelationshipType': 'relevant_to_opportunity', 'FromKey': 'PUB:1', 'ToKey': 'GRANT:1', 'EvidenceURL': 9},
            {'RelationshipType': 'relevant_to_opportunity', 'FromKey': 'PUB:1', 'ToKey': 'GRANT:1', 'EvidenceURL': 'https://evidence', 'Confidence': 1},
            {'RelationshipType': 'relevant_to_opportunity', 'FromKey': 'PUB:1', 'ToKey': 'GRANT:1', 'EvidenceURL': 'https://evidence', 'AwardID': 1},
            {'RelationshipType': 'relevant_to_opportunity', 'FromKey': 'PUB:1', 'ToKey': 'GRANT:1', 'EvidenceURL': 'https://evidence', 'ReviewStatus': False},
        ]
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    normalize_relationship(row)
        with self.assertRaisesRegex(ValueError, 'relationship record'):
            normalize_relationship([])

    def test_run_rejects_failed_source_and_preserves_last_batch(self):
        result = evaluate_run([{'OpportunityKey':'GRANT:1'}], [{'source':'nhmrc','status':'failed','count':0}], [{'OpportunityKey':'GRANT:old'}])
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['records'], [{'OpportunityKey':'GRANT:old'}])

    def test_run_rejects_missing_source_health(self):
        result = evaluate_run([{'OpportunityKey':'GRANT:1', 'Source':'nhmrc'}], [], [{'OpportunityKey':'GRANT:old'}])
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('missing_source_health', result['errors'])

    def test_run_rejects_record_from_unreported_source(self):
        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1', 'Source':'mrff'}],
            [{'source':'nhmrc', 'status':'succeeded', 'count':1}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('unreported_source', result['errors'])

    def test_run_rejects_incomplete_or_duplicate_health_rows(self):
        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1', 'Source':'nhmrc'}],
            [{'source':'nhmrc','status':'succeeded','count':1}, {'source':'nhmrc','status':'succeeded','count':1}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('duplicate_health_source', result['errors'])

        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1', 'Source':'nhmrc'}],
            [{'source':'','status':'succeeded','count':1}],
        )
        self.assertIn('missing_health_source', result['errors'])

    def test_run_rejects_records_without_source(self):
        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1'}],
            [{'source':'nhmrc','status':'succeeded','count':1}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('missing_record_source', result['errors'])

    def test_run_rejects_invalid_or_mismatched_health_counts(self):
        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1', 'Source':'nhmrc'}],
            [{'source':'nhmrc', 'status':'succeeded', 'count':2}],
        )
        self.assertIn('health_record_count_mismatch', result['errors'])

        result = evaluate_run(
            [{'OpportunityKey':'GRANT:1', 'Source':'nhmrc'}],
            [{'source':'nhmrc', 'status':'succeeded', 'count':True}],
        )
        self.assertIn('invalid_health_count', result['errors'])

    def test_run_rejects_non_string_identities_without_coercion(self):
        result = evaluate_run(
            [{'OpportunityKey': ['not-a-key'], 'Source': 7}],
            [{'source': True, 'status': 'succeeded', 'count': 1}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('invalid_opportunity_key', result['errors'])
        self.assertIn('invalid_record_source', result['errors'])
        self.assertIn('invalid_health_source', result['errors'])

    def test_run_rejects_duplicate_normalized_opportunity_keys(self):
        result = evaluate_run(
            [
                {'OpportunityKey': 'GRANT:1', 'Source': 'nhmrc'},
                {'OpportunityKey': ' GRANT:1 ', 'Source': 'nhmrc'},
            ],
            [{'source': 'nhmrc', 'status': 'succeeded', 'count': 2}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('duplicate_opportunity_key', result['errors'])

    def test_run_rejects_whitespace_divergent_source_and_identity_values(self):
        result = evaluate_run(
            [{'OpportunityKey': ' GRANT:1 ', 'Source': ' nhmrc '}],
            [{'source': ' nhmrc ', 'status': 'succeeded', 'count': 1}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('whitespace_opportunity_key', result['errors'])
        self.assertIn('whitespace_record_source', result['errors'])
        self.assertIn('whitespace_health_source', result['errors'])

    def test_run_rejects_non_object_rows_without_incidental_errors(self):
        result = evaluate_run(
            [None],
            [None],
            [{'OpportunityKey': 'GRANT:old'}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('invalid_record_object', result['errors'])
        self.assertIn('invalid_health_object', result['errors'])
        self.assertEqual(result['records'], [{'OpportunityKey': 'GRANT:old'}])

    def test_registry_reconciliation_requires_exact_key_sets(self):
        result = reconcile_registry_keys(
            [{'OpportunityKey': ' g1 '}, {'OpportunityKey': 'g2'}],
            [{'OpportunityKey': 'g1'}, {'OpportunityKey': 'g2'}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('whitespace_emitted_key', result['errors'])

        result = reconcile_registry_keys(
            [{'OpportunityKey': 'g1'}, {'OpportunityKey': 'g2'}],
            [{'OpportunityKey': 'g1'}, {'OpportunityKey': 'g3'}],
            [{'OpportunityKey': 'old'}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('registry_missing_emitted_keys', result['errors'])
        self.assertIn('registry_has_unexpected_keys', result['errors'])
        self.assertEqual(result['records'], [{'OpportunityKey': 'old'}])

    def test_registry_reconciliation_rejects_malformed_or_duplicate_rows(self):
        result = reconcile_registry_keys([None], [{'OpportunityKey': 'g1'}])
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('invalid_emitted_record_object', result['errors'])
        result = reconcile_registry_keys(
            [{'OpportunityKey': 'g1'}, {'OpportunityKey': 'g1'}],
            [{'OpportunityKey': 'g1'}],
        )
        self.assertIn('duplicate_emitted_key', result['errors'])

    def test_registry_reconciliation_checks_selected_fields_and_preserves_prior(self):
        emitted = [{'OpportunityKey': 'g1', 'Title': 'Call', 'Status': 'open'}]
        readback = [{'OpportunityKey': 'g1', 'Title': 'Call', 'Status': 'open'}]
        result = reconcile_registry_records(emitted, readback, ['Title', 'Status'])
        self.assertEqual(result['status'], 'reconciled')
        result = reconcile_registry_records(
            emitted,
            [{'OpportunityKey': 'g1', 'Title': 'Changed', 'Status': 'open'}],
            ['Title', 'Status'],
            [{'OpportunityKey': 'old'}],
        )
        self.assertEqual(result['status'], 'rejected')
        self.assertIn('field_mismatch:g1:Title', result['errors'])
        self.assertEqual(result['records'], [{'OpportunityKey': 'old'}])

    def test_registry_reconciliation_requires_explicit_unique_fields(self):
        with self.assertRaisesRegex(ValueError, 'unique'):
            reconcile_registry_records([], [], ['Title', 'Title'])
        with self.assertRaisesRegex(ValueError, 'collection'):
            reconcile_registry_records([], [], 'Title')
        result = reconcile_registry_records(
            [{'OpportunityKey': 'g1', 'Title': 'Call'}],
            [{'OpportunityKey': 'g1', 'Title': 'Call'}],
            [' Title '],
        )
        self.assertEqual(result['status'], 'reconciled')

    def test_policy_and_delivery_keys_are_versioned(self):
        policy = {'PolicyKey':'CHHHS-DEFAULT','Version':'1.0','OrganisationKey':'CHHHS','AnchorKind':'final','LeadDays':10,'CalendarOrBusinessDays':'business','HolidayCalendarVersion':'qld-2026','EffectiveFrom':'2026-01-01'}
        self.assertTrue(validate_policy(policy))
        self.assertEqual(
            delivery_event_key('u','g','new','1',10,'email', current_user_key='u'),
            delivery_event_key('u','g','new','1',10,'email', current_user_key='u'),
        )

    def test_delivery_key_rejects_coercible_or_unbounded_inputs(self):
        with self.assertRaisesRegex(ValueError, 'identity fields'):
            delivery_event_key(None, 'g', 'new', '1', 10, 'email', current_user_key='u')
        with self.assertRaisesRegex(ValueError, 'identity fields'):
            delivery_event_key('u', 'g', 'new', '1', 10, '', current_user_key='u')
        with self.assertRaisesRegex(ValueError, 'offset_days'):
            delivery_event_key('u', 'g', 'new', '1', True, 'email', current_user_key='u')
        with self.assertRaisesRegex(ValueError, 'offset_days'):
            delivery_event_key('u', 'g', 'new', '1', 3661, 'email', current_user_key='u')
        with self.assertRaisesRegex(ValueError, 'match current_user_key'):
            delivery_event_key('u2', 'g', 'new', '1', 10, 'email', current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'surrounding whitespace'):
            delivery_event_key('u1', 'g', 'new', '1', 10, 'email', current_user_key=' u1')


if __name__ == '__main__':
    unittest.main()
