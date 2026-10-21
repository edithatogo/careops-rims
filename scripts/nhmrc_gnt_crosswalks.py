"""NHMRC RGMS grant-code crosswalks, qualified against retained primary evidence.

The 2017 guide p43 defines GNT plus seven digits (six-digit numbers are padded).
The migration notice establishes RGMS use for existing grants on 1 September 2021.
Year-only registry dates must place that date strictly inside the funding interval.
This optional policy never changes exact-alias qualification or original strings.
"""
import hashlib
import json
import re
from pathlib import Path

from award_identifier_crosswalks import qualify_award_alias
from source_relationship_evidence import normalise_doi

RULE_ID = 'nhmrc-rgms-gnt-v1'
GUIDE_SHA256 = '92c37f512dca324ae2da039f3dea11a69d5f0901044c893d908ea11232477a3a'
GUIDE_URL = 'https://www.nhmrc.gov.au/sites/default/files/2019-03/rgms-user-guide-grant-administration.pdf'
MIGRATION_URL = 'https://www.nhmrc.gov.au/sapphire/sapphire-recent-updates'


def qualify_gnt(number, source_funder_ror, authority, records):
    """Use the explicit encoding only for an independently bound NHMRC funder."""
    if authority.get('namespace') != 'nhmrc' or source_funder_ror != authority.get('ror'):
        return {'state': 'unqualified_funder_namespace', 'matches': []}
    if not isinstance(number, str) or not re.fullmatch(r'GNT(?:[1-9][0-9]{6}|0[1-9][0-9]{5})', number):
        return {'state': 'unsupported_grant_code', 'matches': []}
    bare = number[3:] if number[3] != '0' else number[4:]
    # Do not discard ambiguous identities before checking their historical dates.
    match = qualify_award_alias({'funder_award_id': bare}, source_funder_ror, authority, records)
    if match['state'] != 'source_supported_alias':
        return match
    selected = [r for r in records if str(r['id']) == match['matches'][0]['record_id']]
    record = selected[0]
    start, end = record.get('startDate'), record.get('endDate')
    if (type(start) is not int or type(end) is not int
            or not 1900 <= start <= 2020 or not 2022 <= end <= 9999):
        return {'state': 'historical_scope_unproved', 'matches': []}
    return {**match, 'grant_number': bare, 'start_year': start, 'end_year': end}


def project_packet(folder, publications, trusted_authority_sha256):
    """Derive edges from originals; the authority receipt is pinned outside packet."""
    root = Path(folder)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if (manifest.get('kind') != 'nhmrc_gnt_crosswalk_retention_v1'
            or manifest.get('complete') is not True or manifest.get('namespace') != 'nhmrc'):
        raise ValueError('Complete GNT source packet required')
    files = {f['name']: f for f in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate source file')
    pinned_files = None

    def raw(name):
        if Path(name).name != name or name not in files:
            raise ValueError('Exact retained filename required')
        if pinned_files is not None and name != 'rule-authority.json' and files[name] != pinned_files.get(name):
            raise ValueError('Externally pinned source identity drift')
        b = (root / name).read_bytes()
        if len(b) != files[name]['bytes'] or hashlib.sha256(b).hexdigest() != files[name]['sha256']:
            raise ValueError('Retained source hash or length drift')
        return b

    policy_bytes = raw('rule-authority.json')
    if not re.fullmatch('[0-9a-f]{64}', trusted_authority_sha256 or '') or hashlib.sha256(policy_bytes).hexdigest() != trusted_authority_sha256:
        raise ValueError('External rule authority digest required')
    policy = json.loads(policy_bytes)
    pinned_files = {f['name']: f for f in policy['source_files']}
    if (len(pinned_files) != len(policy['source_files'])
            or manifest['crossref'] != policy['crossref'] or manifest['ardc'] != policy['ardc']):
        raise ValueError('Externally pinned source catalogue drift')
    if (policy['rule'] != RULE_ID or policy['guide_url'] != GUIDE_URL
            or policy['guide_sha256'] != GUIDE_SHA256 or policy['guide_page'] != 43
            or policy['migration_url'] != MIGRATION_URL
            or hashlib.sha256(raw('guide.pdf')).hexdigest() != GUIDE_SHA256
            or hashlib.sha256(raw('migration-web-readback.json')).hexdigest() != policy['migration_sha256']):
        raise ValueError('Primary rule authority drift')
    authority = json.loads(raw('authority-ror.json'))
    if not any(x.get('type') == 'website' and x.get('value') == 'https://www.nhmrc.gov.au/' for x in authority['links']):
        raise ValueError('NHMRC namespace authority required')
    funders = {normalise_doi('10.13039/' + v) for x in authority['external_ids'] if x['type'] == 'fundref' for v in x['all']}
    index = {}
    for p in publications:
        if doi := normalise_doi(p.get('DOI')):
            index.setdefault(doi, set()).add(p['CanonicalKey'])
    lookups = {}
    for q in manifest['ardc']:
        d = json.loads(raw(q['filename']))
        if (q['original_identifier'] in lookups or q['sha256'] != files[q['filename']]['sha256']
                or q['complete'] is not True or d['status'] != 'OK' or d['code'] != '200'
                or d['data']['offset'] != 0 or d['data']['numFound'] != len(d['data']['records'])):
            raise ValueError('Incomplete or conflicting grant lookup')
        lookups[q['original_identifier']] = (q, d['data']['records'])
    rows = {}
    for q in manifest['crossref']:
        d = json.loads(raw(q['filename'])); work = d.get('message', {})
        doi = normalise_doi(q['doi'])
        if (not doi or d.get('status') != 'ok' or normalise_doi(work.get('DOI')) != doi
                or q['sha256'] != files[q['filename']]['sha256']):
            raise ValueError('Publication identity/provenance drift')
        for funder in work.get('funder', []):
            fid = normalise_doi(funder.get('DOI'))
            if fid not in funders:
                continue
            for number in funder.get('award', []):
                if number not in lookups:
                    continue
                lookup, records = lookups[number]
                match = qualify_gnt(number, authority['id'], {'ror': authority['id'], 'namespace': 'nhmrc'}, records)
                if match['state'] != 'source_supported_alias':
                    continue
                uri = match['matches'][0]['award_uri']; source = 'crossref:' + doi
                key = '|'.join([source, 'publication_award_crosswalk', 'doi:' + doi, uri])
                provenance = dict(relationship='issuer_defined_grant_code', funderDOI=fid,
                    awardNumber=number, grantNumber=match['grant_number'], rule=RULE_ID,
                    ruleAuthoritySHA256=trusted_authority_sha256, guideSHA256=GUIDE_SHA256,
                    guideURL=GUIDE_URL, guidePage=43, migrationURL=MIGRATION_URL,
                    migrationSHA256=policy['migration_sha256'], grantStartYear=match['start_year'],
                    grantEndYear=match['end_year'], ardcRawSHA256=lookup['sha256'],
                    ardcSourceURL=lookup['url'], authorityROR=authority['id'],
                    authorityRawSHA256=files['authority-ror.json']['sha256'])
                keys = index.get(doi, set())
                row = dict(EvidenceKey=key, RelationshipKind='publication_award_crosswalk',
                    SourceWorkID=source, PublicationDOI=doi, PublicationPMID='',
                    ReferenceType=json.dumps(provenance, separators=(',', ':'), ensure_ascii=False),
                    FromKey='doi:' + doi, ToKey=uri, FromLabel=fid, ToLabel=number,
                    ORCID='', ORCIDStatus='Absent', ROR=authority['id'], IdentityStatus='Source-supported',
                    SourceURL=q['url'], ObservedUTC=q['observed_utc'], RawSHA256=q['sha256'],
                    SourceVersion=manifest['batch'], ReviewState='Not reviewed', AuthenticationState='Not authenticated',
                    SourceProvider='Crossref', CanonicalKey=next(iter(keys)) if len(keys) == 1 else '',
                    CanonicalMatchCount=len(keys), AdmissionState='Source-supported' if len(keys) == 1 else 'Ambiguous DOI' if keys else 'Unmapped publication')
                if key in rows and rows[key] != row:
                    raise ValueError('Conflicting repeated GNT assertion')
                rows[key] = row
    return sorted(rows.values(), key=lambda r: r['EvidenceKey'])
