import unittest
from scripts.grants_planning import institutional_deadline, subscribers, validate_policy
from scripts.grants_registry import normalize_opportunity


class PlanningTests(unittest.TestCase):
    def test_business_days_skip_supplied_holidays(self):
        self.assertEqual(institutional_deadline('2026-09-28', 1, holidays=['2026-09-25']), '2026-09-24')

    def test_unknown_precision_does_not_invent_deadline(self):
        self.assertIsNone(institutional_deadline('2026-09', 5))

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            institutional_deadline('2026-09-28', -1)
        with self.assertRaisesRegex(ValueError, 'holidays'):
            institutional_deadline('2026-09-28', 1, holidays=[20260925])
        with self.assertRaisesRegex(ValueError, 'holidays'):
            institutional_deadline('2026-09-28', 1, holidays=['2026-09-25', '2026-09-25'])
        for malformed in (None, {'2026-09-25': True}):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, 'holidays'):
                institutional_deadline('2026-09-28', 1, holidays=malformed)
        self.assertFalse(validate_policy(None))

    def test_policy_rejects_reversed_effective_range_and_bad_holiday(self):
        policy = {
            'PolicyKey': 'CHHHS-DEFAULT', 'Version': '1.0', 'OrganisationKey': 'CHHHS',
            'AnchorKind': 'application_close', 'LeadDays': 10,
            'CalendarOrBusinessDays': 'business', 'HolidayCalendarVersion': 'qld-2026',
            'EffectiveFrom': '2026-01-01', 'EffectiveTo': '2026-12-31',
        }
        reversed_policy = {**policy, 'EffectiveTo': '2025-12-31'}
        self.assertFalse(validate_policy(reversed_policy))
        bad_holiday = {**policy, 'HolidayDates': ['2026-02-30']}
        self.assertFalse(validate_policy(bad_holiday))
        non_string_holiday = {**policy, 'HolidayDates': [20260228]}
        self.assertFalse(validate_policy(non_string_holiday))

    def test_policy_identity_and_effective_dates_are_strings(self):
        policy = {
            'PolicyKey': 'CHHHS-DEFAULT', 'Version': '1.0', 'OrganisationKey': 'CHHHS',
            'AnchorKind': 'application_close', 'LeadDays': 10,
            'CalendarOrBusinessDays': 'business', 'HolidayCalendarVersion': 'qld-2026',
            'EffectiveFrom': '2026-01-01',
        }
        for field in ('PolicyKey', 'Version', 'OrganisationKey', 'AnchorKind', 'HolidayCalendarVersion', 'EffectiveFrom'):
            with self.subTest(field=field):
                invalid = {**policy, field: 7}
                self.assertFalse(validate_policy(invalid))
        self.assertFalse(validate_policy({**policy, 'EffectiveTo': False}))
        self.assertFalse(validate_policy({**policy, 'EffectiveTo': ''}))

    def test_policy_identity_and_dates_reject_surrounding_whitespace(self):
        policy = {
            'PolicyKey': 'CHHHS-DEFAULT', 'Version': '1.0', 'OrganisationKey': 'CHHHS',
            'AnchorKind': 'application_close', 'LeadDays': 10,
            'CalendarOrBusinessDays': 'business', 'HolidayCalendarVersion': 'qld-2026',
            'EffectiveFrom': '2026-01-01',
        }
        for field in ('PolicyKey', 'Version', 'OrganisationKey', 'AnchorKind', 'HolidayCalendarVersion', 'EffectiveFrom'):
            with self.subTest(field=field):
                self.assertFalse(validate_policy({**policy, field: f' {policy[field]}'}))
        self.assertFalse(validate_policy({**policy, 'EffectiveTo': '2026-12-31 '}))
        self.assertFalse(validate_policy({**policy, 'HolidayDates': [' 2026-12-25']}))

    def test_overlapping_subscriptions_deduplicate_and_respect_pause(self):
        grant = {'OpportunityKey': 'g1', 'CategoryKeys': ['health']}
        rules = [
            {'UserKey': 'u1', 'Active': True, 'Scope': 'category', 'TargetKey': 'health'},
            {'UserKey': 'u1', 'Active': True, 'Scope': 'opportunity', 'TargetKey': 'g1'},
            {'UserKey': 'u2', 'Active': False, 'Scope': 'opportunity', 'TargetKey': 'g1'},
        ]
        self.assertEqual(subscribers(grant, rules, current_user_key='u1'), ['u1'])
        self.assertEqual(subscribers(grant, rules, current_user_key='u2'), [])

    def test_malformed_subscription_rule_fails_closed(self):
        with self.assertRaises(ValueError):
            subscribers({'OpportunityKey': 'g1'}, [{'UserKey': 'u1', 'Active': True, 'Scope': 'unknown', 'TargetKey': 'g1'}], current_user_key='u1')
        with self.assertRaises(ValueError):
            subscribers({'OpportunityKey': 'g1'}, [{'UserKey': 'u1', 'Active': 'yes', 'Scope': 'opportunity', 'TargetKey': 'g1'}], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'rule must be an object'):
            subscribers({'OpportunityKey': 'g1'}, [None], current_user_key='u1')
        for malformed in (None, 'not-a-rule'):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, 'subscriptions must be a collection'):
                subscribers({'OpportunityKey': 'g1'}, malformed, current_user_key='u1')

    def test_subscription_identity_types_are_not_coerced(self):
        with self.assertRaisesRegex(ValueError, 'OpportunityKey'):
            subscribers({'OpportunityKey': True}, [], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'CategoryKeys'):
            subscribers({'OpportunityKey': 'g1', 'CategoryKeys': [7]}, [], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'FunderKey'):
            subscribers({'OpportunityKey': 'g1', 'FunderKey': 7}, [], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'FunderKey'):
            subscribers({'OpportunityKey': 'g1', 'FunderKey': False}, [], current_user_key='u1')

    def test_subscription_identities_reject_surrounding_whitespace(self):
        with self.assertRaisesRegex(ValueError, 'current_user_key'):
            subscribers({'OpportunityKey': 'g1'}, [], current_user_key=' u1')
        with self.assertRaisesRegex(ValueError, 'OpportunityKey'):
            subscribers({'OpportunityKey': ' g1'}, [], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'UserKey'):
            subscribers(
                {'OpportunityKey': 'g1'},
                [{'UserKey': ' u1', 'Active': True, 'Scope': 'opportunity', 'TargetKey': 'g1'}],
                current_user_key='u1',
            )

    def test_subscription_matching_requires_opportunity_identity(self):
        with self.assertRaises(ValueError):
            subscribers({}, [], current_user_key='u1')
        with self.assertRaisesRegex(ValueError, 'current_user_key'):
            subscribers({'OpportunityKey': 'g1'}, [], current_user_key=None)

    def test_alias_input_has_same_identity(self):
        a = normalize_opportunity({'title': 'Call', 'link': 'https://example.org/call'})
        b = normalize_opportunity({'Title': 'Call', 'URL': 'https://example.org/call'})
        self.assertEqual(a['OpportunityKey'], b['OpportunityKey'])

    def test_impossible_deadline_is_unknown(self):
        self.assertEqual(normalize_opportunity({'Deadline': '2027-02-30'})['DeadlinePrecision'], 'unknown')

    def test_rounds_do_not_merge(self):
        a = {'Source': 'f', 'SourceID': 'scheme', 'RoundID': '2026'}
        b = {**a, 'RoundID': '2027'}
        self.assertNotEqual(normalize_opportunity(a)['OpportunityKey'], normalize_opportunity(b)['OpportunityKey'])
