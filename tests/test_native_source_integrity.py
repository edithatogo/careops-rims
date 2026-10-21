import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_native_source_integrity import packet_contract, verify_payload


class NativeSourceIntegrityTests(unittest.TestCase):
    def packet(self, folder):
        raw = b'{"id":"qualified"}'
        entry = {'name': 'record.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        rule = json.dumps({'source_files': [entry]}).encode()
        manifest = {'batch': '00000000-0000-4000-8000-000000000001', 'complete': True,
            'files': [entry, {'name': 'rule-authority.json', 'sha256': hashlib.sha256(rule).hexdigest(), 'bytes': len(rule)}]}
        (folder / 'record.json').write_bytes(raw)
        (folder / 'rule-authority.json').write_bytes(rule)
        (folder / 'manifest.json').write_text(json.dumps(manifest))
        return raw, manifest['batch'], hashlib.sha256(rule).hexdigest()

    def test_every_byte_is_checked_including_same_length_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); raw, batch, pin = self.packet(folder)
            url = 'https://tenant.sharepoint.com/sites/test/Documents/award-crosswalk-' + batch
            contract = packet_contract(folder, url, expected_batch=batch, expected_rule_sha256=pin)
            self.assertEqual(verify_payload(contract, url+'/record.json', raw), raw)
            tampered = raw.replace(b'qualified', b'falsified')
            self.assertEqual(len(raw), len(tampered))
            with self.assertRaises(ValueError):
                verify_payload(contract, url+'/record.json', tampered)
            with self.assertRaises(KeyError):
                verify_payload(contract, url+'/unknown.json', raw)

    def test_rehashed_mutable_manifest_cannot_repin_independent_rule(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); raw, batch, pin = self.packet(folder)
            changed = raw.replace(b'qualified', b'falsified')
            (folder/'record.json').write_bytes(changed)
            m=json.loads((folder/'manifest.json').read_text());m['files'][0]['sha256']=hashlib.sha256(changed).hexdigest()
            (folder/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):
                packet_contract(folder, 'https://tenant.sharepoint.com/Documents/award-crosswalk-'+batch,
                    expected_batch=batch, expected_rule_sha256=pin)

    def test_batch_and_rule_pins_are_independent_required_identities(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); _, batch, pin = self.packet(folder)
            url = 'https://tenant.sharepoint.com/Documents/award-crosswalk-'+batch
            for bad in [None, '', ' ', 123, ' '+batch]:
                with self.assertRaises(ValueError):
                    packet_contract(folder,url,expected_batch=bad,expected_rule_sha256=pin)
            with self.assertRaises(ValueError):
                packet_contract(folder,url,expected_batch=batch,expected_rule_sha256='0'*64)
