"""Add protocol-qualified study funding and complete clinical-study chains."""
import base64
import copy
import json
import re
from urllib.parse import urlparse


def prepare(document, archive_url, batch, function_source):
    u = urlparse(archive_url)
    if (u.scheme != 'https' or not (u.hostname or '').endswith('.sharepoint.com')
            or u.username is not None or u.password is not None or u.query or u.fragment
            or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained protocol batch required')
    result = copy.deepcopy(document)
    part = next(p for p in result['definition']['parts']
                if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl')
    text = base64.b64decode(part['payload']).decode()
    sites = re.findall(r'StudySite\s*=\s*"((?:[^"\n]|"")*)"\s*,', text)
    if len(sites) != 1 or not archive_url.startswith(sites[0].replace('""', '"') + '/Documents/'):
        raise ValueError('Protocol archive must use the bound study site and Documents library')
    if 'ProtocolStudyAwardProjector=' in text:
        raise ValueError('Existing protocol derivation must be reconciled')
    marker = 'Rows=Table.Buffer(Table.FromRecords(Output & StudyEvidence & PubMedEvidence & AwardAliases & CrossrefAwardEvidence,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'ReadStudy=' not in text or 'StudyRows=' not in text:
        raise ValueError('Qualified source evidence and study reader required')
    additions = ('BeforeProtocol=List.Buffer(Output & StudyEvidence & PubMedEvidence & AwardAliases & CrossrefAwardEvidence),\n'
        '    ProtocolStudyAwardProjector=' + function_source.rstrip() + ',\n'
        '    ProtocolStudyAwardEvidence=ProtocolStudyAwardProjector(ReadStudy,' + json.dumps(archive_url)
        + ',' + json.dumps(batch) + ',StudyRows,BeforeProtocol),\n    ')
    text = text.replace(marker, additions.replace('\n', '\n\t\t\t\t')
        + 'Rows=Table.Buffer(Table.FromRecords(BeforeProtocol & ProtocolStudyAwardEvidence,Columns,MissingField.Error))')
    provider = '"Crossref", "OpenAlex")'
    if text.count(provider) != 1:
        raise ValueError('Qualified source-provider expression required')
    text = text.replace(provider, '"Crossref", LEFT([SourceWorkID], 9) = "protocol:", "Trial protocol", "OpenAlex")')
    admission = 'column AdmissionState = SWITCH(TRUE(), [CanonicalMatchCount] = 0,'
    if text.count(admission) != 1:
        raise ValueError('Qualified admission rule required')
    text = text.replace(admission, 'column AdmissionState = SWITCH(TRUE(), [RelationshipKind] = "study_award_reference" && [IdentityStatus] = "Source-supported", "Source-supported", [CanonicalMatchCount] = 0,')
    measures = '''\tmeasure 'Source study award links' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] = "study_award_reference", SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

\tmeasure 'Complete clinical study award chains' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] = "publication_study_award_chain", SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

'''
    text = text.replace('\tpartition SourceRelationshipEvidence = m', measures + '\tpartition SourceRelationshipEvidence = m')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result
