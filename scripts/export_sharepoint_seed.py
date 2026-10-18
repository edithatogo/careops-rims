"""Generate seed files for the SharePoint Publication Registry list.

Reads validated baseline records from private/ and formats them for SharePoint List
import (CSV and JSON). Adheres to formula-safety and URL-validation policies.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from export_publication_register import safe_cell, safe_link
from project_utils import ROOT, save_json

SHAREPOINT_COLUMNS = [
    'Title',
    'SourceKey',
    'CanonicalKey',
    'Authors',
    'Journal',
    'PublicationYear',
    'PublicationMonth',
    'PublicationDateRaw',
    'PublicationDatePrecision',
    'SourceSet',
    'PMID',
    'DOI',
    'PubMedURL',
    'DORAURL',
    'MatchedFacilities',
    'CHHHSAffiliatedAuthors',
    'AttributionEvidence',
    'ReviewStatus',
    'ReviewNotes',
    'FirstObservedUTC',
    'LastObservedUTC',
]


def build_source_key(row: dict[str, Any]) -> str:
    """Derive a stable, unique source key for SharePoint lookup and deduplication."""
    pmid = row.get('PMID')
    if pmid and str(pmid).strip():
        return f"pubmed:{str(pmid).strip()}"
    dora_url = row.get('DORAURL')
    if dora_url and str(dora_url).strip():
        handle = str(dora_url).strip().rstrip('/')
        if '/handle/' in handle:
            handle = handle.split('/handle/')[-1]
        return f"dora:{handle}"
    doi = row.get('DOI')
    if doi and str(doi).strip():
        return f"doi:{str(doi).strip().lower()}"
    canon = row.get('CanonicalKey', '')
    return f"key:{canon}"


def map_review_status(status: Any) -> str:
    """Map internal review status to SharePoint Choice column value."""
    s = str(status).lower().strip() if status else 'needs_review'
    if s in {'included', 'include'}:
        return 'Included'
    if s in {'excluded', 'exclude'}:
        return 'Excluded'
    return 'Needs Review'


def transform_record(
    raw: dict[str, Any],
    alias_map: dict[str, str] | None = None,
    pub_status_map: dict[str, str] | None = None,
    pub_attr_map: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Map a raw publication record into the SharePoint list schema, joining SQLite resolutions if present."""
    title = str(raw.get('Title') or 'Untitled').strip()
    source_key = build_source_key(raw)
    canon_key = str(raw.get('CanonicalKey') or '').strip()
    effective_canon = (alias_map or {}).get(canon_key, canon_key)
    authors = str(raw.get('Authors') or '').strip()
    journal = str(raw.get('Journal') or '').strip()

    year_val = raw.get('PublicationYear')
    pub_year = int(year_val) if year_val and str(year_val).isdigit() else None

    month_val = str(raw.get('PublicationMonth') or '').strip()
    raw_date = str(raw.get('PublicationDateRaw') or '').strip()
    precision = str(raw.get('PublicationDatePrecision') or 'unknown').strip()
    source_set = str(raw.get('SourceSet') or 'Unknown').strip()

    pmid = str(raw.get('PMID') or '').strip()
    doi = str(raw.get('DOI') or '').strip()
    pubmed_url = safe_link(raw.get('PubMedURL')) or ''
    dora_url = safe_link(raw.get('DORAURL')) or ''

    matched_facilities = str(raw.get('MatchedFacilities') or '').strip()
    affiliated_authors = str(raw.get('CHHHSAffiliatedAuthors') or '').strip()
    if pub_attr_map and effective_canon in pub_attr_map:
        if not matched_facilities and pub_attr_map[effective_canon].get('facilities'):
            matched_facilities = pub_attr_map[effective_canon]['facilities']
        if not affiliated_authors and pub_attr_map[effective_canon].get('authors'):
            affiliated_authors = pub_attr_map[effective_canon]['authors']

    raw_status = raw.get('ReviewStatus')
    if pub_status_map and effective_canon in pub_status_map:
        raw_status = pub_status_map[effective_canon]
    review_status = map_review_status(raw_status)
    review_notes = str(raw.get('ReviewNotes') or '').strip()

    first_observed = str(raw.get('FirstObservedAt') or raw.get('FirstObservedUTC') or '').strip()
    last_observed = str(raw.get('LastObservedAt') or raw.get('LastObservedUTC') or first_observed).strip()

    return {
        'Title': title,
        'SourceKey': source_key,
        'CanonicalKey': canon_key,
        'Authors': authors,
        'Journal': journal,
        'PublicationYear': pub_year,
        'PublicationMonth': month_val,
        'PublicationDateRaw': raw_date,
        'PublicationDatePrecision': precision,
        'SourceSet': source_set,
        'PMID': pmid,
        'DOI': doi,
        'PubMedURL': pubmed_url,
        'DORAURL': dora_url,
        'MatchedFacilities': matched_facilities,
        'CHHHSAffiliatedAuthors': affiliated_authors,
        'AttributionEvidence': str(raw.get('AttributionEvidence') or '').strip(),
        'ReviewStatus': review_status,
        'ReviewNotes': review_notes,
        'FirstObservedUTC': first_observed,
        'LastObservedUTC': last_observed,
    }


def export_seed(
    input_path: Path,
    output_dir: Path,
    sqlite_path: Path | None = None,
) -> dict[str, Any]:
    """Generate both CSV and JSON seed artifacts for SharePoint list population."""
    import sqlite3
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict):
        raw_records = data.get('records', [])
    elif isinstance(data, list):
        raw_records = data
    else:
        raise ValueError('Unrecognised input JSON structure')

    alias_map: dict[str, str] = {}
    pub_status_map: dict[str, str] = {}
    pub_attr_map: dict[str, dict[str, str]] = {}
    if sqlite_path and sqlite_path.exists():
        conn = sqlite3.connect(sqlite_path)
        c = conn.cursor()
        c.execute('SELECT old_id, canonical_id FROM publication_alias')
        alias_map = dict(c.fetchall())
        c.execute('SELECT id, review_status FROM publication')
        pub_status_map = dict(c.fetchall())
        c.execute('SELECT publication_id, authors, facilities FROM attribution_resolution')
        for pid, auth, fac in c.fetchall():
            auth_list = json.loads(auth) if auth else []
            fac_list = json.loads(fac) if fac else []
            pub_attr_map[pid] = {
                'authors': '; '.join(auth_list),
                'facilities': '; '.join(fac_list),
            }
        conn.close()

    transformed = [
        transform_record(r, alias_map=alias_map, pub_status_map=pub_status_map, pub_attr_map=pub_attr_map)
        for r in raw_records
    ]

    # Write CSV
    csv_path = output_dir / 'publication-registry-seed.csv'
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=SHAREPOINT_COLUMNS)
        writer.writeheader()
        for row in transformed:
            safe_row = {k: safe_cell(v) if isinstance(v, str) else v for k, v in row.items()}
            writer.writerow(safe_row)

    # Write JSON
    json_path = output_dir / 'publication-registry-seed.json'
    save_json(json_path, transformed)

    status_counts: dict[str, int] = {}
    for r in transformed:
        st = r['ReviewStatus']
        status_counts[st] = status_counts.get(st, 0) + 1

    summary = {
        'total_records': len(transformed),
        'csv_output': str(csv_path),
        'json_output': str(json_path),
        'status_counts': status_counts,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description='Export SharePoint seed data from baseline.')
    parser.add_argument(
        '--input',
        type=Path,
        default=ROOT / 'private/ops/candidate-releases/baseline-20260912/registry-metadata.json',
        help='Input JSON with baseline records',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=ROOT / 'private/ops/sharepoint-seed',
        help='Directory to output seed files',
    )
    parser.add_argument(
        '--sqlite',
        type=Path,
        default=ROOT / 'private/ops/publications.sqlite',
        help='Path to reviewed SQLite database for facilities, authors, and review status',
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f'Input file not found: {args.input}')

    result = export_seed(args.input, args.output_dir, sqlite_path=args.sqlite)
    print(f"Exported {result['total_records']} seed records to {args.output_dir}:")
    print(f"  CSV:  {result['csv_output']}")
    print(f"  JSON: {result['json_output']}")
    print(f"  Status breakdown: {result['status_counts']}")


if __name__ == '__main__':
    main()
