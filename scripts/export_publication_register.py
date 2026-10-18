"""Render a complete canonical bibliography; does not query Power BI or certify its data."""
from __future__ import annotations

import argparse
import csv
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urlparse

EXPORT_FIELDS = [
    'CanonicalKey', 'Title', 'Authors', 'Journal', 'PublicationDateRaw',
    'PublicationDatePrecision', 'PublicationYear', 'PublicationMonth',
    'CHHHSAffiliatedAuthors', 'AttributionStatus', 'AttributionEvidence',
    'DedupMethod', 'SourceSet', 'PMID', 'DOI', 'PubMedURL', 'DORAURL', 'MatchedFacilities',
]
PRECISIONS = {'day', 'month', 'year', 'range', 'unknown', 'rss_unverified'}
SOURCE_SETS = {'PubMed', 'DORA', 'PubMed; DORA', 'OpenAlex', 'Crossref', 'Dimensions', 'Scopus', 'Web of Science', 'ARDC'}
SOURCE_HOSTS = {
    'pubmed.ncbi.nlm.nih.gov', 'dora.health.qld.gov.au', 'doi.org', 'www.doi.org',
    'openalex.org', 'api.openalex.org', 'crossref.org', 'api.crossref.org',
    'app.dimensions.ai', 'dimensions.ai', 'scopus.com', 'www.scopus.com'
}
MONTH = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')


def key_hash(rows: list[dict[str, Any]]) -> str:
    """Order-independent fingerprint; duplicate keys remain significant."""
    keys = sorted(str(row.get('CanonicalKey', '')) for row in rows)
    return hashlib.sha256(json.dumps(keys, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def safe_cell(value: Any) -> str:
    """Neutralise spreadsheet formula interpretation without truncating citation text."""
    text = '' if value is None else str(value)
    trimmed = text.lstrip('\ufeff \t\r\n')
    if text.startswith(('\t', '\r', '\n', '\ufeff')) or trimmed.startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


def safe_link(value: Any) -> str | None:
    """Only make recognised HTTPS source identifiers clickable; never fetch a URL."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlparse(value.strip())
        if (parsed.scheme != 'https' or parsed.hostname not in SOURCE_HOSTS
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            return None
    except ValueError:
        return None
    return value.strip()


class _MetadataReader(HTMLParser):
    """Read rendered contract fields, including escaped Unicode and newlines."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.field = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article':
            self.row = {}
            self.rows.append(self.row)
        if tag == 'dd' and self.row is not None:
            self.field = attrs.get('data-field')
            if self.field in self.row:
                raise ValueError('Duplicate HTML metadata field')
            self.row[self.field] = ''

    def handle_endtag(self, tag):
        if tag == 'dd':
            self.field = None
        if tag == 'article':
            self.row = None

    def handle_data(self, data):
        if self.field is not None:
            self.row[self.field] += data


def verify_written_exports(rows: list[dict[str, Any]], output: Path) -> None:
    """Reopen both outputs and compare every field, not merely their key count."""
    with (output/'publications.csv').open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        actual_csv = list(reader)
        if reader.fieldnames != EXPORT_FIELDS:
            raise ValueError('CSV headers differ from export contract')
    expected_csv = [{name: safe_cell(row.get(name)) for name in EXPORT_FIELDS} for row in rows]
    if actual_csv != expected_csv:
        raise ValueError('CSV content differs from complete supplied records')
    reader = _MetadataReader()
    reader.feed((output/'publications.html').read_text(encoding='utf-8'))
    reader.close()
    expected_html = [{name: '' if row.get(name) is None else str(row[name]) for name in EXPORT_FIELDS} for row in rows]
    if reader.rows != expected_html:
        raise ValueError('HTML content differs from complete supplied records')


def export_errors(envelope: dict[str, Any]) -> list[str]:
    """Check declared native expectations. This cannot establish their authenticity."""
    errors: list[str] = []
    if envelope.get('data_kind') not in {'synthetic', 'live_export'}:
        errors.append('data_kind must be synthetic or live_export')
    if not isinstance(envelope.get('coverage_note'), str) or not envelope['coverage_note'].strip():
        errors.append('A nonempty source coverage/limitations note is required')
    if not isinstance(envelope.get('source_snapshot_id'), str) or not envelope['source_snapshot_id'].strip():
        errors.append('A source snapshot/run identifier is required')
    scope = envelope.get('scope', {})
    if not isinstance(scope, dict):
        scope = {}
    mode, reporting_month = scope.get('mode'), scope.get('reporting_month')
    if mode not in {'all', 'month'}:
        errors.append('scope.mode must be all or month')
    if mode == 'month' and (not isinstance(reporting_month, str) or not MONTH.fullmatch(reporting_month)):
        errors.append('A valid YYYY-MM reporting month is required for monthly exports')
    if mode == 'all' and reporting_month is not None:
        errors.append('An all-publications scope cannot have a reporting-month filter')
    rows = envelope.get('records')
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return errors + ['records must be a list of record objects']
    expected = envelope.get('expected_canonical_count')
    if type(expected) is not int or expected < 0 or expected != len(rows):
        errors.append('Export row count differs from the independent expected canonical count')
    keys: list[str] = []
    for index, row in enumerate(rows):
        prefix = f'Record {index}: '
        if set(row) != set(EXPORT_FIELDS):
            errors.append(prefix + 'fields differ from the exact export contract')
        if any(value is not None and type(value) not in (str, int) for value in row.values()):
            errors.append(prefix + 'field values must be scalar text/integer/null')
        key = row.get('CanonicalKey')
        if not isinstance(key, str) or not key.strip():
            errors.append(prefix + 'missing canonical key')
        else:
            keys.append(key)
        if not isinstance(row.get('Title'), str) or not row['Title'].strip():
            errors.append(prefix + 'title is required')
        if row.get('SourceSet') not in SOURCE_SETS:
            errors.append(prefix + 'unknown source set')
        precision = row.get('PublicationDatePrecision')
        if precision not in PRECISIONS:
            errors.append(prefix + 'unknown publication-date precision')
        month = row.get('PublicationMonth')
        if month not in (None, ''):
            if not isinstance(month, str) or not MONTH.fullmatch(month):
                errors.append(prefix + 'invalid publication month')
            elif str(row.get('PublicationYear')) != month[:4]:
                errors.append(prefix + 'publication year/month disagree')
        if precision in {'year', 'range', 'unknown', 'rss_unverified'} and month not in (None, ''):
            errors.append(prefix + 'unverified/insufficient precision must not allocate a month')
        if precision in {'day', 'month'} and month in (None, ''):
            errors.append(prefix + 'corroborated day/month precision requires a month')
        if mode == 'month' and month != reporting_month:
            errors.append(prefix + 'record falls outside the declared reporting month')
        if envelope.get('data_kind') == 'live_export' and (
                (isinstance(key, str) and key.startswith('TEST:'))
                or str(row.get('Title', '')).startswith('[SYNTHETIC]')):
            errors.append(prefix + 'synthetic fixture cannot be declared live')
    if len(keys) != len(set(keys)):
        errors.append('Duplicate canonical keys in export')
    digest = envelope.get('expected_key_sha256')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or digest != key_hash(rows):
        errors.append('Export identity fingerprint differs from independent expected keys')
    return errors


def render_exports(envelope: dict[str, Any], output: Path) -> dict[str, Any]:
    """Write new atomic CSV/HTML output; existing destinations are never overwritten."""
    errors = export_errors(envelope)
    if errors:
        raise ValueError('; '.join(errors))
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = envelope['records']
    synthetic = envelope['data_kind'] == 'synthetic'
    label = 'SYNTHETIC TEST DATA — NOT A LIVE CHHHS REPORT' if synthetic else 'Source-attributed CHHHS publication register'
    scope = envelope['scope']
    title = 'All observed publications' if scope['mode'] == 'all' else 'Publications: ' + scope['reporting_month']
    fragments = []
    for row in rows:
        links = []
        urls = [row.get('PubMedURL')] + str(row.get('DORAURL') or '').split('; ')
        doi = row.get('DOI')
        if isinstance(doi, str) and doi:
            urls.append(doi if doi.startswith('https://') else 'https://doi.org/' + doi.removeprefix('doi:').strip())
        for value in urls:
            url = safe_link(value)
            if url:
                links.append(f'<a href="{escape(url, quote=True)}" rel="noreferrer">{escape(url)}</a>')
        fragments.append(
            '<article data-key="' + escape(row['CanonicalKey'], quote=True) + '">'
            '<h2>' + escape(row['Title']) + '</h2>'
            '<p>' + escape(str(row.get('Authors') or 'Authors not supplied')) + '</p>'
            '<p>' + escape(str(row.get('Journal') or 'Journal not supplied')) + '. '
            + escape(str(row.get('PublicationDateRaw') or 'Publication date not supplied'))
            + ' <small>[' + escape(str(row['PublicationDatePrecision'])) + ']</small></p>'
            '<p><strong>CHHHS attribution:</strong> ' + escape(str(row.get('CHHHSAffiliatedAuthors') or 'Not author-resolved'))
            + '<br>' + escape(str(row.get('AttributionEvidence') or row.get('AttributionStatus') or 'Not supplied')) + '</p>'
            '<p><strong>Sources:</strong> ' + escape(str(row['SourceSet']))
            + ' | <strong>Reconciliation:</strong> ' + escape(str(row.get('DedupMethod') or 'Not supplied')) + '</p>'
            '<p>' + '<br>'.join(links) + '</p><details open><summary>Complete record metadata</summary><dl>'
            + ''.join('<dt>' + escape(name) + '</dt><dd data-field="' + name + '">'
                      + escape('' if row.get(name) is None else str(row[name])) + '</dd>' for name in EXPORT_FIELDS)
            + '</dl></details></article>')
    css = '''body{font:16px/1.5 Georgia,serif;max-width:960px;margin:2rem auto;padding:0 1.2rem}
 h1{font-size:1.7rem}h2{font-size:1.12rem}article{border-top:1px solid;padding:1rem 0;overflow-wrap:anywhere}dd{white-space:pre-wrap}dt{font-weight:bold}
 .notice{border:2px solid;padding:1rem}small{font-size:.85em}a{overflow-wrap:anywhere}
 @media print{@page{size:A4;margin:18mm}body{max-width:none;margin:0;padding:0;font-size:10pt}
 h2{break-after:avoid}article{break-inside:avoid}a{word-break:break-all}}
'''
    html = ('<!doctype html><html lang="en-AU"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + escape(title) + '</title><style>' + css + '</style><body><header>'
            '<div class="notice"><strong>' + escape(label) + '</strong></div><h1>' + escape(title) + '</h1>'
            '<p>' + str(len(rows)) + ' canonical records. Snapshot: ' + escape(envelope['source_snapshot_id']) + '.</p>'
            '<p>' + escape(envelope['coverage_note']) + '</p></header><main>'
            + (''.join(fragments) if rows else '<p>No publications in this verified selection.</p>')
            + '</main><footer><p>Every supplied canonical record is rendered. Counts and identities were checked against the supplied expectations; native Power BI extraction and source completeness are separate acceptance gates. CSV formula-like text is prefixed with an apostrophe for spreadsheet safety.</p></footer></body></html>')
    with tempfile.TemporaryDirectory(prefix='.register-', dir=output.parent) as temp:
        staged = Path(temp) / 'output'; staged.mkdir()
        with (staged / 'publications.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS, quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writeheader()
            writer.writerows({name: safe_cell(row.get(name)) for name in EXPORT_FIELDS} for row in rows)
        (staged / 'publications.html').write_text(html, encoding='utf-8')
        verify_written_exports(rows, staged)
        receipt = {'data_kind': envelope['data_kind'], 'scope': scope, 'source_snapshot_id': envelope['source_snapshot_id'],
                   'rows': len(rows), 'canonical_keys_sha256': key_hash(rows),
                   'verified_against_supplied_expectations': True, 'native_powerbi_extraction_verified_by_this_script': False,
                   'csv_and_html_all_fields_readback_verified': True,
                   'pdf_created': False, 'csv_formula_safety': 'apostrophe prefix; no text truncation',
                   'files': {name: hashlib.sha256((staged/name).read_bytes()).hexdigest()
                             for name in ['publications.csv', 'publications.html']}}
        (staged/'manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        if output.exists():
            raise FileExistsError(f'Refusing to overwrite {output}')
        os.rename(staged, output)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Canonical export JSON with independent expected count/key fingerprint')
    parser.add_argument('output', type=Path, help='New output directory; never overwritten')
    args = parser.parse_args()
    try:
        envelope = json.loads(args.input.read_text(encoding='utf-8'))
        if not isinstance(envelope, dict):
            raise ValueError('The input must be an object')
        receipt = render_exports(envelope, args.output)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'Export failed: {error}\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
