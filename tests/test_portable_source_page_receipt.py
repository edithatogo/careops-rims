"""Reject incomplete, corrupted or generation-mismatched fictional page receipts."""
import hashlib
import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.build_native_commit_package import page_query, validate_source_page_receipt


class PortableSourcePageReceiptTests(unittest.TestCase):
    def _generation(self, generation='refresh-17'):
        return {"generation": generation, "refreshRequestId": "request-17",
                "modelId": "model-17", "refreshStatus": "Completed",
                "refreshStartedAtUTC": "2026-09-29T01:00:00Z",
                "refreshCompletedAtUTC": "2026-09-29T01:05:00Z",
                "refreshComplete": True, "extractionComplete": True}

    def _source_pages(self, generation, keys, source_table_aliases=None):
        keys = sorted(map(str, keys))
        rows_by_table = {
            'PubMedPublications': [{"[PMID]": key} for key in keys],
            'PubMedMetadataChunks': [],
            'PubMedAuthorEvidence': [{"[PMID]": key, "[AuthorIndex]": 1,
                                     "[AffiliationIndex]": 1, "[AuthorName]": f"author-{key}",
                                     "[AffiliationText]": f"affiliation-{key}",
                                     "[EvidenceKind]": "fixture"} for key in keys],
        }
        for key in keys:
            payload = json.dumps({"PMID": key, "Title": f"title-{key}"}, separators=(",", ":")).encode()
            hex_value = payload.hex()
            chunk_count = (len(hex_value) + 19999) // 20000
            for index in range(chunk_count):
                chunk = hex_value[index * 20000:(index + 1) * 20000]
                rows_by_table['PubMedMetadataChunks'].append({
                    "[PMID]": key, "[ChunkIndex]": index, "[ChunkCount]": chunk_count,
                    "[MetadataChunk]": chunk, "[MetadataCharacters]": len(hex_value),
                    "[Encoding]": "UTF8-HEX",
                })
        sources = {}
        for table, rows in rows_by_table.items():
            keyspec = {'PubMedPublications': ('PMID',),
                       'PubMedMetadataChunks': ('PMID', 'ChunkIndex'),
                       'PubMedAuthorEvidence': ('PMID', 'AuthorIndex', 'AffiliationIndex')}[table]
            pages = []
            cursor = None
            for page_number, offset in enumerate(range(0, len(rows), 100)):
                page_rows = rows[offset:offset + 100]
                query = page_query(table, cursor, source_table_aliases)
                pages.append({"page_number": page_number, "query": query,
                              "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                              "http": 200, "body": {"results": [{"tables": [{"rows": page_rows}]}]}})
                cursor = tuple(page_rows[-1][f'[{field}]'] for field in keyspec)
            terminal_number = len(pages)
            query = page_query(table, cursor, source_table_aliases)
            pages.append({"page_number": terminal_number, "query": query,
                          "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                          "http": 200, "body": {"results": [{"tables": [{"rows": []}]}]}})
            sources[table] = {"page_size": 100, "pages": pages}
        receipt = {"kind": "native_source_page_extraction_v1", "generation": generation['generation'],
                "model_id": generation['modelId'], "request_id": generation['refreshRequestId'],
                "refresh_status": "Completed", "latest_request_before": generation['refreshRequestId'],
                "latest_request_after": generation['refreshRequestId'], "sources": sources,
                **({"source_table_aliases": source_table_aliases} if source_table_aliases else {})}
        if generation.get('processing_chain'):
            receipt['processing_chain'] = generation['processing_chain']
        return receipt

    def test_source_page_receipt_rejects_cursor_drift_and_incomplete_payloads(self):
        generation = self._generation()
        good = self._source_pages(generation, ['1001', '1002'])
        self.assertEqual(validate_source_page_receipt(good, generation)['PublicationPageCount'], 1)
        self.assertEqual(validate_source_page_receipt(good, generation)['AuthorEvidenceRowCount'], 2)
        aliases = {
            "PubMedPublications": "FreshPubMedPublications",
            "PubMedMetadataChunks": "FreshPubMedMetadataChunks",
            "PubMedAuthorEvidence": "FreshPubMedAuthorEvidence",
            "SearchAudit": "FreshSearchAudit",
            "PubMedIngestionAudit": "FreshPubMedIngestionAudit",
        }
        aliased = self._source_pages(generation, ['1001', '1002'], aliases)
        self.assertEqual(validate_source_page_receipt(aliased, generation)['_source_table_aliases'], aliases)
        self.assertIn('EVALUATE', aliased['sources']['PubMedPublications']['pages'][0]['query'])
        aliased['sources']['PubMedPublications']['pages'][0]['query_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'query/cursor fingerprint'):
            validate_source_page_receipt(aliased, generation)
        cases = []
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedPublications']['pages'][0]['query'] += ' '
        cases.append(('query drift', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedMetadataChunks']['pages'].pop()
        cases.append(('missing terminal page', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedPublications']['pages'][0]['http'] = 429
        cases.append(('source HTTP failure', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedMetadataChunks']['pages'][0]['body'] = {'error': {'code': 'SourceUnavailable'}}
        cases.append(('source query error', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedPublications']['pages'][0]['body']['results'][0]['tables'][0]['rows'] = []
        cases.append(('empty page before continuation', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedPublications']['pages'][0]['page_number'] = 2
        cases.append(('page sequence drift', changed))
        changed = json.loads(json.dumps(good))
        changed['latest_request_after'] = 'another-request'
        cases.append(('generation drift', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedPublications']['pages'][0]['body']['results'][0]['tables'][0]['rows'][0]['[PMID]'] = '9999'
        cases.append(('keyset mismatch', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedMetadataChunks']['pages'][0]['body']['results'][0]['tables'][0]['rows'][0]['[MetadataChunk]'] = 'not-hex'
        cases.append(('invalid chunk encoding', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedAuthorEvidence']['pages'].pop()
        cases.append(('author evidence missing terminal page', changed))
        changed = json.loads(json.dumps(good))
        duplicate_author = changed['sources']['PubMedAuthorEvidence']['pages'][0]['body']['results'][0]['tables'][0]['rows'][1]
        duplicate_author['[PMID]'] = '1001'
        duplicate_author['[AuthorIndex]'] = 1
        duplicate_author['[AffiliationIndex]'] = 1
        cases.append(('duplicate author evidence cursor tuple', changed))
        changed = json.loads(json.dumps(good))
        changed['sources']['PubMedAuthorEvidence']['pages'][0]['body']['results'][0]['tables'][0]['rows'][0]['[PMID]'] = '9999'
        cases.append(('orphan author evidence PMID', changed))
        for label, receipt in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_source_page_receipt(receipt, generation)
