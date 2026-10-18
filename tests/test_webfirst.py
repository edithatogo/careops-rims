"""Adversarial policy tests; deliberately not native Power BI execution."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from webfirst_contracts import (CAPABILITIES, choose_route, fallback_errors, isolation_errors,
                               live_evidence_errors, local_validate, runtime_hashes)
from export_publication_register import (EXPORT_FIELDS, export_errors, key_hash,
                                         render_exports, safe_cell, safe_link, verify_written_exports)
from deploy_canonical_report import validate_deployment_target


def good_capabilities():
    return {'permission_denied': False, 'capabilities': [
        {'operation': op, 'provider': 'plugin', 'status': 'verified',
         'evidence_ref': 'private/ops/discovery/observations.json#' + op}
        for op in CAPABILITIES]}


def uid(name):
    return str(uuid5(NAMESPACE_URL, 'https://example.invalid/' + name))


def good_isolation():
    return {'tenant_id': uid('tenant'), 'workspace_id': uid('workspace'),
            'original_report_id': uid('original-report'), 'original_model_id': uid('original-model'),
            'development_report_id': uid('development-report'), 'development_model_id': uid('development-model'),
            'dependency_inventory_complete': True, 'recovery_verified': True,
            'baseline_unchanged': True, 'canary_roundtrip_verified': True}


def good_fallback():
    return {'reason': 'unsupported_web_power_query_operation', 'webui_attempted': True,
            'blocker_confirmed': True, 'permissions_ok': True, 'owner_approved': True,
            'evidence_refs': ['private/ops/web-blocker.json']}


def example_envelope():
    return json.loads((ROOT/'tests/fixtures/webfirst-export-synthetic.json').read_text())


class RoutePolicyTests(unittest.TestCase):
    def test_complete_plugin_is_web_route_not_live_acceptance(self):
        r = choose_route(good_capabilities())
        self.assertEqual(r['route'], 'web_first')
        self.assertFalse(r['live_acceptance'])

    def test_read_only_plugin_does_not_prove_authoring(self):
        d=good_capabilities();d['capabilities']=[x for x in d['capabilities'] if x['operation'].startswith('read_')]
        self.assertEqual(choose_route(d)['route'], 'needs_capability_verification')

    def test_web_ui_can_supply_missing_plugin_operation(self):
        d=good_capabilities();d['capabilities'][0]['provider']='webui'
        self.assertEqual(choose_route(d)['route'], 'web_first')

    def test_declared_available_is_not_verified_write(self):
        d=good_capabilities();d['capabilities'][0]['status']='available'
        self.assertIn(d['capabilities'][0]['operation'],choose_route(d)['unverified_operations'])

    def test_permission_denial_blocks_even_with_tools(self):
        d=good_capabilities();d['permission_denied']=True
        self.assertEqual(choose_route(d)['route'],'blocked_permissions')

    def test_absent_connector_is_not_fallback(self):
        r=choose_route({'capabilities': []})
        self.assertEqual(r['route'],'needs_capability_verification')
        self.assertFalse(r['fallback_authorised'])

    def test_unsubstantiated_verified_claim_is_not_verified(self):
        d=good_capabilities();d['capabilities'][0]['evidence_ref']=''
        self.assertEqual(choose_route(d)['route'],'needs_capability_verification')

    def test_unknown_provider_does_not_pass(self):
        d=good_capabilities();d['capabilities'][0]['provider']='imagined_api'
        self.assertEqual(choose_route(d)['route'],'needs_capability_verification')

    def test_canonical_report_deployment_route_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'canonical/shared report deployment is disabled'):
            validate_deployment_target(str(uuid5(NAMESPACE_URL, 'workspace')), str(uuid5(NAMESPACE_URL, 'report')), 'canonical')
        with self.assertRaisesRegex(ValueError, 'concrete isolated'):
            validate_deployment_target('{{WORKSPACE_ID}}', '{{REPORT_ID}}', 'isolated')


class IsolationPolicyTests(unittest.TestCase):
    def test_distinct_models_with_recovery(self):
        self.assertEqual(isolation_errors(good_isolation()),[])

    def test_copy_of_report_still_shares_model(self):
        d=good_isolation();d['development_model_id']=d['original_model_id']
        self.assertTrue(isolation_errors(d))

    def test_original_report_is_not_a_development_copy(self):
        d=good_isolation();d['development_report_id']=d['original_report_id']
        self.assertTrue(isolation_errors(d))

    def test_no_recovery(self):
        d=good_isolation();d['recovery_verified']=False
        self.assertTrue(isolation_errors(d))

    def test_changed_baseline(self):
        d=good_isolation();d['baseline_unchanged']=False
        self.assertTrue(isolation_errors(d))

    def test_display_names_not_ids(self):
        d=good_isolation();d['original_model_id']='CHHHS'
        self.assertTrue(isolation_errors(d))

    def test_strings_are_not_boolean_proof(self):
        d=good_isolation();d['recovery_verified']='true'
        self.assertTrue(isolation_errors(d))


class FallbackPolicyTests(unittest.TestCase):
    def test_confirmed_technical_blocker_can_be_reviewed(self):
        self.assertEqual(fallback_errors(good_fallback()),[])

    def test_absent_plugin_does_not_activate_vm(self):
        d=good_fallback();d['reason']='plugin_not_exposed_in_this_chat'
        self.assertTrue(fallback_errors(d))

    def test_permission_cannot_be_bypassed(self):
        d=good_fallback();d['reason']='permission_denied'
        self.assertTrue(fallback_errors(d))

    def test_no_actual_web_attempt(self):
        d=good_fallback();d['webui_attempted']=False
        self.assertTrue(fallback_errors(d))

    def test_owner_approval_required(self):
        d=good_fallback();d['owner_approved']=False
        self.assertTrue(fallback_errors(d))

    def test_no_pbix_download_is_not_web_authoring_failure(self):
        d=good_fallback();d['reason']='pbix_download_unavailable_only'
        self.assertTrue(fallback_errors(d))


class ExportPolicyTests(unittest.TestCase):
    def test_complete_fixture(self):
        self.assertEqual(export_errors(example_envelope()),[])

    def test_dora_only_included_without_pmid(self):
        d=example_envelope();self.assertTrue(any(r['SourceSet']=='DORA' and not r['PMID'] for r in d['records']))
        self.assertEqual(export_errors(d),[])

    def test_row_truncation_rejected(self):
        d=example_envelope();d['records']=d['records'][:-1]
        self.assertTrue(export_errors(d))

    def test_equal_count_wrong_keys_rejected(self):
        d=example_envelope();d['records'][0]['CanonicalKey']='TEST:DIFFERENT'
        self.assertTrue(export_errors(d))

    def test_duplicate_key_rejected(self):
        d=example_envelope();d['records'][1]['CanonicalKey']=d['records'][0]['CanonicalKey']
        d['expected_key_sha256']=key_hash(d['records'])
        self.assertTrue(export_errors(d))

    def test_unallocated_date_must_not_get_january(self):
        d=example_envelope();r=next(x for x in d['records'] if x['PublicationDatePrecision']=='rss_unverified')
        r['PublicationMonth']='2026-01'
        self.assertTrue(export_errors(d))

    def test_unknown_precision_rejected(self):
        d=example_envelope();d['records'][0]['PublicationDatePrecision']='approximate'
        self.assertTrue(export_errors(d))

    def test_extra_workforce_column_rejected(self):
        d=example_envelope();d['records'][0]['Employee']='hidden legacy'
        self.assertTrue(export_errors(d))

    def test_fixture_cannot_be_declared_live(self):
        d=example_envelope();d['data_kind']='live_export'
        self.assertTrue(export_errors(d))

    def test_missing_source_coverage_note_rejected(self):
        d=example_envelope();d['coverage_note']=''
        self.assertTrue(export_errors(d))

    def test_formula_safety(self):
        for s in ['=1+1','+SUM(A1:A2)','-cmd','@SUM(A1:A2)','\t=1','  =1']:
            self.assertTrue(safe_cell(s).startswith("'"))

    def test_normal_text_unchanged(self):
        self.assertEqual(safe_cell('A complete article title'),'A complete article title')

    def test_active_links_blocked(self):
        self.assertIsNone(safe_link('javascript:alert(1)'))
        self.assertIsNone(safe_link('https://evil.invalid'))
        self.assertIsNone(safe_link('https://pubmed.ncbi.nlm.nih.gov@evil.invalid/a'))

    def test_valid_source_link(self):
        self.assertIsNotNone(safe_link('https://pubmed.ncbi.nlm.nih.gov/12345/'))

    def test_complete_html_and_csv_not_first_screen(self):
        d=example_envelope()
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export';render_exports(d,dest)
            with (dest/'publications.csv').open(newline='',encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f))
            html=(dest/'publications.html').read_text()
            self.assertEqual(len(rows),len(d['records']))
            self.assertEqual(html.count('<article '),len(d['records']))
            self.assertIn('SYNTHETIC TEST DATA',html)
            self.assertEqual(list(rows[0]),EXPORT_FIELDS)

    def test_html_escape(self):
        d=example_envelope();d['records'][0]['Title']='<script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export';render_exports(d,dest)
            html=(dest/'publications.html').read_text()
            self.assertNotIn('<script>',html)
            self.assertIn('&lt;script&gt;',html)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export';dest.mkdir()
            with self.assertRaises(FileExistsError):render_exports(example_envelope(),dest)

    def test_all_fields_survive_long_unicode_metadata(self):
        d=example_envelope()
        d['records'][0]['AttributionEvidence']='研究 & <evidence>\n' * 5000
        d['records'][0]['MatchedFacilities']='=formula-like value'
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export'
            receipt=render_exports(d,dest)
            self.assertTrue(receipt['csv_and_html_all_fields_readback_verified'])
            verify_written_exports(d['records'],dest)

    def test_html_field_loss_detected_even_with_same_keys(self):
        d=example_envelope()
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export';render_exports(d,dest)
            p=dest/'publications.html'
            p.write_text(p.read_text().replace('data-field="Authors"','data-field="MissingAuthors"',1))
            with self.assertRaisesRegex(ValueError,'HTML content'):
                verify_written_exports(d['records'],dest)

    def test_csv_field_loss_detected_even_with_same_keys(self):
        d=example_envelope()
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'export';render_exports(d,dest)
            p=dest/'publications.csv'
            with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
            rows[0]['Authors']='truncated'
            with p.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=EXPORT_FIELDS);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'CSV content'):
                verify_written_exports(d['records'],dest)

    def test_monthly_scope_excludes_unknown_month(self):
        d=example_envelope();d['scope']={'mode':'month','reporting_month':'2026-08'}
        self.assertTrue(export_errors(d))

    def test_valid_monthly_subset(self):
        d=example_envelope();d['scope']={'mode':'month','reporting_month':'2026-08'}
        d['records']=[r for r in d['records'] if r['PublicationMonth']=='2026-08']
        d['expected_canonical_count']=len(d['records']);d['expected_key_sha256']=key_hash(d['records'])
        self.assertEqual(export_errors(d),[])

    def test_empty_export_supported(self):
        d=example_envelope();d['records']=[];d['expected_canonical_count']=0;d['expected_key_sha256']=key_hash([])
        self.assertEqual(export_errors(d),[])


class LiveEvidenceTests(unittest.TestCase):
    def evidence_case(self, directory):
        from webfirst_contracts import LIVE_CHECKS
        payload = Path(directory)/'receipt.json';payload.write_text('{"kind":"test of receipt structure only"}')
        target={'tenant_id':uid('t'),'workspace_id':uid('w'),'report_id':uid('r'),'model_id':uid('m')}
        return {'data_kind':'live_powerbi','target':target,'refresh_run_id':'test-run-structure',
                'started_at_utc':'2026-09-12T03:00:00+00:00','finished_at_utc':'2026-09-12T04:00:00+00:00',
                'contract_sha256':hashlib.sha256((ROOT/'contracts/web-first-execution.contract.json').read_bytes()).hexdigest(),
                'source_health':{'PubMed':'success','DORA':'success'},
                'artifacts':[{'id':'all','path':'receipt.json','sha256':hashlib.sha256(payload.read_bytes()).hexdigest(),
                              'target':target,'refresh_run_id':'test-run-structure','captured_at_utc':'2026-09-12T03:30:00+00:00'}],
                'checks':{name:{'status':'pass','artifact_id':'all'} for name in LIVE_CHECKS}}

    def test_structural_receipt_can_pass_without_certifying_its_truth(self):
        # The checker verifies structure/integrity only; authorised source review remains mandatory.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(live_evidence_errors(self.evidence_case(tmp),Path(tmp)),[])

    def test_bad_evidence_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['artifacts'][0]['sha256']='0'*64
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_wrong_live_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['artifacts'][0]['target']=dict(d['target'],model_id=uid('other'))
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_wrong_refresh_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['artifacts'][0]['refresh_run_id']='old-run'
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_stale_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['artifacts'][0]['captured_at_utc']='2026-08-12T03:00:00+00:00'
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_naive_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['artifacts'][0]['captured_at_utc']='2026-09-12T03:30:00'
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_stale_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['contract_sha256']='0'*64
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_a_source_failure_blocks_native_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.evidence_case(tmp);d['source_health']['DORA']='failure'
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_blank_template_fails_closed(self):
        d=json.loads((ROOT/'config/live-evidence.template.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(live_evidence_errors(d,Path(tmp)))

    def test_local_fixtures_cannot_be_native_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(live_evidence_errors({'data_kind':'synthetic'},Path(tmp)))

    def test_path_escape_rejected(self):
        d=json.loads((ROOT/'config/live-evidence.template.json').read_text())
        d['artifacts']=[{'id':'escape','path':'../outside.json','sha256':'0'*64}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(any('path' in e.lower() for e in live_evidence_errors(d,Path(tmp))))


class LocalManifestTests(unittest.TestCase):
    def test_current_local_package(self):
        result=local_validate(ROOT)
        self.assertEqual(result['errors'],[])
        self.assertFalse(result['native_acceptance'])

    def test_runtime_hashes_not_empty(self):
        self.assertGreater(len(runtime_hashes(ROOT)),30)

    def test_extra_runtime_page_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target=Path(tmp)/'repo'
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','__pycache__','.agents'))
            p=target/'powerbi/unexpected-page.json';p.write_text('{}')
            self.assertTrue(local_validate(target)['errors'])

    def test_contract_requires_native_grants_page_scope(self):
        d=json.loads((ROOT/'contracts/web-first-execution.contract.json').read_text())
        self.assertEqual(d['required_pages'], [
            'CHHHS Publications', 'Monthly Publications',
            'Source Reconciliation', 'Clinical Analytics', 'Funding Opportunities',
            'Funding Calendar', 'My Funding Watchlist'])
        self.assertFalse(d['local_validation_is_native_acceptance'])


class RetainedProjectionPayloadTests(unittest.TestCase):
    def test_retained_reader_parameters_are_explicit_and_fail_closed(self):
        payload=(ROOT/'config/native-retained-parameters.tmdl').read_text()
        self.assertIn('expression pRetainedSiteUrl = ""',payload)
        self.assertIn('expression pRetainedArchiveFolderUrl = ""',payload)
        self.assertIn('IsParameterQueryRequired=true',payload)

    def test_payload_is_additive_and_uses_retained_readers(self):
        payload=(ROOT/'config/native-retained-projections.tmdl').read_text()
        dora=(ROOT/'config/native-retained-dora-projection.tmdl').read_text()
        self.assertIn('createOrReplace',payload)
        self.assertIn('table RetainedPubMedPublications',payload)
        self.assertIn('partition RetainedPubMedPublications = m',payload)
        self.assertIn('createOrReplace',dora)
        self.assertIn('table RetainedDoraPublications',dora)
        self.assertIn('partition RetainedDoraPublications = m',dora)
        self.assertIn('fnParseRetainedDoraMetadata(RetainedSourceObservations)',dora)
        self.assertIn('fnReadRetainedPublicationRows(RetainedArchiveFiles, RetainedSourceObservations, "PubMed")',payload)
        self.assertNotIn('table PubMedPublications',payload)
        self.assertNotIn('table DoraHistoricalMetadata',payload)

    def test_dora_archive_fallback_preserves_table_shapes(self):
        payload=(ROOT/'config/native-dora-archive-partitions.tmdl').read_text()
        self.assertIn('ref table DoraSourceObservations',payload)
        self.assertIn('ref table DoraHarvest',payload)
        self.assertIn('ref table DoraPublications',payload)
        self.assertIn('fnParseRetainedDoraMetadata(RetainedSourceObservations)',payload)
        self.assertNotIn('\n  table DoraPublications\n',payload)

    def test_canonical_retained_partition_is_isolated_and_reference_only(self):
        payload=(ROOT/'config/native-canonical-retained-partitions.tmdl').read_text()
        self.assertIn('Apply only to the isolated development model',payload)
        self.assertIn('ref table PubMedPublications',payload)
        self.assertIn('ref table DoraPublications',payload)
        self.assertIn('source = RetainedPubMedPublications',payload)
        self.assertIn('source = RetainedDoraPublications',payload)
        self.assertNotIn('\n  table PubMedPublications\n',payload)
        self.assertNotIn('\n  table DoraPublications\n',payload)

if __name__=='__main__':unittest.main()
