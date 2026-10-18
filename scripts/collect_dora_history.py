"""Archive public collection pages and explicit full-record metadata, without PDFs."""
import argparse
from collections import defaultdict
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from collect_pubmed import atomic_json

BASE = 'https://dora.health.qld.gov.au'
COLLECTION = BASE + '/qldresearchjspui/handle/1/849'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.table = None
        self.cell = False
        self.row = []
        self.fields = defaultdict(list)
        self.items = []
        self.links = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.table = 'record' if 'itemDisplayTable' in attrs.get('class', '') else ('index' if attrs.get('summary') == 'This table browses all dspace content' else None)
        if tag == 'tr':
            self.row = []
        if self.table == 'record' and tag == 'td':
            self.cell = True
            self.row.append('')
        if tag == 'a' and attrs.get('href'):
            link = urljoin(BASE, attrs['href'])
            self.links.append(link)
            if self.table == 'index' and re.fullmatch(re.escape(BASE) + r'/qldresearchjspui/handle/1/\d+', link):
                self.items.append(link)

    def handle_data(self, value):
        self.text.append(value)
        if self.cell:
            self.row[-1] += value

    def handle_endtag(self, tag):
        if tag == 'td':
            self.cell = False
        if tag == 'tr' and self.table == 'record' and len(self.row) >= 2:
            self.fields[self.row[0].strip()].append(self.row[1].strip())
        if tag == 'table':
            self.table = None


def parse_record(body, url):
    page = Page()
    page.feed(body.decode('utf-8'))
    fields = page.fields
    def one(key):
        values = list(dict.fromkeys(fields.get(key, [])))
        if len(values) > 1:
            raise ValueError('Conflicting metadata: ' + key)
        return values[0] if values else None
    uri = one('dc.identifier.uri')
    # Older records retain an HTTP handle for the same verified HTTPS item.
    if uri not in {url, url.replace('https://', 'http://', 1)} or not one('dc.title'):
        raise ValueError('Record identity/title not verified')
    issued = one('dc.date.issued') or ''
    match = re.fullmatch(r'(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?', issued)
    parts = {k: v for k, v in zip(('Year', 'Month', 'Day'), match.groups()) if v} if match else {}
    return {'source': 'dora', 'source_record_id': url, 'url': url,
            'title': one('dc.title'), 'doi': one('dc.identifier.doi'), 'pmid': one('dc.identifier.pmid'),
            'journal': one('dc.identifier.journaltitle') or one('dc.relation.ispartof'),
            'authors': [{'name': a, 'affiliations': []} for a in fields.get('dc.contributor.author', [])],
            'publication_date_parts': parts, 'publication_date_raw': issued, 'date_basis': 'publication_verified',
            'attribution_evidence': '; '.join(fields.get('dc.description', [])),
            'collection_evidence': COLLECTION, 'coverage_status': 'public_collection_snapshot',
            'identity_evidence': {key: fields[key] for key in ('dc.identifier.citation', 'dc.identifier.orcidwork',
                                  'dc.relation.url', 'local.relation.url', 'dc.description.pages',
                                  'dc.description.volume', 'dc.description.issue') if fields.get(key)}}


def collect(folder):
    folder.mkdir(parents=True, exist_ok=True)
    receipt_path = folder / 'receipt.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
        'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'status': 'running', 'files': {}}
    if receipt['status'] == 'succeeded':
        raise ValueError('Completed archive is immutable')
    lock = folder / '.writer.lock'
    lock.mkdir()
    receipt.update(status='running')
    receipt.pop('error_type', None)
    def fetch(url):
        if urlparse(url).netloc != 'dora.health.qld.gov.au':
            raise ValueError('Unexpected source host')
        name = hashlib.sha256(url.encode()).hexdigest() + '.html'
        path = folder / name
        if url in receipt['files']:
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != receipt['files'][url]['sha256']:
                raise ValueError('Archive hash mismatch')
            return body
        time.sleep(0.5)
        with urlopen(url, timeout=45) as response:
            body = response.read()
        path.write_bytes(body)
        receipt['files'][url] = {'file': name, 'sha256': hashlib.sha256(body).hexdigest()}
        atomic_json(receipt_path, receipt)
        return body
    try:
        url, visited, items, expected = COLLECTION, set(), [], None
        while url:
            if url in visited:
                raise ValueError('Pagination cycle')
            visited.add(url)
            page = Page(); page.feed(fetch(url).decode('utf-8'))
            counts = re.findall(r'order\):\s*\d+\s+to\s+\d+\s+of\s+(\d+)', ' '.join(page.text))
            if not counts or len(set(counts)) != 1:
                raise ValueError('Collection count unavailable')
            count = int(counts[0])
            if expected is not None and expected != count:
                raise ValueError('Collection changed during traversal')
            expected = count
            items.extend(page.items)
            offset = int(urlparse(url).query.split('=')[-1]) if '?' in url else 0
            next_links = [x for x in page.links if x == COLLECTION + '?offset=' + str(offset + 20)]
            url = next_links[0] if next_links else None
        if len(items) != expected or len(set(items)) != expected:
            raise ValueError('Collection keys do not reconcile')
        atomic_json(folder / 'collection-keys.json', items)
        print('Collection keys:', len(items), flush=True)
        records = []
        for i, item in enumerate(items):
            records.append(parse_record(fetch(item + '?mode=full'), item))
            if (i + 1) % 50 == 0:
                print('Metadata:', i + 1, '/', expected, flush=True)
        atomic_json(folder / 'candidate-records.json', records)
        receipt.update(status='succeeded', expected_count=expected, retrieved_count=len(records),
                       candidates_sha256=hashlib.sha256((folder/'candidate-records.json').read_bytes()).hexdigest(),
                       coverage='all public collection keys observed in this traversal; not an institutional census')
    except Exception as exc:
        receipt.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        receipt['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        atomic_json(receipt_path, receipt)
        lock.rmdir()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    collect(parser.parse_args().output)
