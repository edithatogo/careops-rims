"""Project publication/award edges from complete retained Crossref and ARDC bytes."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from award_identifier_crosswalks import qualify_award_alias
from source_relationship_evidence import normalise_doi


def project_packet(folder, publications):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    if manifest.get('kind') != 'publication_award_crosswalk_retention_v1' or not manifest.get('complete'):
        raise ValueError('Complete crosswalk source packet required')
    files = {r['name']: r for r in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate source file')
    def read(name):
        if Path(name).name != name or name not in files:
            raise ValueError('Exact manifest file required')
        raw = (folder / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != files[name]['sha256'] or len(raw) != files[name]['bytes']:
            raise ValueError('Retained source hash or length drift')
        return json.loads(raw)
    authority = read(manifest['authority']['name'])
    if manifest['authority']['sha256'] != files[manifest['authority']['name']]['sha256']:
        raise ValueError('Authority provenance hash drift')
    websites = [x['value'] for x in authority.get('links', []) if x.get('type') == 'website']
    if manifest['namespace'] != 'nhmrc' or 'https://www.nhmrc.gov.au/' not in websites:
        raise ValueError('NHMRC funder namespace authority required')
    funders = {normalise_doi('10.13039/' + value) for r in authority['external_ids']
               if r['type'] == 'fundref' for value in r['all']}
    index = {}
    for row in publications:
        doi = normalise_doi(row.get('DOI'))
        if doi:
            index.setdefault(doi, set()).add(row['CanonicalKey'])
    lookups = {}
    for query in manifest['ardc']:
        d = read(query['filename'])
        if query['sha256'] != files[query['filename']]['sha256']:
            raise ValueError('Grant provenance hash drift')
        if (not query['complete'] or d['status'] != 'OK' or d['code'] != '200'
                or d['data']['offset'] != 0 or d['data']['numFound'] != len(d['data']['records'])):
            raise ValueError('Incomplete grant lookup')
        if query['original_identifier'] in lookups:
            raise ValueError('Duplicate grant lookup')
        lookups[query['original_identifier']] = (query, d['data']['records'])
    result = {}
    for query in manifest['crossref']:
        d = read(query['filename']); work = d.get('message', {})
        if query['sha256'] != files[query['filename']]['sha256']:
            raise ValueError('Publication provenance hash drift')
        doi = normalise_doi(query['doi'])
        if d.get('status') != 'ok' or normalise_doi(work.get('DOI')) != doi or not doi:
            raise ValueError('Publication DOI identity drift')
        for funder in work.get('funder', []):
            fid = normalise_doi(funder.get('DOI'))
            if fid not in funders:
                continue
            for number in funder.get('award', []):
                if number not in lookups:
                    continue
                lookup, records = lookups[number]
                match = qualify_award_alias({'funder_award_id': number}, authority['id'],
                    {'ror': authority['id'], 'namespace': manifest['namespace']}, records)
                if match['state'] != 'source_supported_alias':
                    continue
                uri = match['matches'][0]['award_uri']; source = 'crossref:' + doi
                key = '|'.join([source, 'publication_award_crosswalk', 'doi:' + doi, uri])
                keys = index.get(doi, set())
                provenance = {'relationship': 'explicit_publication_award_identifier',
                    'funderDOI': fid, 'awardNumber': number,
                    'ardcRawSHA256': lookup['sha256'], 'ardcSourceURL': lookup['url'],
                    'authorityROR': authority['id'], 'authorityRawSHA256': manifest['authority']['sha256']}
                row = dict(RelationshipKind='publication_award_crosswalk',
                    SourceWorkID=source, PublicationDOI=doi, PublicationPMID='',
                    ReferenceType=json.dumps(provenance, separators=(',', ':'), ensure_ascii=False),
                    FromKey='doi:' + doi, ToKey=uri, FromLabel=fid, ToLabel=number,
                    ORCID='', ORCIDStatus='Absent', ROR=authority['id'],
                    IdentityStatus='Source-supported', SourceURL=query['url'],
                    ObservedUTC=query['observed_utc'], RawSHA256=query['sha256'],
                    SourceVersion=manifest['batch'], ReviewState='Not reviewed',
                    AuthenticationState='Not authenticated', SourceProvider='Crossref',
                    CanonicalKey=next(iter(keys)) if len(keys) == 1 else '',
                    CanonicalMatchCount=len(keys), AdmissionState='Source-supported' if len(keys) == 1
                    else 'Ambiguous DOI' if keys else 'Unmapped publication')
                row['EvidenceKey'] = key
                if key in result and result[key] != row:
                    raise ValueError('Conflicting repeated publication award assertion')
                result[key] = row
    return sorted(result.values(), key=lambda row: row['EvidenceKey'])
