import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_native_retention_package as retention


class PortableRetentionDefinitionTests(unittest.TestCase):
    def _baseline(self):
        def action(operation):
            return {'type': 'OpenApiConnection', 'runAfter': {}, 'inputs': {
                'host': {'operationId': operation}, 'parameters': {}}}
        return {'properties': {'definition': {
            'triggers': {'manual': {'type': 'Request', 'kind': 'Button'}},
            'actions': {'Run_a_query_against_a_dataset': action('ExecuteDatasetQuery'),
                        'Create_file': action('CreateFile'),
                        'Get_file_content_using_path': action('GetFileContentByPath')}}}}

    def test_fixed_source_staging_is_immutable_and_does_not_collect_other_source(self):
        builder = getattr(retention, 'build_definition', None)
        self.assertIsNotNone(builder, 'Source-specific fixed-batch staging is missing')
        baseline = self._baseline()
        original = copy.deepcopy(baseline)
        batch = '00000000-0000-4000-8000-000000000001'
        result = builder(baseline, tables=['DoraPublications', 'DoraMetadataChunks'], batch=batch)
        self.assertEqual(baseline, original)
        actions = result['properties']['definition']['actions']
        self.assertEqual(actions['Batch']['inputs'], batch)
        self.assertFalse(any('PubMed' in key for key in actions))
        self.assertFalse(any('commit' in key.lower() for key in actions))
        page_actions = actions['DoraPublications_Pages']['actions']['DoraPublications_Has_rows']['actions']
        existing = page_actions['DoraPublications_Existing']
        self.assertEqual(existing['inputs']['host']['operationId'], 'GetFileContentByPath')
        condition = page_actions['DoraPublications_Exists']
        self.assertEqual(condition['runAfter'], {'DoraPublications_Existing': ['Succeeded', 'Failed']})
        self.assertNotIn('DoraPublications_Write', condition['actions'])
        missing = condition['else']['actions']['DoraPublications_Require_missing']
        self.assertIn('404', missing['inputs'])
        write = condition['else']['actions']['DoraPublications_Write']
        self.assertEqual(write['runAfter'], {'DoraPublications_Require_missing': ['Succeeded']})
        self.assertEqual(page_actions['DoraPublications_Read']['runAfter'], {'DoraPublications_Exists': ['Succeeded']})

    def test_source_and_batch_invalidity_reject_before_compilation(self):
        builder = getattr(retention, 'build_definition', None)
        self.assertIsNotNone(builder, 'Source-specific fixed-batch staging is missing')
        for tables, batch in [([], None), (['Unknown'], None),
                              (['DoraPublications', 'DoraPublications'], None),
                              (['DoraPublications'], '../overwrite')]:
            with self.subTest(tables=tables, batch=batch), self.assertRaises(ValueError):
                builder(self._baseline(), tables=tables, batch=batch)

    def test_synthetic_full_projection_matches_every_native_table(self):
        model = (ROOT / 'config' / 'native-ingestion.tmdl').read_text(encoding='utf-8')
        for table in retention.SOURCES:
            expected = retention._tmdl_table_projection(model, table)
            projection = ',\n'.join(f'    "{alias}", {table}[{source}]'
                                     for alias, source in expected)
            query = (f'EVALUATE\nSELECTCOLUMNS(\n'
                     f'    TOPN(100, {table}, {table}[{expected[0][1]}], ASC),\n'
                     f'{projection}\n)\nORDER BY [{expected[0][0]}]')
            with self.subTest(table=table):
                retention.validate_page_projection(table, query, model)

    def test_non_key_column_deletion_or_rename_fails_closed(self):
        model = (ROOT / 'config' / 'native-ingestion.tmdl').read_text(encoding='utf-8')
        table = 'PubMedPublications'
        expected = retention._tmdl_table_projection(model, table)
        self.assertIn(('Abstract', 'Abstract'), expected)
        cases = {
            'deleted': [pair for pair in expected if pair[0] != 'Abstract'],
            'renamed': [('Summary', source) if alias == 'Abstract' else (alias, source)
                        for alias, source in expected],
            'reordered': expected[1:] + expected[:1],
            'duplicated': expected[:-1] + [expected[-2]],
            'misprojected': [(alias, 'PMID') if alias == 'Abstract' else (alias, source)
                             for alias, source in expected],
        }
        for case, projection_fields in cases.items():
            projection = ',\n'.join(f'    "{alias}", {table}[{source}]'
                                     for alias, source in projection_fields)
            query = (f'EVALUATE\nSELECTCOLUMNS(\n'
                     f'    TOPN(100, {table}, {table}[PMID], ASC),\n'
                     f'{projection}\n)\nORDER BY [PMID]')
            with self.subTest(case=case), self.assertRaisesRegex(
                    ValueError, 'Page projection differs from native TMDL columns'):
                retention.validate_page_projection(table, query, model)

    def test_page_expression_rejects_reordered_or_duplicate_cursors(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config'
            config.mkdir()
            query = config / 'source-PubMedMetadataChunks-page.dax'
            with patch.object(retention, 'ROOT', Path(directory)):
                for declarations in ('VAR After1 = -1\nVAR After0 = ""',
                                     'VAR After0 = ""\nVAR After0 = ""'):
                    query.write_text(declarations, encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'Cursor template indexes changed'):
                        retention.page_expression('PubMedMetadataChunks', ['PMID', 'ChunkIndex'])
                query.write_text('VAR After0 = ""\nVAR After1 = -1', encoding='utf-8')
                expression = retention.page_expression('PubMedMetadataChunks', ['PMID', 'ChunkIndex'])
                self.assertIn("variables('PubMedMetadataChunks_cursor_0')", expression)
                self.assertIn("variables('PubMedMetadataChunks_cursor_1')", expression)


if __name__ == '__main__':
    unittest.main()
