import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from qualify_protocol_award_metadata import parse_cover

COVER = '''Clinical trials registration NCT00000001
Protocol version/date Version 1.0, dated 1 January 2026
Protocol number CT12345
Funding source Australia:
 NHMRC 2021 Clinical Trials and Cohort Studies
 (Application ID 1234567)
 NHMRC 2021 MRFF International Clinical Trial
 Collaborations (Application ID 7654321)
'''

class ProtocolCoverTests(unittest.TestCase):
    def test_explicit_funding_field_not_adjacent_mrff_number(self):
        row = parse_cover(COVER)
        self.assertEqual(row['original_application_id'], '1234567')
        self.assertEqual(row['study_identifier'], 'clinicaltrials.gov:NCT00000001')
        self.assertEqual(row['source_page'], 1)

    def test_conflicting_study_identity_rejected(self):
        with self.assertRaises(ValueError):
            parse_cover(COVER + '\nClinical trials registration NCT00000002')

    def test_later_page_mentions_do_not_supply_missing_cover_evidence(self):
        with self.assertRaises(ValueError):
            parse_cover(COVER.replace('Clinical trials registration', 'Trial title') + '\fClinical trials registration NCT00000001')

    def test_number_outside_explicit_funding_section_rejected(self):
        wrong = COVER.replace('Funding source Australia:', 'Funding section absent')
        with self.assertRaises(ValueError):
            parse_cover(wrong)
