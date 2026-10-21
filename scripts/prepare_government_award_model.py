"""Append exact historical government-record references without changing old facts."""
import base64
import copy
import json
from urllib.parse import urlparse

from scripts.prepare_protocol_study_award_model import validate_study_archive


def prepare(document, archive_url, batch, function_source):
    u = urlparse(archive_url)
    if (u.scheme != 'https' or not (u.hostname or '').endswith('.sharepoint.com')
            or u.netloc != u.hostname or u.query or u.fragment
            or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained government batch URL required')
    result = copy.deepcopy(document)
    parts = [p for p in result['definition']['parts']
             if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl']
    if len(parts) != 1:
        raise ValueError('Unique existing evidence table required')
    part = parts[0]
    text = base64.b64decode(part['payload']).decode()
    validate_study_archive(text, archive_url)
    if 'GovernmentAwardProjector=' in text:
        raise ValueError('Existing government derivation requires reconciliation')
    marker = 'Rows=Table.Buffer(Table.FromRecords(BeforeRegistry & RegistryPublicationEvidence,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'ReadStudy=' not in text or text.count('\tcolumn EvidenceKey') != 1:
        raise ValueError('Accepted registry source contract required')
    extra = ('BeforeGovernment=List.Buffer(BeforeRegistry & RegistryPublicationEvidence),\n'
             '    GovernmentAwardProjector=' + function_source.rstrip() + ',\n'
             '    GovernmentAwardEvidence=GovernmentAwardProjector(ReadStudy,'
             + json.dumps(archive_url) + ',' + json.dumps(batch) + '),\n    ')
    text = text.replace(marker, extra.replace('\n', '\n\t\t\t\t')
        + 'Rows=Table.Buffer(Table.FromRecords(BeforeGovernment & GovernmentAwardEvidence,Columns,MissingField.Error))')
    measures = '''\t/// Explicit source references to historical government application records; no current-status or reviewed-funding claim.
\tmeasure 'Government source award references' = CALCULATE(COUNTROWS(SourceRelationshipEvidence), SourceRelationshipEvidence[RelationshipKind] = "publication_government_award_reference") + 0
\t\tformatString: #,0

\tmeasure 'Government record publication links' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] = "publication_government_award_reference", SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

'''
    text = text.replace('\tcolumn EvidenceKey', measures + '\tcolumn EvidenceKey')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result
