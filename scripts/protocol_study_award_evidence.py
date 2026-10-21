"""Build explicit clinical-study funding edges from a pinned protocol packet."""
import copy
import hashlib
import json
from pathlib import Path
from qualify_protocol_award_metadata import parse_cover


def project_packet(folder, studies, publication_references):
    root = Path(folder); manifest = json.loads((root / 'manifest.json').read_bytes())
    if manifest.get('kind') != 'protocol_study_award_retention_v1' or not manifest.get('complete'):
        raise ValueError('Complete protocol source packet required')
    files = {r['name']: r for r in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate protocol source file')
    def raw(name):
        if Path(name).name != name or name not in files:
            raise ValueError('Exact protocol source filename required')
        value = (root / name).read_bytes()
        if len(value) != files[name]['bytes'] or hashlib.sha256(value).hexdigest() != files[name]['sha256']:
            raise ValueError('Protocol source byte/hash drift')
        return value
    pdf = raw('protocol.pdf')
    if not pdf.startswith(b'%PDF-'):
        raise ValueError('Original protocol PDF required')
    facts = parse_cover(raw('protocol-page1.txt').decode())
    prepared = json.loads(raw('protocol-facts.json'))
    if facts != prepared:
        raise ValueError('Protocol metadata extraction drift')
    study = json.loads(raw('study-source-envelope.json'))
    body = study['response']['body']['protocolSection']['identificationModule']
    nct = facts['study_identifier'].split(':', 1)[1]
    if (study['response']['statusCode'] != 200 or study['requested_id'] != nct
            or body['nctId'] != nct or body['orgStudyIdInfo']['id'] != facts['protocol_identifier']):
        raise ValueError('Study/protocol identity drift')
    matched_studies = [r for r in studies if r['SourceKey'] == facts['study_identifier']]
    if len(matched_studies) != 1 or matched_studies[0].get('NCTId') != nct:
        raise ValueError('Existing study register binding drift')
    authority = json.loads(raw('authority-ror.json'))
    if not any(x.get('type') == 'website' and x.get('value') == 'https://www.nhmrc.gov.au/' for x in authority['links']):
        raise ValueError('NHMRC namespace authority required')
    grant = json.loads(raw('ardc-grant.json')); data = grant['data']
    if grant['status'] != 'OK' or grant['code'] != '200' or data['offset'] != 0 or data['numFound'] != len(data['records']):
        raise ValueError('Incomplete grant source')
    uri = 'https://purl.org/au-research/grants/nhmrc/' + facts['original_application_id']
    grants = [r for r in data['records'] if r.get('type') == 'grant' and r.get('purl') == uri
              and facts['original_application_id'] in r.get('identifiers', [])]
    if len(grants) != 1:
        raise ValueError('Grant identifier unresolved or ambiguous')
    source = 'protocol:' + facts['study_identifier'] + ':' + facts['protocol_identifier']
    provenance = {'relationship': 'explicit_protocol_funding_source', 'protocolPage': 1,
        'protocolIdentifier': facts['protocol_identifier'], 'protocolIdentifierNamespace': facts['protocol_identifier_namespace'],
        'protocolVersion': facts['protocol_version'], 'protocolRawSHA256': files['protocol.pdf']['sha256'],
        'studySourceRawSHA256': files['study-source-envelope.json']['sha256'],
        'studyRegisterSourceSHA256': matched_studies[0]['SourcePayloadSHA256'],
        'ardcRawSHA256': files['ardc-grant.json']['sha256'], 'authorityRawSHA256': files['authority-ror.json']['sha256'],
        'retentionBatch': manifest['batch']}
    base = dict(EvidenceKey='|'.join([source, 'study_award_reference', facts['study_identifier'], uri]),
        RelationshipKind='study_award_reference', SourceWorkID=source, PublicationDOI='', PublicationPMID='',
        ReferenceType=json.dumps(provenance, separators=(',', ':')), FromKey=facts['study_identifier'], ToKey=uri,
        FromLabel=facts['protocol_identifier'], ToLabel=facts['original_application_id'], ORCID='', ORCIDStatus='Absent',
        ROR=authority['id'], IdentityStatus='Source-supported', SourceURL=manifest['protocol_source_url'],
        ObservedUTC=manifest['observed_utc'], RawSHA256=files['protocol.pdf']['sha256'], SourceVersion=facts['protocol_version'],
        ReviewState='Not reviewed', AuthenticationState='Not authenticated')
    refs = [r for r in publication_references if r['RelationshipKind'] == 'publication_study_reference'
            and r['ToKey'] == facts['study_identifier'] and r['PublicationPMID']]
    result = [base]
    for pmid in sorted({r['PublicationPMID'] for r in refs}):
        row = copy.deepcopy(base); row.update(RelationshipKind='publication_study_award_chain', PublicationPMID=pmid)
        row['EvidenceKey'] = '|'.join([source, row['RelationshipKind'], 'pmid:' + pmid, facts['study_identifier'], uri])
        evidence = [{k: r[k] for k in ['SourceWorkID', 'RawSHA256', 'SourceVersion', 'ReferenceType']}
                    for r in refs if r['PublicationPMID'] == pmid]
        evidence.sort(key=lambda r: (r['SourceWorkID'], r['ReferenceType']))
        row['ReferenceType'] = json.dumps({**provenance, 'publicationReferenceEvidence': evidence}, separators=(',', ':'))
        result.append(row)
    return result
