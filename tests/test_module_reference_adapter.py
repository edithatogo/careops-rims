import copy
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from module_reference_adapter import prepare, digest, SOURCES
spec = importlib.util.spec_from_file_location('fictional_reference_consumer', ROOT / 'examples/module-reference-demo/consumer.py')
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


class OptionalReferenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/module-reference-demo/input.json').read_text())
        self.allowed = {tuple(k) for k in self.data['allowed_keys']}
        self.state = {'case': {'CaseKey': 'fictional-case-1', 'Status': 'Draft'}}

    def packet(self):
        return prepare(self.data['snapshot'], self.data['context'], self.allowed)

    def test_standalone_and_explicit_uncertainty(self):
        before = copy.deepcopy(self.data)
        self.assertEqual(consumer.view(self.state, self.allowed)['references'], [])
        packet = self.packet()
        publication = next(r for r in packet['references'] if r['kind'] == 'publication')
        self.assertEqual(publication['id'], self.data['snapshot']['publications'][0]['CanonicalKey'])
        self.assertEqual(publication['links'][0]['status'], 'review-required')
        self.assertEqual(publication['links'][0]['confidence'], 'unknown')
        self.assertEqual(self.data, before)

    def test_permissions_before_export_and_after_cache(self):
        with self.assertRaises(PermissionError):
            prepare(self.data['snapshot'], self.data['context'], set())
        saved = consumer.receive(self.state, self.packet())
        visible = consumer.view(saved, {(SOURCES['publication'], 'fictional:publication:1')})
        self.assertEqual(len(visible['references']), 1)
        self.assertEqual(visible['references'][0]['links'], [])
        self.assertEqual(consumer.view(saved, set())['case'], self.state['case'])

    def test_unchanged_replay_and_changed_attempt_id(self):
        packet = self.packet()
        saved = consumer.receive(self.state, packet)
        self.assertEqual(saved, consumer.receive(saved, packet))
        self.data['context']['correlation_id'] = 'fictional-attempt-2'
        self.assertEqual(packet['idempotency_key'], self.packet()['idempotency_key'])

    def test_conflict_and_revision_changes_are_atomic(self):
        saved = consumer.receive(self.state, self.packet())
        before = copy.deepcopy(saved)
        for field in ['label', 'revision']:
            packet = self.packet()
            packet['references'][-1][field] += '-changed'
            packet['idempotency_key'] = digest({k: v for k, v in packet.items() if k not in {'correlation_id', 'idempotency_key'}})
            with self.assertRaises(ValueError):
                consumer.receive(saved, packet)
            self.assertEqual(saved, before)

    def test_outage_retains_last_good_and_labels_stale(self):
        saved = consumer.receive(self.state, self.packet())
        outage = consumer.view(consumer.receive(saved, None), self.allowed)
        self.assertEqual(outage['references'], consumer.view(saved, self.allowed)['references'])
        self.assertIn('stale', outage['integration_status'])

    def test_source_qualified_ids_do_not_collide(self):
        self.data['snapshot']['publications'][0]['CanonicalKey'] = 'fictional:org:1'
        self.allowed.add((SOURCES['publication'], 'fictional:org:1'))
        saved = consumer.receive(self.state, self.packet())
        self.assertEqual(len(saved['references']), 2)

    def test_unknown_version_and_bad_integrity_refused(self):
        packet = self.packet()
        packet['contract'] = 'careops-rims.references/2'
        with self.assertRaises(ValueError):
            consumer.receive(self.state, packet)
        packet = self.packet()
        packet['references'][0]['label'] = 'tampered'
        with self.assertRaises(ValueError):
            consumer.receive(self.state, packet)

    def test_missing_org_or_version_does_not_infer_association(self):
        for mutation in ['missing', 'version']:
            data = copy.deepcopy(self.data)
            if mutation == 'missing':
                data['snapshot']['organisation_reference']['units'] = []
            else:
                data['snapshot']['publications'][0]['OrganisationReferenceVersion'] = 'other-v1'
            packet = prepare(data['snapshot'], data['context'], self.allowed)
            publication = next(r for r in packet['references'] if r['kind'] == 'publication')
            self.assertEqual(publication['links_state'], 'unresolved_reference')
            self.assertEqual(publication['links'], [])

    def test_unknown_fields_unsafe_urls_and_provider_version_refused(self):
        for mutation in ['field', 'url', 'provider']:
            packet = self.packet()
            if mutation == 'field':
                packet['references'][0]['raw_payload'] = 'not minimum necessary'
            elif mutation == 'url':
                packet['references'][0]['evidence_url'] = 'https://example.invalid/path?token=secret'
            else:
                packet['provider_version'] = '2'
            packet['idempotency_key'] = digest({k: v for k, v in packet.items() if k not in {'correlation_id', 'idempotency_key'}})
            with self.assertRaises(ValueError):
                consumer.receive(self.state, packet)

    def test_consumer_standalone_in_isolated_interpreter(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'consumer.py'
            path.write_bytes((ROOT / 'examples/module-reference-demo/consumer.py').read_bytes())
            code = "import runpy,json; m=runpy.run_path(%r); print(json.dumps(m['view']({'case': {'CaseKey':'fictional-independent'}},set())))" % str(path)
            run = subprocess.run([sys.executable, '-I', '-c', code], cwd=folder,
                                 text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(run.stdout)['case']['CaseKey'], 'fictional-independent')
            self.assertEqual(json.loads(run.stdout)['references'], [])

    def test_duplicate_or_padded_ids_and_oversize_refused(self):
        for key in ['CanonicalKey', 'OrganisationKeys']:
            data = copy.deepcopy(self.data)
            data['snapshot']['publications'][0][key] += ' '
            with self.assertRaises(ValueError):
                prepare(data['snapshot'], data['context'], self.allowed)
        data = copy.deepcopy(self.data)
        data['snapshot']['publications'][0]['OrganisationKeys'] = 0
        with self.assertRaises(ValueError):
            prepare(data['snapshot'], data['context'], self.allowed)
        self.data['snapshot']['publications'] *= 51
        with self.assertRaises(ValueError):
            self.packet()


if __name__ == '__main__':
    unittest.main()
