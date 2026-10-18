"""Public PubMed archive collector. Python 3.10+; no dependencies or credentials.
Creates a unique run archive only. Does not publish a registry release or change Power BI.
Run against an approved execution directory: python collect_pubmed.py --output PATH
"""
import argparse, datetime as dt, hashlib, json, pathlib, time, urllib.parse, urllib.request, uuid
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        output.write(canonical_json(value))
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def validate_config(config):
    pubmed = config['pubmed']
    if pubmed.get('enabled') is not True:
        raise ValueError('PubMed collection is disabled')
    if pubmed.get('api_base', BASE) != BASE:
        raise ValueError('Only the fixed NCBI HTTPS root is supported')
    for key, default, maximum in [('max_requests_per_second', 2, 3),
                                   ('fetch_batch_size', 100, 100),
                                   ('maximum_ids_per_search_window', 9999, 9999)]:
        value = pubmed.get(key, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError('Invalid ' + key)
    if pubmed.get('initial_ingestion_kind', 'baseline') not in {'baseline', 'incremental'}:
        raise ValueError('Invalid ingestion kind')
    if not isinstance(pubmed.get('query'), str) or not pubmed['query'].strip():
        raise ValueError('A search query is required')
    return pubmed


class RateLimiter:
    """Serialize requests across processes using the same approved rate database."""
    def __init__(self, path, rate):
        self.path, self.rate = path, rate
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS rate (id INTEGER PRIMARY KEY, next_at REAL)')
            db.execute('INSERT OR IGNORE INTO rate VALUES (1, 0)')

    def wait(self):
        with sqlite3.connect(self.path, timeout=60) as db:
            db.execute('BEGIN IMMEDIATE')
            next_at = db.execute('SELECT next_at FROM rate WHERE id=1').fetchone()[0]
            time.sleep(max(0, min(next_at - time.time(), 60)))
            db.execute('UPDATE rate SET next_at=? WHERE id=1', (time.time() + 1 / self.rate,))

def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'

def text(node):
    return '' if node is None else ''.join(node.itertext()).strip()

def parse_records(body):
    root = ET.fromstring(body)
    if root.tag != 'PubmedArticleSet' or root.find('.//ERROR') is not None:
        raise ValueError('Unexpected PubMed response')
    records = []
    for entry in root:
        if entry.tag != 'PubmedArticle':
            raise ValueError('Unsupported publication record type; explicit adapter needed')
        cite = entry.find('MedlineCitation')
        if cite is None:
            raise ValueError('Missing MedlineCitation')
        article = cite.find('Article')
        if article is None:
            raise ValueError('Missing Article')
        pmid = text(cite.find('PMID'))
        title = text(article.find('ArticleTitle'))
        if not re.fullmatch(r'[1-9][0-9]*', pmid) or not title:
            raise ValueError('Missing PMID or title')
        date = article.find('Journal/JournalIssue/PubDate')
        parts = {child.tag: text(child) for child in date} if date is not None else {}
        doi_values = sorted(set(text(n).strip().lower() for n in entry.findall('PubmedData/ArticleIdList/ArticleId') if n.get('IdType') == 'doi' and text(n)))
        if len(doi_values) > 1:
            raise ValueError('Conflicting DOI values within PMID ' + pmid)
        authors = []
        for author in article.findall('AuthorList/Author'):
            name = text(author.find('CollectiveName')) or ' '.join(filter(None, [text(author.find('ForeName')), text(author.find('LastName'))]))
            authors.append({'name': name, 'affiliations': [text(n) for n in author.findall('AffiliationInfo/Affiliation')]})
        records.append({'source': 'pubmed', 'source_record_id': pmid, 'pmid': pmid,
                        'doi': doi_values[0] if doi_values else None, 'title': title,
                        'journal': text(article.find('Journal/Title')), 'publication_date_parts': parts,
                        'authors': authors, 'publication_types': [text(n) for n in article.findall('PublicationTypeList/PublicationType')],
                        'url': 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/',
                        'review_status': 'needs_review'})
    ids = [r['pmid'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate PMID in response')
    return records

class Collector:
    def __init__(self, folder, settings=None, limiter=None, receipt=None):
        self.folder = folder
        self.settings = settings or {}
        self.receipt = receipt if receipt is not None else {'files': []}
        self.files = self.receipt['files']
        self.limiter = limiter
        self.limit = self.settings.get('maximum_ids_per_search_window', 9999)
        self.batch_size = self.settings.get('fetch_batch_size', 100)
        for item in self.files:
            path = pathlib.Path(item['file'])
            if path.name != str(path) or path.is_absolute():
                raise ValueError('Unsafe archive member')
            if hashlib.sha256((self.folder / path).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Archived response hash mismatch')

    def request(self, endpoint, query):
        if endpoint not in {'esearch.fcgi', 'efetch.fcgi'}:
            raise ValueError('Unsupported endpoint')
        for item in self.files:
            if item.get('endpoint') == endpoint and item['query'] == query:
                body = (self.folder / item['file']).read_bytes()
                if hashlib.sha256(body).hexdigest() != item['sha256']:
                    raise ValueError('Archived response hash mismatch')
                return body
        encoded = urllib.parse.urlencode(dict(query, tool='CHHHS_Research_DEV'))
        url = urllib.request.Request(BASE + endpoint, data=encoded.encode(),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        for attempt in range(5):
            if self.limiter is None:
                raise ValueError('A shared rate limiter is required for network access')
            self.limiter.wait()
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    body = response.read()
            except Exception as exc:
                # No retries for permanent HTTP errors. Never expose arbitrary response bodies.
                status = getattr(exc, 'code', None)
                if status and status not in (429, 500, 502, 503, 504):
                    raise RuntimeError('PubMed HTTP ' + str(status)) from None
                if attempt == 4:
                    raise RuntimeError('PubMed request failed after bounded retries') from None
                time.sleep(min(2 ** attempt, 16))
                continue
            digest = hashlib.sha256(body).hexdigest()
            name = '%s-%s.response' % (uuid.uuid4().hex, endpoint.replace('.fcgi', ''))
            with (self.folder / name).open('xb') as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
            self.files.append({'file': name, 'sha256': digest, 'query': query, 'endpoint': endpoint})
            atomic_json(self.folder / 'manifest.json', self.receipt)
            return body
        raise AssertionError('Unreachable')

    def ids(self, term, start, end):
        result = json.loads(self.request('esearch.fcgi', {'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': str(self.limit), 'datetype': 'pdat', 'mindate': start.isoformat(), 'maxdate': end.isoformat()}))
        if 'error' in result:
            raise ValueError('PubMed search error')
        value = result['esearchresult']
        if value.get('errorlist') or value.get('warninglist', {}).get('phrasesignored'):
            raise ValueError('PubMed query warning requires review')
        count = int(value['count'])
        raw_ids = value['idlist']
        if (count < 0 or not isinstance(raw_ids, list)
                or any(not isinstance(i, str) or not re.fullmatch(r'[1-9][0-9]*', i) for i in raw_ids)
                or len(raw_ids) != len(set(raw_ids))):
            raise ValueError('Invalid or duplicate search IDs')
        if count > self.limit:
            if start >= end:
                raise ValueError('Daily result window exceeds retrieval limit')
            middle = start + (end - start) // 2
            ids = self.ids(term, start, middle) | self.ids(term, middle + dt.timedelta(days=1), end)
            if len(ids) != count:
                raise ValueError('Split-window count mismatch; source may have changed, start a new run')
            return ids
        ids = set(raw_ids)
        if len(ids) != count:
            raise ValueError('Search count does not reconcile with IDs')
        return ids

    def collect(self, term, start, end):
        ids = self.ids(term, start, end)
        records = []
        ordered = sorted(ids, key=int)
        self.receipt['expected_count'] = len(ids)
        for offset in range(0, len(ordered), self.batch_size):
            expected = set(ordered[offset:offset + self.batch_size])
            body = self.request('efetch.fcgi', {'db': 'pubmed', 'id': ','.join(sorted(expected, key=int)), 'retmode': 'xml'})
            batch = parse_records(body)
            if {r['pmid'] for r in batch} != expected:
                raise ValueError('Fetch IDs do not reconcile with search IDs')
            records.extend(batch)
        if len(records) != len(ids):
            raise ValueError('Final count mismatch')
        return records

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--config', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1] / 'config/collector.json')
    parser.add_argument('--resume', type=pathlib.Path, help='Existing run directory; archived responses must pass hash checks')
    parser.add_argument('--rate-db', type=pathlib.Path, required=True, help='Shared rate database for all collection processes')
    parser.add_argument('--start', type=dt.date.fromisoformat, default=dt.date(1800, 1, 1))
    parser.add_argument('--end', type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args()
    if args.start > args.end:
        parser.error('start must be before end')
    config = json.loads(args.config.read_text())
    settings = validate_config(config)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]
    folder = args.resume or args.output / run_id
    if args.resume:
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest['configuration'] != config or manifest['start'] != str(args.start) or manifest['end'] != str(args.end):
            raise ValueError('Resume configuration or date window differs')
        if manifest['status'] == 'succeeded':
            raise ValueError('Completed run is immutable; create a new run')
        run_id = manifest['run_id']
        now = manifest['started_at']
    else:
        folder.mkdir(parents=True, exist_ok=False)
        manifest = {'schema_version': '1.0', 'run_id': run_id, 'started_at': now, 'source': 'pubmed', 'status': 'running', 'coverage_status': 'provisional_pubmed_only', 'start': str(args.start), 'end': str(args.end), 'ingestion_kind': settings.get('initial_ingestion_kind', 'baseline'), 'configuration': config, 'files': []}
    # A run lock prevents concurrent resume and receipt replacement. After an abrupt
    # process death an operator must confirm the writer is gone before removing it.
    lock = folder / '.writer.lock'
    lock.mkdir()
    try:
        limiter = RateLimiter(args.rate_db, settings.get('max_requests_per_second', 2))
        collector = Collector(folder, settings, limiter, manifest)
        manifest.update(status='running')
        manifest.pop('error_type', None)
        atomic_json(folder / 'manifest.json', manifest)
        records = collector.collect(config['pubmed']['query'], args.start, args.end)
        for record in records:
            record['collected_at'] = now
            record['run_id'] = run_id
        content = canonical_json(records).encode()
        atomic_json(folder / 'candidate-records.json', records)
        manifest.update(status='succeeded', retrieved_count=len(records), candidates_sha256=hashlib.sha256(content).hexdigest())
    except Exception as exc:
        manifest.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        manifest['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        atomic_json(folder / 'manifest.json', manifest)
        lock.rmdir()
    print(str(folder))

if __name__ == '__main__':
    main()
