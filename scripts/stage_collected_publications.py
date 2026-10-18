"""Verify archived source receipts and stage a local provisional bibliography."""
import argparse
import hashlib
import json
from pathlib import Path

from collect_pubmed import Collector
from import_dora import parse_feed
from publication_registry import Registry, identifiers
from export_publication_register import render_exports


def stage(pubmed, dora, database, output, release_id, history=False):
    receipt = json.loads((pubmed / 'manifest.json').read_text())
    if receipt.get('status') != 'succeeded':
        raise ValueError('PubMed run did not succeed')
    Collector(pubmed, receipt=receipt)  # Verify archived response hashes.
    body = (pubmed / 'candidate-records.json').read_bytes()
    if hashlib.sha256(body).hexdigest() != receipt['candidates_sha256']:
        raise ValueError('PubMed candidate hash mismatch')
    rows = json.loads(body)
    if len(rows) != receipt['expected_count'] or len(rows) != receipt['retrieved_count']:
        raise ValueError('PubMed counts do not reconcile')
    feed_receipt = json.loads((dora / 'receipt.json').read_text())
    if history:
        if feed_receipt.get('status') != 'succeeded':
            raise ValueError('DoRA historical collection did not succeed')
        for item in feed_receipt['files'].values():
            if Path(item['file']).name != item['file']:
                raise ValueError('Unsafe DoRA archive member')
            if hashlib.sha256((dora / item['file']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('DoRA historical archive hash mismatch')
        feed = (dora / 'candidate-records.json').read_bytes()
        if hashlib.sha256(feed).hexdigest() != feed_receipt['candidates_sha256']:
            raise ValueError('DoRA candidate hash mismatch')
        dora_rows = json.loads(feed)
        # Retain malformed source identifiers as evidence, never use them to merge.
        # The hashed source candidates remain untouched in their archive.
        for row in dora_rows:
            for kind in ('pmid', 'doi'):
                try:
                    identifiers({kind: row.get(kind)})
                except ValueError:
                    row.setdefault('identifier_warnings', {})[kind] = row[kind]
                    row[kind] = None
        keys = json.loads((dora / 'collection-keys.json').read_text())
        if (len(dora_rows) != feed_receipt['expected_count'] or len(dora_rows) != feed_receipt['retrieved_count']
                or len(set(keys)) != len(keys) or set(keys) != {r['source_record_id'] for r in dora_rows}):
            raise ValueError('DoRA historical key/count mismatch')
        source_hash = feed_receipt['candidates_sha256']
        observed_at = feed_receipt['started_at']
    else:
        feed = (dora / 'rss.xml').read_bytes()
        if hashlib.sha256(feed).hexdigest() != feed_receipt['sha256']:
            raise ValueError('DoRA feed hash mismatch')
        dora_rows = parse_feed(feed)
        if len(dora_rows) != feed_receipt['item_count']:
            raise ValueError('DoRA feed count mismatch')
        source_hash = feed_receipt['sha256']
        observed_at = feed_receipt['retrieved_at']
    registry = Registry(database, 'live_export')
    try:
        registry.ingest(rows, receipt['run_id'], 'pubmed', receipt['started_at'], receipt['ingestion_kind'])
        registry.ingest(dora_rows, 'dora-' + source_hash, 'dora', observed_at, 'baseline')
        folder = registry.stage(output, release_id, {
            'pubmed': 'provisional query baseline',
            'pubmed_window': [receipt['start'], receipt['end']],
            'dora': 'complete observed public collection snapshot; institutional completeness unverified' if history else 'finite RSS; historical completeness unverified',
            'source_receipts': [receipt['run_id'], source_hash],
        })
        for source in [folder / 'all-publications.json', *sorted((folder / 'monthly').glob('*.json'))]:
            render_exports(json.loads(source.read_text()), folder / 'rendered' / source.stem)
        return folder
    finally:
        registry.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pubmed', 'dora', 'database', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--release-id', required=True)
    parser.add_argument('--history', action='store_true', help='Use verified full DoRA collection archive instead of RSS')
    args = parser.parse_args()
    print(stage(args.pubmed, args.dora, args.database, args.output, args.release_id, args.history))
