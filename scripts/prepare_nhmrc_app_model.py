"""Append qualified APP derivation to the accepted model without changing old M."""
import base64
import copy
import json
import re
from urllib.parse import urlparse


def prepare(document, archive_url, batch, function_source, trusted_rule_sha256):
    if not re.fullmatch('[0-9a-f]{64}', trusted_rule_sha256 or ''):
        raise ValueError('External APP rule authority digest required')
    if not re.fullmatch('[0-9a-f-]{36}', batch):
        raise ValueError('Exact batch identity required')
    u = urlparse(archive_url)
    if (u.scheme != 'https' or not (u.hostname or '').endswith('.sharepoint.com')
            or u.netloc != u.hostname or u.query or u.fragment
            or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained APP batch URL required')
    result = copy.deepcopy(document)
    parts = [p for p in result['definition']['parts'] if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl']
    if len(parts) != 1:
        raise ValueError('Unique accepted evidence table required')
    part = parts[0]; text = base64.b64decode(part['payload']).decode()
    sites = re.findall(r'StudySite\s*=\s*"((?:[^"\n]|"")*)"\s*,', text)
    if len(sites) != 1 or not archive_url.startswith(sites[0].replace('""', '"') + '/Documents/'):
        raise ValueError('APP archive must use bound study site/Documents')
    marker = 'Rows=Table.Buffer(Table.FromRecords(BeforeGNT & GNTEvidence,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'ReadStudy=' not in text or 'APPProjector=' in text:
        raise ValueError('Accepted GNT evidence contract required')
    extra = ('BeforeAPP=List.Buffer(BeforeGNT & GNTEvidence),\n'
        '    APPProjector=' + function_source.rstrip() + ',\n'
        '    APPEvidence=APPProjector(ReadStudy,' + json.dumps(archive_url) + ','
        + json.dumps(batch) + ',' + json.dumps(trusted_rule_sha256) + '),\n    ')
    text = text.replace(marker, extra.replace('\n', '\n\t\t\t\t')
        + 'Rows=Table.Buffer(Table.FromRecords(BeforeAPP & APPEvidence,Columns,MissingField.Error))')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result
