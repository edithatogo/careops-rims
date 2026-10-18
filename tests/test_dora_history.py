from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_dora_history import Page, parse_record

class HistoryTests(unittest.TestCase):
    def body(self, fields):
        return ('<table class="itemDisplayTable">' + ''.join('<tr><td>'+k+'</td><td>'+v+'</td></tr>' for k,v in fields) + '</table>').encode()
    def test_explicit_metadata_only_and_year_precision(self):
        url='https://dora.health.qld.gov.au/qldresearchjspui/handle/1/7'
        row=parse_record(self.body([('dc.title','Synthetic title'),('dc.identifier.uri',url),('dc.date.issued','2024'),('dc.identifier.pmid','123'),('dc.description','Affiliated author: A'),('dc.description.abstract','Do not retain')]),url)
        self.assertEqual(row['publication_date_parts'],{'Year':'2024'})
        self.assertEqual(row['pmid'],'123')
        self.assertNotIn('Do not retain',str(row))
    def test_legacy_http_handle_requires_same_item(self):
        url='https://dora.health.qld.gov.au/qldresearchjspui/handle/1/7'
        body=self.body([('dc.title','Synthetic'),('dc.identifier.uri',url.replace('https:','http:'))])
        self.assertEqual(parse_record(body,url)['url'],url)
        with self.assertRaises(ValueError):parse_record(body,url+'8')

    def test_identity_and_conflicting_identifiers_fail(self):
        for fields in [[('dc.title','A')],[('dc.title','A'),('dc.identifier.uri','u'),('dc.identifier.pmid','1'),('dc.identifier.pmid','2')]]:
            with self.assertRaises(ValueError):parse_record(self.body(fields),'u')
    def test_index_ignores_navigation_and_pdf(self):
        p=Page();p.feed('<a href="/qldresearchjspui/handle/1/849">Collection</a><table summary="This table browses all dspace content"><a href="/qldresearchjspui/handle/1/7">Item</a></table>')
        self.assertEqual(p.items,['https://dora.health.qld.gov.au/qldresearchjspui/handle/1/7'])

class CollectionTests(unittest.TestCase):
    def test_full_collection_count_and_archive_integrity(self):
        import io,json,tempfile
        from unittest.mock import patch
        from collect_dora_history import collect,COLLECTION
        url='https://dora.health.qld.gov.au/qldresearchjspui/handle/1/7'
        index=('<p>Items (Sorted by Submit Date in Descending order): 1 to 1 of 1</p><table summary="This table browses all dspace content"><a href="'+url+'">A</a></table>').encode()
        metadata=HistoryTests().body([('dc.title','Synthetic'),('dc.identifier.uri',url),('dc.date.issued','2024')])
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'archive'
            with patch('collect_dora_history.time.sleep'),patch('collect_dora_history.urlopen',side_effect=[io.BytesIO(index),io.BytesIO(metadata)]):
                collect(folder)
            receipt=json.loads((folder/'receipt.json').read_text())
            self.assertEqual(receipt['status'],'succeeded')
            self.assertEqual(receipt['retrieved_count'],1)
            self.assertEqual(len(receipt['files']),2)
            with self.assertRaises(ValueError):collect(folder)
