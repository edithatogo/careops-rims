import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_structured_monthly_report import prepare
from tests.test_reconcile_full_month_exports import paged


class StructuredReportInputTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((Path(__file__).parent /
            'fixtures/webfirst-export-synthetic.json').read_text())['records']

    def build(self, rows, period='2026-08'):
        full = paged(rows, {'mode': 'all', 'reporting_month': None})
        month = paged([r for r in rows if r['PublicationMonth'] == period],
                      {'mode': 'month', 'reporting_month': period})
        return full, month

    def prepare(self, full, month, **kwargs):
        return prepare(full, month, template_sha256='a' * 64,
            output_revision='sample-1', generated_at='2026-10-19T12:00:00+10:00',
            **kwargs)

    def test_zero_one_many_and_complete_source_values_are_preserved(self):
        selected = [r for r in self.rows if r['PublicationMonth'] == '2026-08']
        for rows in ([], selected[:1], selected):
            rows = copy.deepcopy(rows)
            for r in rows:
                r['Authors'] = 'Étude — ' * 2000
                r['AttributionEvidence'] = None
            full, month = self.build(rows)
            result = self.prepare(full, month)
            self.assertEqual(result['records'], rows)
            self.assertEqual(len(result['fields']['Bibliography']), len(rows))
            for record, entry in zip(rows, result['fields']['Bibliography']):
                self.assertIn(json.dumps(record['Authors'], ensure_ascii=False), entry['Citation'])
                self.assertIn('AttributionEvidence: null', entry['Citation'])
                self.assertEqual(entry['CanonicalKey'], record['CanonicalKey'])
            self.assertFalse(result['native_generation_proved'])

    def test_missing_monthly_record_is_rejected_before_template_mapping(self):
        full, month = self.build(self.rows)
        month = paged(month['pages'][0]['records'][:-1], month['scope'])
        with self.assertRaisesRegex(ValueError, 'Monthly keys differ'):
            self.prepare(full, month)

    def test_naive_time_and_blank_revision_are_rejected(self):
        full, month = self.build(self.rows)
        for revision, when in [(' ', '2026-10-19T12:00:00+10:00'),
                               ('sample-1', '2026-10-19T12:00:00')]:
            with self.assertRaises(ValueError):
                prepare(full, month, template_sha256='a' * 64,
                        output_revision=revision, generated_at=when)
