"""Join explicit Crossref funding identifiers to retained historical NHMRC rows.

No prefix rewriting, title matching, current-status or ARDC-PURL inference.
"""
import hashlib
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

from source_relationship_evidence import normalise_doi


def exact_identifier(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if value >= 0 and value == int(value) else None
    return value if isinstance(value, str) and value and value == value.strip() else None


def project_packet(folder):
    root = Path(folder)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if (manifest.get('kind') != 'historical_nhmrc_crossref_retention_v1'
            or manifest.get('namespace') != 'nhmrc' or manifest.get('complete') is not True):
        raise ValueError('Complete historical NHMRC packet required')
    files = {r['name']: r for r in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate government source file')

    def raw(name):
        if Path(name).name != name or '/' in name or '\\' in name or name not in files:
            raise ValueError('Exact retained government source filename required')
        data = (root / name).read_bytes()
        if len(data) != files[name]['bytes'] or hashlib.sha256(data).hexdigest() != files[name]['sha256']:
            raise ValueError('Retained government source hash or length drift')
        return data

    def referenced(ref):
        data = raw(ref['name'])
        if ref['sha256'] != files[ref['name']]['sha256']:
            raise ValueError('Government provenance hash drift')
        return data

    authority = json.loads(referenced(manifest['authority']))
    if not any(r.get('type') == 'website' and r.get('value') == 'https://www.nhmrc.gov.au/'
               for r in authority['links']):
        raise ValueError('Independent NHMRC namespace authority required')
    funders = {'10.13039/' + value for r in authority['external_ids'] if r['type'] == 'fundref'
               for value in r['all']}
    upstream = json.loads(referenced(manifest['source_manifest']))
    if (upstream.get('format') != 'rims-funding-native-workbook-commit-v1'
            or upstream.get('source') != 'nhmrc' or upstream.get('complete') is not True
            or upstream.get('fidelity') != 'original_binary_content_exact_saved_readback'):
        raise ValueError('Retained official NHMRC workbook source contract required')
    spec = manifest['workbook']
    source_url = spec['source_url']
    u = urlparse(source_url)
    sources = [r for r in upstream['files'] if r['name'] == spec['name']]
    if (len(sources) != 1 or sources[0]['source_url'] != source_url
            or u.scheme != 'https' or u.netloc != 'www.nhmrc.gov.au'
            or not u.path.startswith('/sites/default/files/') or u.query or u.fragment
            or spec['sheet'] != 'GRANTS DATA' or spec['id_column'] != 'APP ID'):
        raise ValueError('Official workbook identity, URL or identifier column drift')
    binding = sources[0]
    if 'sha256' not in binding or 'bytes' not in binding:
        if 'source_retention' not in manifest:
            raise ValueError('Upstream workbook digest or length missing or different')
        receipt = json.loads(referenced(manifest['source_retention']))
        if (receipt.get('status') != 'PASS_NATIVE_ORIGINAL_WORKBOOK_ARCHIVE'
                or not upstream.get('run') or receipt.get('run') != upstream['run']):
            raise ValueError('Upstream retention identity drift')
        original = [r for r in receipt['files'] if r['name'] == 'manifest.json']
        retained = [r for r in receipt['files'] if r['name'] == spec['name']]
        source_data = referenced(manifest['source_manifest'])
        if (len(original) != 1 or len(retained) != 1
                or original[0].get('sha256') != hashlib.sha256(source_data).hexdigest()
                or type(original[0].get('bytes')) is not int or original[0]['bytes'] != len(source_data)
                or retained[0].get('matches_original_CLI_capture') is not True):
            raise ValueError('Upstream retention manifest or workbook binding drift')
        binding = retained[0]
    data = referenced(spec)
    if (binding.get('sha256') != hashlib.sha256(data).hexdigest()
            or type(binding.get('bytes')) is not int or binding['bytes'] != len(data)):
        raise ValueError('Upstream workbook digest or length missing or different')
    workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        sheet = workbook[spec['sheet']]
        rows = sheet.iter_rows(values_only=True)
        headers = list(next(rows))
        if headers.count(spec['id_column']) != 1:
            raise ValueError('Unique historical application identifier column required')
        column = headers.index(spec['id_column'])
        applications = {}
        for coordinate, row in enumerate(rows, 2):
            number = exact_identifier(row[column])
            if number is not None:
                applications.setdefault(number, []).append(coordinate)
    finally:
        workbook.close()
    result, dois = {}, set()
    for query in manifest['crossref']:
        work = json.loads(referenced(query))
        doi = normalise_doi(query['doi'])
        if (not doi or doi in dois or work.get('status') != 'ok'
                or normalise_doi(work.get('message', {}).get('DOI')) != doi):
            raise ValueError('Unique complete Crossref publication identity required')
        dois.add(doi)
        for funder in work['message'].get('funder', []):
            funder_id = normalise_doi(funder.get('DOI'))
            if funder_id not in funders:
                continue
            for original in funder.get('award', []):
                # A funding assertion must already contain the exact original string.
                if not isinstance(original, str) or original != exact_identifier(original):
                    continue
                matches = applications.get(original, [])
                if not matches:
                    continue
                if len(matches) != 1:
                    raise ValueError('Ambiguous historical application identifier')
                source, target = 'crossref:' + doi, 'nhmrc:' + original
                provenance = dict(relationship='explicit_crossref_funding_to_historical_application',
                    recordKind='historical_nhmrc_application', funderDOI=funder_id,
                    originalAwardNumber=original, authorityROR=authority['id'],
                    authorityRawSHA256=manifest['authority']['sha256'],
                    workbookSourceURL=source_url, workbookRawSHA256=spec['sha256'],
                    sourceManifestSHA256=manifest['source_manifest']['sha256'],
                    workbookSheet=spec['sheet'], identifierColumn=spec['id_column'],
                    workbookRow=matches[0], retentionBatch=manifest['batch'])
                row = dict(RelationshipKind='publication_government_award_reference',
                    SourceWorkID=source, PublicationDOI=doi, PublicationPMID='',
                    ReferenceType=json.dumps(provenance, separators=(',', ':'), ensure_ascii=False),
                    FromKey='doi:' + doi, ToKey=target, FromLabel=funder_id, ToLabel=original,
                    ORCID='', ORCIDStatus='Absent', ROR=authority['id'],
                    IdentityStatus='Source-supported', SourceURL=query['url'],
                    ObservedUTC=query['observed_utc'], RawSHA256=query['sha256'],
                    SourceVersion=manifest['batch'], ReviewState='Not reviewed',
                    AuthenticationState='Not authenticated')
                key = '|'.join([source, row['RelationshipKind'], row['FromKey'], target])
                row['EvidenceKey'] = key
                if key in result and result[key] != row:
                    raise ValueError('Conflicting historical application assertion')
                result[key] = row
    return sorted(result.values(), key=lambda r: r['EvidenceKey'])
