"""Parse the observed public DoRA RSS export; never claim full historical coverage."""
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


def parse_feed(body):
    root = ET.fromstring(body)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('Unexpected DoRA feed schema')
    rows, seen = [], set()
    for item in channel.findall('item'):
        title, url = item.findtext('title'), item.findtext('link')
        parsed = urlparse(url or '')
        if (not title or parsed.scheme != 'https' or parsed.hostname != 'dora.health.qld.gov.au'
                or parsed.username or parsed.password or not parsed.path.startswith('/qldresearchjspui/handle/')):
            raise ValueError('Invalid DoRA title or stable source URL')
        if url in seen:
            raise ValueError('Duplicate DoRA feed identity')
        seen.add(url)
        description = item.findtext('description') or ''
        authors = re.search(r'(?:^|\n)Authors: (.*?)(?=\n(?:Abstract|Description):|$)', description, re.S)
        attribution = re.search(r'(?:^|\n)Description: (.*)$', description, re.S)
        rows.append({'source': 'dora', 'source_record_id': url, 'url': url, 'title': title,
                     'pmid': None, 'doi': None, 'journal': None,
                     'authors': [{'name': a.strip(), 'affiliations': []} for a in authors.group(1).split(';') if a.strip()] if authors else [],
                     'attribution_evidence': attribution.group(1).strip() if attribution else '',
                     'raw_feed_date': item.findtext('pubDate'),
                     'dc_date_raw': item.findtext('{http://purl.org/dc/elements/1.1/}date'),
                     'date_basis': 'rss_unverified', 'publication_date_parts': {},
                     'coverage_status': 'finite_feed_history_incomplete'})
    return rows


# Portable validation helpers from the qualified source snapshot.
import copy
import json

PUBLICATION_COLUMNS = (
    'DORAKey', 'DORAURL', 'Title', 'Authors', 'Abstract', 'CHHHSAffiliatedAuthors',
    'AttributionEvidence', 'PublicationDate', 'PublicationDateRaw',
    'PublicationDatePrecision', 'PublicationYear', 'NormalizedTitle', 'PMID',
    'DOI', 'Journal', 'CoverageStatus', 'CollectionExpectedCount', 'FullMetadataJSON',
)

OFFICIAL_HANDLE = re.compile(
    r'https://dora\.health\.qld\.gov\.au/qldresearchjspui/handle/[1-9][0-9]*/[1-9][0-9]*\Z'
)

def reconcile_feed_with_history(body, retained):
    """Local expected-outcome adapter; does not fetch, commit, or execute native M.

    Retained input is the full retained parser output, not a model text column.
    Preserve rich same-key records exactly and keep sparse RSS observations separate.
    """
    history = copy.deepcopy(retained)
    keys = []
    for row in history:
        if not set(PUBLICATION_COLUMNS).issubset(row):
            raise ValueError('Full retained DoRA schema required')
        url = row['DORAURL']
        if not isinstance(url, str) or not OFFICIAL_HANDLE.fullmatch(url) or row['DORAKey'] != 'DORA:' + url:
            raise ValueError('Retained DoRA identity mismatch')
        if not isinstance(row['Title'], str) or not row['Title'].strip():
            raise ValueError('Retained DoRA title missing')
        fields = json.loads(row['FullMetadataJSON'])
        if not isinstance(fields, list) or not all(isinstance(f, dict) and {'Field', 'Value'}.issubset(f) for f in fields):
            raise ValueError('Retained DoRA full metadata schema mismatch')
        uris = {f['Value'] for f in fields if f['Field'] == 'dc.identifier.uri'}
        if len(uris) != 1 or next(iter(uris)) not in {url, url.replace('https://', 'http://', 1)}:
            raise ValueError('Retained DoRA metadata identity mismatch')
        titles = {f['Value'] for f in fields if f['Field'] == 'dc.title'}
        if titles != {row['Title']}:
            raise ValueError('Retained DoRA metadata title mismatch')
        keys.append(row['DORAKey'])
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate retained DoRA identity')
    current = parse_feed(body)
    raw_items = ET.fromstring(body).find('channel').findall('item')
    observations, additions = [], []
    for item, raw_item in zip(current, raw_items):
        url = item['url']
        if not OFFICIAL_HANDLE.fullmatch(url):
            raise ValueError('RSS DoRA canonical handle required')
        key = 'DORA:' + url
        item['raw_rss'] = {name: raw_item.findtext(name) for name in ('title', 'link', 'description', 'pubDate')}
        observations.append(copy.deepcopy(item))
        if key in keys:
            continue
        authors = '; '.join(dict.fromkeys(a['name'] for a in item['authors']))
        evidence = item['raw_rss']['description'] or ''
        markers = ('Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated authors:',
                   'Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated author:')
        marker = next((value for value in markers if value in evidence), None)
        metadata = [
            {'Field': 'rims.source.format', 'Value': 'dora_rss_v1'},
            {'Field': 'dc.identifier.uri', 'Value': url},
            {'Field': 'dc.title', 'Value': item['title']},
            {'Field': 'dc.description', 'Value': item['raw_rss']['description'] or ''},
            {'Field': 'rims.rss.pubDate', 'Value': item['raw_feed_date']},
            {'Field': 'rims.rss.observation', 'Value': json.dumps(item['raw_rss'], ensure_ascii=False)},
        ]
        metadata.extend({'Field': 'dc.contributor.author', 'Value': a['name']} for a in item['authors'])
        row = dict.fromkeys(PUBLICATION_COLUMNS)
        row.update(DORAKey=key, DORAURL=url, Title=item['title'], Authors=authors, Abstract='',
                   CHHHSAffiliatedAuthors=evidence.split(marker, 1)[1].strip() if marker else None,
                   AttributionEvidence=evidence or 'No explicit DORA affiliation evidence; review required.',
                   PublicationDateRaw=item['raw_feed_date'] or '', PublicationDatePrecision='unknown',
                   NormalizedTitle=re.sub('[^a-z0-9]', '', item['title'].lower()),
                   CoverageStatus='Finite RSS observation; historical completeness not established',
                   FullMetadataJSON=json.dumps(metadata, ensure_ascii=False))
        additions.append(row)
    union = history + additions
    observed = {item['url'] for item in observations}
    title_conflicts = sum(row['DORAURL'] in observed and any(
        item['url'] == row['DORAURL'] and item['title'] != row['Title'] for item in observations
    ) for row in history)
    audit = {
        'Retained records': len(history), 'Observed RSS items': len(observations),
        'RSS new identities': len(additions), 'Union records': len(union),
        'Distinct union keys': len({r['DORAKey'] for r in union}),
        'RSS title differences preserved as observations': title_conflicts,
        'Historical records lost': len(set(keys) - {r['DORAKey'] for r in union}),
    }
    return {'publications': union, 'observations': observations, 'audit': audit,
            'coverage': 'retained history plus finite RSS observations; not a current complete census'}
