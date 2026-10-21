"""Safety contracts for an additive report consumer; no native fixtures needed."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_dashboard_relationship_summary import prepare


class RelationshipSummaryBoundaryTests(unittest.TestCase):
    def test_rejects_non_sharepoint_or_credential_links_before_copy(self):
        for url in ['https://example.com/view.aspx',
                    'https://' + 'user:secret@' + 'example.sharepoint.com/view.aspx',
                    'http://tenant.sharepoint.com/view.aspx']:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                with self.assertRaises(ValueError):
                    prepare(root/'missing-source', root/'output',
                            dict.fromkeys(['publications','candidate_links','confirmed_links'], url))
                self.assertFalse((root/'output').exists())

    def test_existing_consumer_is_required_and_duplicate_page_refused(self):
        for pages in [['ReportSection3'], ['ResearchDatasetConsumers','ResearchRelationships']]:
            with self.subTest(pages=pages), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); source=root/'source'
                (source/'definition/pages').mkdir(parents=True)
                (source/'definition/pages/pages.json').write_text(json.dumps({'pageOrder':pages}))
                with self.assertRaises(ValueError):
                    prepare(source, root/'output', dict.fromkeys(
                        ['publications','candidate_links','confirmed_links'],
                        'https://tenant.sharepoint.com/Lists/Register/view.aspx'))
                self.assertFalse((root/'output').exists())


if __name__ == '__main__':
    unittest.main()
