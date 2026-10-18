from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from datetime import date,datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from project_utils import parse_pub_date,previous_month,m_text
from pubmed_reference import reconcile_search,reconcile_summary,facility_union
from canonical_reference import reconcile_sources,normalize_title
from validate_project import validate,reference_errors,m_lexical_errors
from audit_pbix import expand,strings

class DatePolicyTests(unittest.TestCase):
    def test_day_31_preserved(self): self.assertEqual(parse_pub_date('2026 Aug 31')['date'],'2026-08-31')
    def test_day_30_preserved(self): self.assertEqual(parse_pub_date('2026 Apr 30')['date'],'2026-04-30')
    def test_valid_leap_day(self): self.assertEqual(parse_pub_date('2024 Feb 29')['date'],'2024-02-29')
    def test_invalid_leap_day_not_clamped(self): self.assertIsNone(parse_pub_date('2025 Feb 29')['date'])
    def test_month_only_precision(self): self.assertEqual((parse_pub_date('2026 Aug')['date'],parse_pub_date('2026 Aug')['precision']),('2026-08-01','month'))
    def test_year_only_not_january(self): self.assertEqual((parse_pub_date('2026')['date'],parse_pub_date('2026')['precision']),(None,'year'))
    def test_missing_date_not_today(self): self.assertIsNone(parse_pub_date(None)['year'])
    def test_unknown_text(self): self.assertIsNone(parse_pub_date('ahead of print')['date'])
    def test_range_not_invented(self): self.assertEqual(parse_pub_date('2026 Jul-Aug')['precision'],'range')
    def test_season_not_invented(self): self.assertIsNone(parse_pub_date('2026 Winter')['date'])
    def test_iso_date(self): self.assertEqual(parse_pub_date('2026-08-31')['date'],'2026-08-31')
    def test_invalid_day(self): self.assertIsNone(parse_pub_date('2026 Apr 31')['date'])
    def test_invalid_month(self): self.assertIsNone(parse_pub_date('2026 13 03')['date'])
    def test_current_month_window(self): self.assertEqual(previous_month(datetime(2026,9,11,tzinfo=timezone.utc)),(date(2026,8,1),date(2026,9,1)))
    def test_january_rollover(self): self.assertEqual(previous_month(datetime(2027,1,1,tzinfo=timezone.utc)),(date(2026,12,1),date(2027,1,1)))
    def test_brisbane_boundary_not_utc_boundary(self): self.assertEqual(previous_month(datetime(2026,8,31,14,tzinfo=timezone.utc)),(date(2026,8,1),date(2026,9,1)))
    def test_before_brisbane_boundary(self): self.assertEqual(previous_month(datetime(2026,8,31,13,59,tzinfo=timezone.utc)),(date(2026,7,1),date(2026,8,1)))
    def test_reject_naive_timestamp(self):
        with self.assertRaises(ValueError): previous_month(datetime(2026,9,1))

class RetrievalContractTests(unittest.TestCase):
    def payload(self,ids,count=None,**kwargs): return {'esearchresult':{'count':str(len(ids) if count is None else count),'idlist':ids,**kwargs}}
    def test_valid_search(self): self.assertEqual(reconcile_search(self.payload(['100','101']))[0],['100','101'])
    def test_true_zero_is_valid(self): self.assertEqual(reconcile_search(self.payload([])),([],{}))
    def test_phrase_not_found_retained_as_warning(self): self.assertIn('phrasesnotfound',reconcile_search(self.payload([],errorlist={'phrasesnotfound':['Rare facility']}))[1])
    def test_invalid_field_is_fatal(self):
        with self.assertRaises(ValueError): reconcile_search(self.payload([],errorlist={'fieldsnotfound':['Affiliaton']}))
    def test_missing_search_fails(self):
        with self.assertRaises(ValueError): reconcile_search({})
    def test_error_payload_fails(self):
        with self.assertRaises(ValueError): reconcile_search({'error':'API rate limit'})
    def test_truncated_ids_fails(self):
        with self.assertRaises(ValueError): reconcile_search(self.payload(['100'],2))
    def test_duplicate_ids_fails(self):
        with self.assertRaises(ValueError): reconcile_search(self.payload(['100','100'],1))
    def test_over_10000_fails(self):
        with self.assertRaises(ValueError): reconcile_search(self.payload([],10001))
    def test_summary_all_present(self): self.assertEqual(len(reconcile_summary(['100'],{'result':{'uids':['100'],'100':{'uid':'100'}}})),1)
    def test_summary_missing_pmid_fails(self):
        with self.assertRaises(ValueError): reconcile_summary(['100','101'],{'result':{'uids':['100'],'100':{'uid':'100'}}})
    def test_summary_uid_mismatch_fails(self):
        with self.assertRaises(ValueError): reconcile_summary(['100'],{'result':{'uids':['100'],'100':{'uid':'200'}}})
    def test_summary_record_error_fails(self):
        with self.assertRaises(ValueError): reconcile_summary(['100'],{'result':{'uids':['100'],'100':{'uid':'100','error':'Unavailable'}}})
    def test_multi_facility_no_double_count(self):
        ids,pairs=facility_union({'Cairns':['100','101','100'],'Atherton':['100']})
        self.assertEqual((len(ids),len(pairs)),(2,3))


class CanonicalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pubmed=json.loads((ROOT/'tests/fixtures/pubmed-publications-synthetic.json').read_text())
        cls.dora=json.loads((ROOT/'tests/fixtures/dora-publications-synthetic.json').read_text())
        cls.rows=reconcile_sources(cls.pubmed,cls.dora)
    def test_title_only_fixture_requires_review(self):
        self.assertEqual(sum(r['SourceSet']=='PubMed; DORA' for r in self.rows),0)
        self.assertEqual(len(self.rows),len(self.pubmed)+len(self.dora))
    def test_dora_only_retained(self):
        self.assertTrue(any(r['SourceSet']=='DORA' and r['DedupMethod']=='DORA-only' for r in self.rows))
    def test_ambiguous_not_silently_merged(self):
        row=next(r for r in self.rows if r.get('DORAKey','').endswith('/3'))
        self.assertEqual((row['DedupMethod'],row['CandidateCount']),('ambiguous-title+year',2))
    def test_normalization_ignores_punctuation_case(self):
        self.assertEqual(normalize_title('A Study: Cairns!'),normalize_title('a study cairns'))
    def test_fixture_is_synthetic(self):
        text=(ROOT/'tests/fixtures/dora-rss-synthetic.xml').read_text()
        self.assertIn('Synthetic test abstract only',text)
        self.assertNotIn('Assessing Cognitive Communication Disorders',text)

class StaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.model=json.loads((ROOT/'audit/model.snapshot.json').read_text())['model']
    def test_m_quote_escaping(self): self.assertEqual(m_text('"Cairns Hospital"[Affiliation]'),'"""Cairns Hospital""[Affiliation]"')
    def test_m_control_escaping(self): self.assertEqual(m_text('a\nb'),'"a#(lf)b"')
    def test_m_valid_nested_syntax(self): self.assertEqual(m_lexical_errors('let T=#table({"A"},{{"a""b"}}) in T'),[])
    def test_m_broken_delimiter_caught(self): self.assertTrue(m_lexical_errors('let T={1,2] in T'))
    def test_m_unclosed_string_caught(self): self.assertTrue(m_lexical_errors('let X="abc'))
    def test_m_backslash_quote_caught(self): self.assertTrue(m_lexical_errors('let X="a\\"b" in X'))
    def test_valid_visual_reference(self): self.assertEqual(reference_errors({'Column':{'Expression':{'SourceRef':{'Entity':'Publication'}},'Property':'PMID'}},self.model),[])
    def test_old_employee_reference_caught(self): self.assertTrue(reference_errors({'Column':{'Expression':{'SourceRef':{'Entity':'Employee'}},'Property':'EmplID'}},self.model))
    def test_renamed_missing_column_caught(self): self.assertTrue(reference_errors({'Column':{'Expression':{'SourceRef':{'Entity':'Publication'}},'Property':'EmployeeID'}},self.model))
    def test_nested_legacy_json_expanded(self):
        obj=expand({'config':json.dumps({'inner':json.dumps({'label':'New Hires'})})})
        self.assertIn('New Hires',json.dumps(obj))
        self.assertTrue(any('New Hires' in str(item) for item in strings(obj)))
    def test_audit_proves_unchanged_binary(self):
        audit=json.loads((ROOT/'audit/source-audit.json').read_text());self.assertTrue(audit['data_model_identical'])
        self.assertEqual(audit['original']['entries']['DataModel'],audit['adapted']['entries']['DataModel'])
    def test_all_local_gates_pass(self): self.assertEqual(validate(ROOT)['status'],'PASS')
    def test_hidden_filter_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ['powerbi','config','powerquery']: shutil.copytree(ROOT/folder,root/folder)
            file=next((root/'powerbi').rglob('visual.json'));obj=json.loads(file.read_text());obj['filterConfig']={'filters':[{'name':'legacy','filter':{'value':'2014L'}}]};file.write_text(json.dumps(obj))
            self.assertEqual(validate(root)['status'],'FAIL')
    def test_old_cache_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ['powerbi','config','powerquery']: shutil.copytree(ROOT/folder,root/folder)
            (root/'powerbi/DataModel').write_text('old data cache')
            self.assertEqual(validate(root)['status'],'FAIL')
    def test_native_acceptance_not_falsely_closed(self):
        meta=json.loads((ROOT/'conductor/tracks/T05_native_acceptance/metadata.json').read_text());self.assertNotEqual(meta['status'],'completed')
    def test_full_schema_validation_not_claimed(self): self.assertIn('NOT the native',validate(ROOT)['validation_scope'])
    def test_no_employment_sources_in_project(self): self.assertNotIn('Sql.Database',json.dumps(self.model))

if __name__=='__main__': unittest.main()
