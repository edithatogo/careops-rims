"""Explicit repository/publisher/protocol paths for remaining NHMRC APP codes.

These source qualifiers complement the funder-DOI path. They do not infer an
issuer from an agency name, author, title or the numeric suffix alone. A target
without an exact registry identity remains a historical government application
reference; no ARDC URI or current grant status is invented.
"""
import copy
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path

import openpyxl

from government_award_crosswalks import exact_identifier
from nhmrc_app_crosswalks import _InstitutionHTML
from nhmrc_app_crosswalks import AUTHORITY_SHA256, qualify_app
from qualify_protocol_award_metadata import parse_cover
from source_relationship_evidence import normalise_doi

RULE_ID = 'nhmrc-explicit-application-source-paths-v1'


class SourceHTML(_InstitutionHTML):
    def __init__(self, text):
        self.pmids, self.funding_text = [], []
        self._funding_depth = 0
        super().__init__(text)

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        a = dict(attrs)
        if tag == 'meta' and a.get('name') == 'citation_pmid':
            self.pmids.append(a.get('content'))
        if tag == 'section':
            if self._funding_depth:
                self._funding_depth += 1
            elif a.get('data-title') == 'Funding':
                self._funding_depth = 1

    def handle_data(self, data):
        super().handle_data(data)
        if self._funding_depth:
            self.funding_text.append(data)

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == 'section' and self._funding_depth:
            self._funding_depth -= 1


def application_number(code):
    if not isinstance(code, str) or not re.fullmatch(r'APP[1-9][0-9]{6}', code):
        raise ValueError('Exact issuer-defined APP representation required')
    return code[3:]


def publication_identity(html, doi, pmid=None):
    """Require an explicit DOI, plus PMID when that source supplies the bridge."""
    doc = SourceHTML(html)
    if not normalise_doi(doi) or doc.dois != [normalise_doi(doi)]:
        raise ValueError('Publication DOI missing, conflicting or duplicated')
    if pmid is not None and doc.pmids != [pmid]:
        raise ValueError('Publication PMID missing, conflicting or duplicated')
    return doc


def repository_project_grant(publication_html, project_html, doi, pmid,
                             code, project_url):
    """Follow a typed publication→project relation and its explicit grant URI.

    The returned HTTP URI is the actual source string, not a generated registry
    identity. A separately qualified ARDC record can provide its own target URI.
    """
    number = application_number(code)
    pub = publication_identity(publication_html, doi, pmid)
    project = SourceHTML(project_html)
    linked = [a for a in pub.links if a.get('rel') == 'UPMProject'
              and a['href'] == project_url]
    uri = 'http://purl.org/au-research/grants/nhmrc/' + number
    grants = [a for a in project.links if a['href'] == uri]
    if len(linked) != 1 or len(grants) != 1:
        raise ValueError('Explicit unique publication/project/grant path required')
    return {'application_number': number, 'original_identifier': code,
            'source_grant_uri': uri, 'namespace': 'nhmrc'}


def repository_direct_grant(publication_html, doi, pmid, code):
    """Retain the institution's exact URI, including its uppercase namespace.

    This asserts what the source records. It does not canonicalise that URI or
    claim an ARDC record exists. Government-record qualification is separate.
    """
    number = application_number(code)
    pub = publication_identity(publication_html, doi, pmid)
    uri = 'http://purl.org/au-research/grants/NHMRC/' + number
    links = [a for a in pub.links if a['href'] == uri]
    if len(links) != 1:
        raise ValueError('Explicit unique institutional grant reference required')
    return {'application_number': number, 'original_identifier': code,
            'source_grant_uri': uri, 'namespace': 'nhmrc',
            'target_kind': 'historical_nhmrc_application'}


def publisher_investigator_application(publisher_html, identity_html, doi, pmid, code):
    """Require the publisher's funding clause and an independent PMID/DOI bridge.

    Only the explicit NHMRC Investigator Grant clause qualifies this path. A
    funding-body name elsewhere in an article cannot assign its namespace.
    The resulting number must still match one official APP ID record.
    """
    number = application_number(code)
    publication_identity(identity_html, doi, pmid)
    pub = publication_identity(publisher_html, doi)
    funding = ' '.join(' '.join(pub.funding_text).split())
    pattern = (r'National Health and Medical Research Council of Australia '
               r'Investigator Grant \((' + re.escape(code) + r'), awarded to [^)]+\)')
    if len(re.findall(pattern, funding)) != 1:
        raise ValueError('Explicit unique publisher NHMRC application clause required')
    return {'application_number': number, 'original_identifier': code,
            'namespace': 'nhmrc', 'target_kind': 'historical_nhmrc_application'}


def government_application(workbook_bytes, sheet, number):
    """Return the unique official source row; never match a title or researcher."""
    if not re.fullmatch(r'[1-9][0-9]{6}', number):
        raise ValueError('Exact seven-digit application number required')
    workbook = openpyxl.load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=True)
    try:
        rows = workbook[sheet].iter_rows(values_only=True)
        headings = list(next(rows))
        if headings.count('APP ID') != 1:
            raise ValueError('Unique official application identifier column required')
        column = headings.index('APP ID')
        matches = [row_number for row_number, row in enumerate(rows, 2)
                   if exact_identifier(row[column]) == number]
    finally:
        workbook.close()
    if len(matches) != 1:
        raise ValueError('Government application missing or ambiguous')
    return {'application_number': number, 'sheet': sheet,
            'identifier_column': 'APP ID', 'row': matches[0],
            'target_key': 'nhmrc:' + number,
            'target_kind': 'historical_nhmrc_application'}


def protocol_application(page_text, code):
    """Qualify the explicit older NHMRC CTCS award on the same protocol cover.

    The adjacent MRFF application remains excluded. Reuse the already-qualified
    cover identity and version; this extraction adds no trial/review decision.
    """
    number = application_number(code)
    facts = parse_cover(page_text)
    cover = ' '.join(page_text.split('\f', 1)[0].split())
    funding = cover.split('Funding source', 1)[1]
    pattern = (r'National Health and Medical Research Council \(NHMRC\) '
               r'Clinical Trials and Cohort Studies funding grant '
               r'\(Award ID: (' + re.escape(code) + r')\)')
    if len(re.findall(pattern, funding)) != 1:
        raise ValueError('Explicit unique NHMRC CTCS APP award clause required')
    return {**facts, 'anchor_application_number': facts['original_application_id'],
            'original_application_id': code, 'original_identifier': code, 'application_number': number,
            'target_kind': 'historical_nhmrc_application'}


def project_packet(folder, previous_rows, publications, trusted_policy_sha256):
    """Project all qualified paths from pinned originals and accepted source rows.

    Existing PubMed/protocol source facts are reused, not corrected or replaced.
    A new edge carries the independent source and the original reference label.
    The protocol retains all four existing publication identities, including
    currently unmapped ones. This local mirror is not the deployed runtime.
    """
    root = Path(folder)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if (manifest.get('kind') != 'nhmrc_explicit_application_sources_v1'
            or manifest.get('complete') is not True):
        raise ValueError('Complete remaining-application source packet required')
    files = {f['name']: f for f in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate source file')
    pinned = None

    def raw(name):
        if Path(name).name != name or name not in files:
            raise ValueError('Exact source filename required')
        info = files[name]
        if pinned is not None and name != 'rule-authority.json' and info != pinned.get(name):
            raise ValueError('Externally pinned source identity drift')
        b = (root / name).read_bytes()
        if len(b) != info['bytes'] or hashlib.sha256(b).hexdigest() != info['sha256']:
            raise ValueError('Source hash or length drift')
        return b

    policy_bytes = raw('rule-authority.json')
    if (not re.fullmatch('[0-9a-f]{64}', trusted_policy_sha256 or '')
            or hashlib.sha256(policy_bytes).hexdigest() != trusted_policy_sha256):
        raise ValueError('External source-policy digest required')
    policy = json.loads(policy_bytes)
    pinned = {f['name']: f for f in policy['source_files']}
    if (len(pinned) != len(policy['source_files']) or policy.get('rule') != RULE_ID
            or policy.get('namespace') != 'nhmrc' or policy['batch'] != manifest['batch']):
        raise ValueError('Source-policy identity drift')
    for filename, digest in AUTHORITY_SHA256.items():
        if hashlib.sha256(raw(filename)).hexdigest() != digest:
            raise ValueError('Issuer application-representation authority drift')
    authority = json.loads(raw('authority-ror.json'))
    if not any(x.get('type') == 'website' and x.get('value') == 'https://www.nhmrc.gov.au/'
               for x in authority['links']):
        raise ValueError('Qualified NHMRC namespace authority required')
    upstream_bytes = raw('nhmrc-source-manifest.json')
    upstream = json.loads(upstream_bytes)
    retention = json.loads(raw('nhmrc-native-run-verification.json'))
    originals = [f for f in retention['files'] if f['name'] == 'manifest.json']
    if (upstream.get('format') != 'rims-funding-native-workbook-commit-v1'
            or upstream.get('source') != 'nhmrc' or upstream.get('complete') is not True
            or upstream.get('fidelity') != 'original_binary_content_exact_saved_readback'
            or retention.get('status') != 'PASS_NATIVE_ORIGINAL_WORKBOOK_ARCHIVE'
            or retention.get('run') != upstream.get('run') or not upstream.get('run')
            or len(originals) != 1 or originals[0]['bytes'] != len(upstream_bytes)
            or originals[0]['sha256'] != hashlib.sha256(upstream_bytes).hexdigest()):
        raise ValueError('Original government archive/source binding drift')
    index = {}
    for pub in publications:
        if doi := normalise_doi(pub.get('DOI')):
            index.setdefault(doi, set()).add(pub['CanonicalKey'])
    result = []
    for case in policy['cases']:
        code = case['original_identifier']; number = application_number(code)
        mode = case['kind']
        provenance = dict(rule=RULE_ID, ruleAuthoritySHA256=trusted_policy_sha256,
            originalApplicationID=code, applicationNumber=number,
            authorityROR=authority['id'], authorityRawSHA256=files['authority-ror.json']['sha256'],
            representationAuthorities=AUTHORITY_SHA256, retentionBatch=manifest['batch'])
        government = None
        if mode != 'repository_project':
            originals = [f for f in upstream['files'] if f['name'] == case['workbook_original_name']]
            retained = [f for f in retention['files'] if f['name'] == case['workbook_original_name']]
            info = files[case['workbook']]
            if (len(originals) != 1 or len(retained) != 1
                    or originals[0]['source_url'] != case['workbook_source_url']
                    or retained[0].get('matches_original_CLI_capture') is not True
                    or retained[0]['sha256'] != info['sha256'] or retained[0]['bytes'] != info['bytes']):
                raise ValueError('Government workbook origin/digest binding drift')
            government = government_application(raw(case['workbook']), 'GRANTS DATA', number)
            provenance.update(recordKind=government['target_kind'],
                workbookRawSHA256=files[case['workbook']]['sha256'],
                workbookSourceURL=case['workbook_source_url'], workbookSheet='GRANTS DATA',
                identifierColumn='APP ID', workbookRow=government['row'])
        if mode == 'protocol_government':
            facts = protocol_application(raw(case['cover']).decode(), code)
            pdf = raw(case['pdf'])
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('Original protocol PDF required')
            anchors = [r for r in previous_rows if r['RelationshipKind'] == 'study_award_reference'
                       and r['FromKey'] == facts['study_identifier']
                       and r['ToKey'] == 'https://purl.org/au-research/grants/nhmrc/' + facts['anchor_application_number']]
            if len(anchors) != 1:
                raise ValueError('Existing qualified protocol/study binding required')
            anchor = anchors[0]; proof = json.loads(anchor['ReferenceType'])
            if (proof['protocolRawSHA256'] != files[case['pdf']]['sha256']
                    or proof['protocolIdentifier'] != facts['protocol_identifier']
                    or anchor['SourceVersion'] != facts['protocol_version']):
                raise ValueError('Protocol binding/source/version drift')
            provenance.update(relationship='explicit_protocol_APP_to_historical_application',
                priorProtocolBindingEvidenceKey=anchor['EvidenceKey'],
                protocolRawSHA256=proof['protocolRawSHA256'], protocolPage=1,
                protocolIdentifier=facts['protocol_identifier'], protocolVersion=facts['protocol_version'],
                studySourceRawSHA256=proof['studySourceRawSHA256'],
                studyRegisterSourceSHA256=proof['studyRegisterSourceSHA256'])
            templates = [r for r in previous_rows if r['SourceWorkID'] == anchor['SourceWorkID']
                         and r['ToKey'] == anchor['ToKey'] and r['RelationshipKind'] in
                         {'study_award_reference', 'publication_study_award_chain'}]
            referenced = {r['PublicationPMID'] for r in previous_rows
                          if r['RelationshipKind'] == 'publication_study_reference'
                          and r['ToKey'] == facts['study_identifier'] and r['PublicationPMID']}
            chains = [r for r in templates if r['RelationshipKind'] == 'publication_study_award_chain']
            if (len(templates) != len(referenced) + 1
                    or {r['PublicationPMID'] for r in chains} != referenced
                    or len(chains) != len(referenced)):
                raise ValueError('Existing protocol publication-reference coverage drift')
            for template in templates:
                row = copy.deepcopy(template); suffix = '|' + template['ToKey']
                if not row['EvidenceKey'].endswith(suffix):
                    raise ValueError('Existing protocol evidence-key contract drift')
                details = copy.deepcopy(provenance)
                original = json.loads(template['ReferenceType'])
                if 'publicationReferenceEvidence' in original:
                    details['publicationReferenceEvidence'] = original['publicationReferenceEvidence']
                row.update(EvidenceKey=row['EvidenceKey'][:-len(template['ToKey'])] + government['target_key'],
                    ToKey=government['target_key'], ToLabel=code,
                    ReferenceType=json.dumps(details, separators=(',', ':')))
                result.append(row)
            continue

        doi = normalise_doi(case['doi']); pmid = case['pmid']
        refs = [r for r in previous_rows if r['RelationshipKind'] == 'publication_grant_reference'
                and r['SourceWorkID'] == 'pubmed:' + pmid and r['PublicationPMID'] == pmid
                and r['ToLabel'].endswith(' | ' + code)]
        if len(refs) != 1:
            raise ValueError('Unique original PubMed application assertion required')
        ref = refs[0]
        provenance.update(originalReferenceEvidenceKey=ref['EvidenceKey'],
            originalReferenceLabel=ref['ToLabel'], originalReferenceSourceVersion=ref['SourceVersion'],
            publicationDOI=doi, publicationPMID=pmid)
        html = raw(case['publication']).decode()
        if mode == 'repository_project':
            fact = repository_project_grant(html, raw(case['project']).decode(), doi, pmid,
                                             code, case['project_url'])
            registry = json.loads(raw(case['registry']))
            if (registry['status'] != 'OK' or registry['code'] != '200'
                    or registry['data']['offset'] != 0
                    or registry['data']['numFound'] != len(registry['data']['records'])):
                raise ValueError('Complete grant registry source required')
            alias = qualify_app(code, authority['id'], dict(namespace=fact['namespace'], ror=authority['id']),
                                registry['data']['records'])
            if alias['state'] != 'source_supported_alias':
                raise ValueError('Exact unique registry grant identity required')
            target = alias['matches'][0]['award_uri']; kind = 'publication_award_crosswalk'
            provenance.update(relationship='explicit_repository_project_grant_application',
                institutionalGrantURI=fact['source_grant_uri'], projectURL=case['project_url'],
                projectRawSHA256=files[case['project']]['sha256'], registryRawSHA256=files[case['registry']]['sha256'])
        elif mode == 'repository_government':
            fact = repository_direct_grant(html, doi, pmid, code)
            target = government['target_key']; kind = 'publication_government_award_reference'
            provenance.update(relationship='explicit_repository_grant_to_historical_application',
                institutionalGrantURI=fact['source_grant_uri'],
                sourceAgencyDiscrepancy=ref['ToLabel'].startswith('Welcome Trust | '))
        elif mode == 'publisher_government':
            publisher_investigator_application(html, raw(case['identity']).decode(), doi, pmid, code)
            target = government['target_key']; kind = 'publication_government_award_reference'
            provenance.update(relationship='explicit_publisher_APP_to_historical_application',
                identitySourceURL=case['identity_url'], identityRawSHA256=files[case['identity']]['sha256'])
        else:
            raise ValueError('Unsupported explicit source path')
        source = ('publisher:' if mode == 'publisher_government' else 'repository:') + doi
        keys = index.get(doi, set())
        result.append(dict(EvidenceKey='|'.join([source, kind, 'doi:' + doi, target]),
            RelationshipKind=kind, SourceWorkID=source, PublicationDOI=doi, PublicationPMID=pmid,
            ReferenceType=json.dumps(provenance, separators=(',', ':')), FromKey='doi:' + doi,
            ToKey=target, FromLabel='NHMRC application namespace', ToLabel=code,
            ORCID='', ORCIDStatus='Absent', ROR=authority['id'], IdentityStatus='Source-supported',
            SourceURL=case['source_url'], ObservedUTC=case['observed_utc'],
            RawSHA256=files[case['publication']]['sha256'], SourceVersion=manifest['batch'],
            ReviewState='Not reviewed', AuthenticationState='Not authenticated',
            SourceProvider='Publisher' if mode == 'publisher_government' else 'Institutional repository',
            CanonicalKey=next(iter(keys)) if len(keys) == 1 else None, CanonicalMatchCount=len(keys),
            AdmissionState='Source-supported' if len(keys) == 1 else 'Ambiguous DOI' if keys else 'Unmapped publication'))
    if len({r['EvidenceKey'] for r in result}) != len(result):
        raise ValueError('Duplicate projected evidence identity')
    return sorted(result, key=lambda r: r['EvidenceKey'])
