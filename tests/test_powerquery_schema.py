"""Cross-artifact schema checks; these do not execute the native M engine."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CanonicalSchemaTests(unittest.TestCase):
    def test_sharepoint_publication_projection_fails_closed_on_missing_columns(self):
        query = (ROOT / 'config/SharePointPublicationRegistry.m').read_text()
        self.assertIn('MissingField.Error', query)
        self.assertNotIn('MissingField.UseNull', query)

    def test_empty_source_schema_matches_semantic_model(self):
        source = (ROOT / 'powerquery/CanonicalPublications.m').read_text()
        schema = re.search(r'PublicationType\s*=\s*type table\s*\[(.*?)\],', source, re.S)
        self.assertIsNotNone(schema, 'Canonical output needs a schema independent of source rows')
        fields = dict(re.findall(r'(\w+)\s*=\s*([^,]+)', schema.group(1)))
        model = json.loads((ROOT / 'audit/model.snapshot.json').read_text())['model']
        publication = next(t for t in model['tables'] if t['name'] == 'Publication')
        types = {'string': 'nullable text', 'dateTime': 'nullable datetime', 'int64': 'nullable number'}
        self.assertEqual(set(fields), {c['name'] for c in publication['columns']})
        for column in publication['columns']:
            expected = types[column['dataType']]
            if column['name'] in ('PublicationDate', 'OnlineDate'):
                expected = 'nullable date'
            self.assertEqual(fields[column['name']].strip(), expected, column['name'])
