import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_pubmed import Collector, validate_config


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def collector(self, responses):
        c = Collector(self.folder)
        responses = iter(responses)
        c.request = lambda *args: json.dumps({'esearchresult': next(responses)}).encode()
        return c

    def test_duplicate_search_ids_rejected(self):
        c = self.collector([{'count': '1', 'idlist': ['123', '123']}])
        with self.assertRaises(ValueError):
            c.ids('test', dt.date(2024, 1, 1), dt.date(2024, 1, 1))

    def test_split_parent_mismatch_rejected(self):
        c = self.collector([{'count': '10000', 'idlist': []},
                            {'count': '1', 'idlist': ['123']},
                            {'count': '0', 'idlist': []}])
        with self.assertRaises(ValueError):
            c.ids('test', dt.date(2024, 1, 1), dt.date(2024, 1, 2))

    def test_invalid_search_id_rejected(self):
        for value in ['abc', '', '-1', '0', '01']:
            c = self.collector([{'count': '1', 'idlist': [value]}])
            with self.assertRaises(ValueError):
                c.ids('test', dt.date(2024, 1, 1), dt.date(2024, 1, 1))

    def test_successful_empty_search(self):
        c = self.collector([{'count': '0', 'idlist': []}])
        self.assertEqual(c.collect('test', dt.date(2024, 1, 1), dt.date(2024, 1, 1)), [])

    def test_valid_split_uses_configured_limit(self):
        c = self.collector([{'count': '3', 'idlist': ['1', '2']},
                            {'count': '2', 'idlist': ['1', '2']},
                            {'count': '1', 'idlist': ['3']}])
        c.limit = 2
        self.assertEqual(c.ids('test', dt.date(2024, 1, 1), dt.date(2024, 1, 2)), {'1', '2', '3'})

    def test_disabled_or_unsafe_configuration_rejected(self):
        for settings in [{'enabled': False, 'query': 'x'},
                         {'enabled': True, 'query': 'x', 'max_requests_per_second': 4},
                         {'enabled': True, 'query': 'x', 'api_base': 'http://example.com'},
                         {'enabled': True, 'query': 'x', 'fetch_batch_size': True}]:
            with self.assertRaises(ValueError):
                validate_config({'pubmed': settings})

    def test_resume_reads_verified_archive_without_network(self):
        c = Collector(self.folder, limiter=Mock())
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'archive'
        with patch('collect_pubmed.urllib.request.urlopen', return_value=response) as network:
            self.assertEqual(c.request('esearch.fcgi', {'term': 'x'}), b'archive')
            receipt = json.loads((self.folder / 'manifest.json').read_text())
            resumed = Collector(self.folder, receipt=receipt)
            self.assertEqual(resumed.request('esearch.fcgi', {'term': 'x'}), b'archive')
            self.assertEqual(network.call_count, 1)

    def test_corrupt_archive_stops_resume(self):
        (self.folder / 'response').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            Collector(self.folder, receipt={'files': [{'file': 'response', 'sha256': '0' * 64}]})

    def test_path_traversal_stops_resume(self):
        with self.assertRaises(ValueError):
            Collector(self.folder, receipt={'files': [{'file': '../response', 'sha256': '0' * 64}]})


if __name__ == '__main__':
    unittest.main()
