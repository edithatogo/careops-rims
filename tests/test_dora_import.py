from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_dora import parse_feed

ITEM = '''<item><title>Synthetic article</title><link>https://dora.health.qld.gov.au/qldresearchjspui/handle/1/test</link>
<description>Title: Synthetic article
Authors: Person, A; Person, B
Abstract: Synthetic abstract
Description: CHHHS affiliated author: Person, A</description><pubDate>Thu, 01 Jan 2026 00:00:00 GMT</pubDate></item>'''

class DoraTests(unittest.TestCase):
    def test_empty_feed_is_success(self):
        self.assertEqual(parse_feed(b'<rss><channel/></rss>'), [])

    def test_missing_channel_is_failure(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<rss/>')

    def test_date_stays_unverified_and_affiliation_is_preserved(self):
        row = parse_feed(('<rss><channel>' + ITEM + '</channel></rss>').encode())[0]
        self.assertEqual(row['publication_date_parts'], {})
        self.assertEqual(row['date_basis'], 'rss_unverified')
        self.assertEqual(len(row['authors']), 2)
        self.assertIn('CHHHS affiliated', row['attribution_evidence'])
        self.assertNotIn('abstract', row)

    def test_duplicate_feed_identity_is_failure(self):
        with self.assertRaises(ValueError):
            parse_feed(('<rss><channel>' + ITEM * 2 + '</channel></rss>').encode())
