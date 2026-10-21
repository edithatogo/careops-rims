"""NHMRC application-number representation, separate from grant-ID formats.

RGMS guide p21 identifies APP1234567 as an Application ID. NHMRC's data
dictionary defines the application identifier as seven digits with no prefix;
ARDC defines its NHMRC Grant ID as that application identification number.
The packet projector must pin these originals before calling this qualifier.
This does not decode MRFF IDs or infer the funding issuer from its administrator.
"""
import re
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from award_identifier_crosswalks import qualify_award_alias
from source_relationship_evidence import normalise_doi

RULE_ID = 'nhmrc-application-number-representation-v1'
AUTHORITY_SHA256 = {
    'rgms-guide.pdf': '92c37f512dca324ae2da039f3dea11a69d5f0901044c893d908ea11232477a3a',
    'data-dictionary.xlsx': 'a78740d1d3bd8686128969a7d51f5fee76528f18667648605e135b57467129d0',
    'ardc-nhmrc-terms.html': 'd856d8bb0858b336b2bd86aee504f2c853d82e6a0c7760e7133fe59660fd1bd8',
}


class _InstitutionHTML(HTMLParser):
    """Read explicit fields and typed links, excluding scripts and free text."""
    def __init__(self, text):
        super().__init__()
        self.dois, self.links, self.funding = [], [], []
        self.in_funding = False
        self.row, self.cell = None, None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and a.get('name') == 'citation_doi':
            self.dois.append(normalise_doi(a.get('content')))
        if tag == 'a' and a.get('href'):
            self.links.append(a)
        if tag == 'table' and 'funders_informations_table' in a.get('class', '').split():
            self.in_funding = True
        if self.in_funding and tag == 'tr':
            self.row = []
        if self.in_funding and tag == 'td':
            self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == 'tr' and self.in_funding and self.row:
            self.funding.append(self.row)
            self.row = None
        if tag == 'table':
            self.in_funding = False


def institutional_application_uri(publication_html, project_html, doi, application, project_url):
    """Follow explicit DOI→funding number and publication→project→grant links.

    The exact HTTP URI is retained. No URI scheme canonicalisation, title match,
    inferred ARDC activity or project-register identity is introduced.
    """
    pub, project = _InstitutionHTML(publication_html), _InstitutionHTML(project_html)
    if pub.dois != [normalise_doi(doi)] or not re.fullmatch('[1-9][0-9]{6}', application):
        return None
    rows = [r for r in pub.funding if len(r) == 2
            and r[0] == 'NHMRC National Health and Medical Research Council'
            and application in [s.strip() for s in r[1].split(',')]]
    links = [r for r in pub.links if r.get('rel') == 'UPMProject' and r['href'] == project_url]
    uri = 'http://purl.org/au-research/grants/nhmrc/' + application
    grants = [r for r in project.links if r['href'] == uri]
    return uri if len(rows) == len(links) == len(grants) == 1 else None


def qualify_app(number, source_funder_ror, authority, records):
    """Resolve only an NHMRC assertion to one exact NHMRC application URI.

    Original APP strings remain part of the result and source evidence. An
    NHMRC-administered MRFF award is a different funding namespace. A conflicting
    primary funding assertion must therefore be separated before this call.
    Nonmatching discovery hits are ignored; duplicate exact identities fail.
    """
    if (authority.get('namespace') != 'nhmrc' or not authority.get('ror')
            or source_funder_ror != authority['ror']):
        return {'state': 'unqualified_funder_namespace', 'matches': []}
    if not isinstance(number, str) or not re.fullmatch(r'APP[1-9][0-9]{6}', number):
        return {'state': 'unsupported_application_code', 'matches': []}
    bare = number[3:]
    result = qualify_award_alias({'funder_award_id': bare}, source_funder_ror,
                                 authority, records)
    if result['state'] != 'source_supported_alias':
        return result
    return {**result, 'original_identifier': number,
            'application_number': bare, 'rule': RULE_ID}


def project_packet(folder, publications, trusted_authority_sha256, *, expected_batch):
    """Derive edges from originals; the authority receipt is pinned outside packet."""
    root = Path(folder)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if (manifest.get('kind') != 'nhmrc_app_crosswalk_retention_v1'
            or manifest.get('complete') is not True or manifest.get('namespace') != 'nhmrc'):
        raise ValueError('Complete APP source packet required')
    if not isinstance(expected_batch, str) or not expected_batch or manifest.get('batch') != expected_batch:
        raise ValueError('Independently selected batch identity required')
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
            or manifest['crossref'] != policy['crossref'] or manifest['ardc'] != policy['ardc']
            or manifest.get('institutional', []) != policy.get('institutional', [])):
        raise ValueError('Externally pinned source catalogue drift')
    if policy['rule'] != RULE_ID or policy['guide_page'] != 21:
        raise ValueError('Application representation policy drift')
    for filename, digest in AUTHORITY_SHA256.items():
        if hashlib.sha256(raw(filename)).hexdigest() != digest:
            raise ValueError('Application representation primary authority drift')
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
                match = qualify_app(number, authority['id'], {'ror': authority['id'], 'namespace': 'nhmrc'}, records)
                institutional = None
                if match['state'] == 'no_exact_identifier' and re.fullmatch(r'APP[1-9][0-9]{6}', number):
                    candidates = [s for s in policy.get('institutional', [])
                                  if s['doi'] == doi and s['original_identifier'] == number]
                    if len(candidates) == 1:
                        candidate = candidates[0]
                        uri = institutional_application_uri(
                            raw(candidate['publication_filename']).decode(),
                            raw(candidate['project_filename']).decode(), doi, number[3:],
                            candidate['project_url'])
                        if uri:
                            institutional = candidate
                if institutional is None and match['state'] != 'source_supported_alias':
                    continue
                if institutional is None:
                    uri = match['matches'][0]['award_uri']
                source = 'crossref:' + doi
                key = '|'.join([source, 'publication_award_crosswalk', 'doi:' + doi, uri])
                provenance = dict(relationship='issuer_defined_application_representation', funderDOI=fid,
                    awardNumber=number, applicationNumber=number[3:], rule=RULE_ID,
                    ruleAuthoritySHA256=trusted_authority_sha256, guideSHA256=AUTHORITY_SHA256['rgms-guide.pdf'], guidePage=21,
                    dictionarySHA256=AUTHORITY_SHA256['data-dictionary.xlsx'],
                    registryTermsSHA256=AUTHORITY_SHA256['ardc-nhmrc-terms.html'], ardcRawSHA256=lookup['sha256'],
                    ardcSourceURL=lookup['url'], authorityROR=authority['id'],
                    authorityRawSHA256=files['authority-ror.json']['sha256'])
                if institutional:
                    provenance.update(relationship='explicit_institutional_application_identifier_chain',
                        institutionalPublicationURL=institutional['publication_url'],
                        institutionalPublicationSHA256=files[institutional['publication_filename']]['sha256'],
                        institutionalProjectURL=institutional['project_url'],
                        institutionalProjectSHA256=files[institutional['project_filename']]['sha256'],
                        ardcExactIdentifierAbsent=True)
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
                    raise ValueError('Conflicting repeated APP assertion')
                rows[key] = row
    return sorted(rows.values(), key=lambda r: r['EvidenceKey'])
