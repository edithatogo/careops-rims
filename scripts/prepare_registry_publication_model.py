"""Append typed registry publication references to the existing evidence model."""
import base64
import copy
import json
from urllib.parse import urlparse
from prepare_protocol_study_award_model import validate_study_archive


def prepare(document, archive_url, batch, function_source):
    u = urlparse(archive_url)
    if (u.scheme != 'https' or not (u.hostname or '').endswith('.sharepoint.com')
            or u.netloc != u.hostname or u.username is not None or u.password is not None
            or u.query or u.fragment or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained registry batch URL required')
    result = copy.deepcopy(document)
    part = next(p for p in result['definition']['parts']
                if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl')
    text = base64.b64decode(part['payload']).decode()
    validate_study_archive(text, archive_url)
    if 'RegistryPublicationProjector=' in text:
        raise ValueError('Existing registry derivation requires reconciliation')
    marker = 'Rows=Table.Buffer(Table.FromRecords(BeforeProtocol & ProtocolStudyAwardEvidence,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'ReadStudy=' not in text:
        raise ValueError('Qualified protocol evidence source contract required')
    extra = ('BeforeRegistry=List.Buffer(BeforeProtocol & ProtocolStudyAwardEvidence),\n'
             '    RegistryPublicationProjector=' + function_source.rstrip() + ',\n'
             '    RegistryPublicationEvidence=RegistryPublicationProjector(ReadStudy,'
             + json.dumps(archive_url) + ',' + json.dumps(batch) + '),\n    ')
    text = text.replace(marker, extra.replace('\n', '\n\t\t\t\t')
        + 'Rows=Table.Buffer(Table.FromRecords(BeforeRegistry & RegistryPublicationEvidence,Columns,MissingField.Error))')
    provider = '"Trial protocol", "OpenAlex")'
    if text.count(provider) != 1 or text.count('\tcolumn EvidenceKey') != 1:
        raise ValueError('Qualified provider and measure placement contract required')
    text = text.replace(provider, '"Trial protocol", LEFT([SourceWorkID], 5) = "ardc:", "ARDC grant registry", "OpenAlex")')
    measure = '''\tmeasure 'Registry source publication references' = CALCULATE(COUNTROWS(SourceRelationshipEvidence), SourceRelationshipEvidence[RelationshipKind] = "grant_related_publication") + 0
\t\tformatString: #,0

\tmeasure 'Registry related publication links' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] = "grant_related_publication", SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

'''
    text = text.replace('\tcolumn EvidenceKey', measure + '\tcolumn EvidenceKey')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result
