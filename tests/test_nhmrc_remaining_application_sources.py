import io
import hashlib
import json
import tempfile
from unittest.mock import patch
import sys
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nhmrc_remaining_application_sources as remaining
from nhmrc_remaining_application_sources import (
    government_application, publication_identity, publisher_investigator_application,
    protocol_application, repository_direct_grant, repository_project_grant,
)


class RemainingApplicationSourceTests(unittest.TestCase):
    def pub(self, doi='10.1234/fixture', pmid='12345678'):
        return ('<meta name="citation_doi" content="' + doi + '">'
                '<meta name="citation_pmid" content="' + pmid + '">')

    def test_explicit_project_path_does_not_need_title_or_person_matching(self):
        url = 'https://institution.example/projects/fixture/'
        pub = self.pub() + '<a rel="UPMProject" href="' + url + '">Unrelated display title</a>'
        project = '<a href="http://purl.org/au-research/grants/nhmrc/1146525">Grant</a>'
        result = repository_project_grant(pub, project, '10.1234/fixture', '12345678', 'APP1146525', url)
        self.assertEqual(result['source_grant_uri'], 'http://purl.org/au-research/grants/nhmrc/1146525')
        for bad in [pub.replace('UPMProject', 'untyped'), pub.replace('12345678', '87654321')]:
            with self.assertRaises(ValueError):
                repository_project_grant(bad, project, '10.1234/fixture', '12345678', 'APP1146525', url)

    def test_direct_uri_is_preserved_and_does_not_claim_registry_identity(self):
        pub = self.pub() + '<a href="http://purl.org/au-research/grants/NHMRC/2008625">Grant</a>'
        result = repository_direct_grant(pub, '10.1234/fixture', '12345678', 'APP2008625')
        self.assertIn('/NHMRC/', result['source_grant_uri'])
        self.assertEqual(result['target_kind'], 'historical_nhmrc_application')
        with self.assertRaises(ValueError):
            repository_direct_grant(pub + pub, '10.1234/fixture', '12345678', 'APP2008625')

    def test_funding_clause_must_be_in_explicit_funding_section(self):
        clause = 'National Health and Medical Research Council of Australia Investigator Grant (APP1176192, awarded to ABC)'
        html = self.pub() + '<section data-title="Funding"><p>' + clause + '</p></section>'
        result = publisher_investigator_application(html, self.pub(), '10.1234/fixture', '12345678', 'APP1176192')
        self.assertEqual(result['application_number'], '1176192')
        for bad in [html.replace('data-title="Funding"', 'data-title="References"'),
                    html.replace('APP1176192', 'MRF1176192'),
                    html.replace('National Health and Medical Research Council of Australia', 'Wellcome Trust')]:
            with self.assertRaises(ValueError):
                publisher_investigator_application(bad, self.pub(), '10.1234/fixture', '12345678', 'APP1176192')

    def workbook(self, ids, heading='APP ID'):
        book = openpyxl.Workbook(); sheet = book.active; sheet.title = 'GRANTS DATA'
        sheet.append([heading, 'Grant Title']);
        for number in ids:
            sheet.append([number, 'Identical title must not choose the record'])
        target = io.BytesIO(); book.save(target); book.close(); return target.getvalue()

    def test_unique_numeric_application_column_and_actual_row_locator(self):
        result = government_application(self.workbook([1176192, 1184238]), 'GRANTS DATA', '1184238')
        self.assertEqual(result['row'], 3)
        self.assertEqual(result['target_key'], 'nhmrc:1184238')
        for data in [self.workbook([1184238, 1184238]), self.workbook([1176192]),
                     self.workbook([1184238], 'Grant ID')]:
            with self.assertRaises(ValueError):
                government_application(data, 'GRANTS DATA', '1184238')

    def test_no_general_prefix_or_unicode_normalisation(self):
        pub = self.pub() + '<a href="http://purl.org/au-research/grants/NHMRC/2008625">Grant</a>'
        for code in ['MRF2008625', 'APP 2008625', 'APP２００８６２５', 'APP2008625 ', 'app2008625']:
            with self.assertRaises(ValueError):
                repository_direct_grant(pub, '10.1234/fixture', '12345678', code)

    def test_publication_identity_is_not_inferred_from_page_titles(self):
        with self.assertRaises(ValueError):
            publication_identity(self.pub('10.1234/other'), '10.1234/fixture', '12345678')
        with self.assertRaises(ValueError):
            publication_identity(self.pub() + self.pub(), '10.1234/fixture', '12345678')

    def test_protocol_ctcs_clause_does_not_admit_adjacent_mrff_application(self):
        page = '''Clinical trials registration NCT12345678
Protocol version/date Version 2.0, dated 24 March 2023
Protocol number CT19029
Funding source Australia:
National Health and Medical Research Council (NHMRC) Clinical Trials and Cohort Studies
funding grant (Award ID: APP1184238)
NHMRC 2021 Clinical Trials and Cohort Studies (Application ID 2014900)
NHMRC 2021 MRFF International Clinical Trial Collaborations (Application ID 2017301)
'''
        result = protocol_application(page, 'APP1184238')
        self.assertEqual(result['application_number'], '1184238')
        self.assertEqual(result['original_identifier'], 'APP1184238')
        self.assertEqual(result['anchor_application_number'], '2014900')
        self.assertEqual(result['study_identifier'], 'clinicaltrials.gov:NCT12345678')
        with self.assertRaises(ValueError):
            protocol_application(page, 'APP2017301')

    def test_pinned_authority_with_missing_identity_refuses_before_projection(self):
        for missing in [None, '', '   ', 123, []]:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                authority = {'id': missing, 'links': [{'type': 'website', 'value': 'https://www.nhmrc.gov.au/'}]}
                def write(name, value):
                    data = json.dumps(value).encode(); (root / name).write_bytes(data)
                    return dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                source = write('authority-ror.json', authority)
                policy = write('rule-authority.json', dict(rule=remaining.RULE_ID, namespace='nhmrc',
                                                          batch='fixture', source_files=[source]))
                write('manifest.json', dict(kind='nhmrc_explicit_application_sources_v1', complete=True,
                                            batch='fixture', files=[source, policy]))
                with patch.object(remaining, 'AUTHORITY_SHA256', {}):
                    with self.assertRaisesRegex(ValueError, 'namespace authority'):
                        remaining.project_packet(root, [], [], policy['sha256'])
