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
