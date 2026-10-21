"""Project typed grant-registry publication references through exact handles."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

OAI = '{http://www.openarchives.org/OAI/2.0/}'
RIF = '{http://ands.org.au/standards/rif-cs/registryObjects}'
DOI_FIELDS = ('dc.identifier.doi', 'unsw.identifier.doiPublisher')


def normalized_doi(value):
    value = value.strip().lower()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/'):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ''


def project_packet(folder):
    root = Path(folder)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if (manifest.get('kind') != 'ardc_publication_handle_retention_v1'
            or manifest.get('namespace') != 'nhmrc' or manifest.get('complete') is not True):
        raise ValueError('Complete qualified registry packet required')
    files = {r['name']: r for r in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate registry source file')

    def raw(name):
        if Path(name).name != name or name not in files:
            raise ValueError('Exact registry source filename required')
        value = (root / name).read_bytes()
        if len(value) != files[name]['bytes'] or hashlib.sha256(value).hexdigest() != files[name]['sha256']:
            raise ValueError('Registry source byte/hash drift')
        return value

    authority_ref = manifest['authority']
    authority = json.loads(raw(authority_ref['name']))
    if authority_ref['sha256'] != files[authority_ref['name']]['sha256']:
        raise ValueError('Registry authority provenance drift')
    if not any(r.get('type') == 'website' and r.get('value') == 'https://www.nhmrc.gov.au/'
               for r in authority['links']):
        raise ValueError('NHMRC namespace authority required')
    funders = {'10.13039/' + n for r in authority['external_ids'] if r['type'] == 'fundref' for n in r['all']}
    grants = {}
    for spec in manifest['grants']:
        record_id, number = spec['record_id'], spec['original_identifier']
        if record_id in grants:
            raise ValueError('Duplicate registry grant record')
        grant_uri = 'https://purl.org/au-research/grants/nhmrc/' + number
        lookup = json.loads(raw(spec['ardc_name']))
        data = lookup['data']
        if (spec['grant_uri'] != grant_uri or lookup['status'] != 'OK' or lookup['code'] != '200'
                or data['offset'] != 0 or data['numFound'] != len(data['records'])):
            raise ValueError('Incomplete or misidentified grant lookup')
        matches = [r for r in data['records'] if r.get('type') == 'grant' and r.get('purl') == grant_uri
                   and number in r.get('identifiers', [])]
        if len(matches) != 1:
            raise ValueError('Exact canonical grant identifier required')
        xml = ET.fromstring(raw(spec['rifcs_name']))
        records = xml.findall(OAI + 'GetRecord/' + OAI + 'record')
        if xml.tag != OAI + 'OAI-PMH' or len(records) != 1 or xml.findall(OAI + 'error'):
            raise ValueError('Exact successful OAI record required')
        record = records[0]
        header = record.find(OAI + 'header')
        if header is None or header.get('status') == 'deleted' or header.findtext(OAI + 'identifier') != 'oai:ands.org.au::' + record_id:
            raise ValueError('OAI record identity drift')
        activities = record.findall(OAI + 'metadata/' + RIF + 'registryObjects/' + RIF + 'registryObject/' + RIF + 'activity')
        if len(activities) != 1 or activities[0].get('type') != 'grant':
            raise ValueError('Typed registry grant required')
        activity = activities[0]
        numbers = [e.text for e in activity.findall(RIF + 'identifier') if e.get('type') == 'nhmrc']
        if numbers != [number]:
            raise ValueError('Namespace-qualified grant identifier drift')
        funding = [normalized_doi(e.findtext(RIF + 'key', '')) for e in activity.findall(RIF + 'relatedObject')
                   if any(r.get('type') == 'isFundedBy' for r in e.findall(RIF + 'relation'))]
        if not any(f in funders for f in funding):
            raise ValueError('Explicit grant funder namespace required')
        references = {e.text for info in activity.findall(RIF + 'relatedInfo') if info.get('type') == 'publication'
                      for e in info.findall(RIF + 'identifier') if e.get('type') == 'URI'}
        grants[record_id] = (spec, references, header.findtext(OAI + 'datestamp', ''))
    rows = {}
    for spec in manifest['publications']:
        grant, references, version = grants[spec['record_id']]
        uri = spec['publication_uri']
        parsed = urlparse(uri)
        if (parsed.scheme not in ('http', 'https') or parsed.netloc not in ('handle.unsw.edu.au', 'hdl.handle.net')
                or parsed.query or parsed.fragment or parsed.path.lstrip('/') != spec['handle'] or uri not in references):
            raise ValueError('Exact typed publication handle required')
        item = json.loads(raw(spec['name']))
        kind = spec.get('metadata_kind', 'dspace')
        if kind == 'dspace':
            valid = item.get('type') == 'item' and item.get('id') == spec['item_id']
            identifiers = [v['value'] for key in DOI_FIELDS for v in item.get('metadata', {}).get(key, [])]
        elif kind == 'figshare':
            valid = (type(item.get('id')) is int and str(item['id']) == spec['item_id']
                     and item.get('is_public') is True and item.get('is_confidential') is False
                     and item.get('defined_type_name') == 'journal contribution')
            identifiers = [r['identifier'] for r in item.get('related_materials', [])
                           if r.get('identifier_type') == 'DOI' and r.get('relation') == 'IsIdenticalTo']
        else:
            raise ValueError('Unqualified repository metadata contract')
        if not valid or item.get('handle') != spec['handle']:
            raise ValueError('Resolved repository identity drift')
        dois = {normalized_doi(value) for value in identifiers}
        dois.discard('')
        if len(dois) > 1 or (kind == 'dspace' and len(dois) != 1):
            raise ValueError('One explicit repository DOI required')
        doi = next(iter(dois)) if dois else ''
        identity = 'doi:' + doi if doi else 'handle:' + spec['handle']
        source = 'ardc:' + spec['record_id']
        key = '|'.join((source, 'grant_related_publication', identity, grant['grant_uri'], uri))
        proof = dict(relationship='RIF-CS relatedInfo publication', publicationHandleURI=uri,
            resolvedHandle=spec['handle'], repositoryItemID=spec['item_id'], repositoryDOI=doi,
            repositoryMetadataKind=kind,
            repositoryDOIState='Explicit repository DOI identity' if doi else 'No explicit identity-equivalent DOI',
            repositoryRelatedMaterials=item.get('related_materials', []) if kind == 'figshare' else [],
            repositoryMetadataSHA256=files[spec['name']]['sha256'], repositoryMetadataURL=spec['final_url'],
            grantIdentifierNamespace='nhmrc', grantOriginalIdentifier=grant['original_identifier'],
            ardcRawSHA256=files[grant['ardc_name']]['sha256'], authorityRawSHA256=authority_ref['sha256'],
            retentionBatch=manifest['batch'])
        row = dict(RelationshipKind='grant_related_publication', SourceWorkID=source,
            PublicationDOI=doi, PublicationPMID='', ReferenceType=json.dumps(proof, separators=(',', ':')),
            FromKey=identity, ToKey=grant['grant_uri'], FromLabel=doi or spec['handle'], ToLabel=grant['original_identifier'],
            ORCID='', ORCIDStatus='Absent', ROR=authority['id'], IdentityStatus='Source-supported',
            SourceURL=grant['rifcs_url'], ObservedUTC=manifest['qualified_utc'],
            RawSHA256=files[grant['rifcs_name']]['sha256'], SourceVersion=version,
            ReviewState='Not reviewed', AuthenticationState='Not authenticated')
        row['EvidenceKey'] = key
        if key in rows:
            raise ValueError('Duplicate registry publication mapping')
        rows[key] = row
    return [rows[k] for k in sorted(rows)]
