"""Extend the existing evidence table using a retained Crossref/ARDC packet."""
import argparse
import base64
import copy
import json
from pathlib import Path
from urllib.parse import urlparse


def prepare(document, archive_url, batch, function_source):
    u = urlparse(archive_url)
    if (u.scheme != 'https' or not (u.hostname or '').endswith('.sharepoint.com')
            or u.username or u.password or u.query or u.fragment
            or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained crosswalk batch URL required')
    result = copy.deepcopy(document)
    part = next(p for p in result['definition']['parts']
                if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl')
    text = base64.b64decode(part['payload']).decode()
    if 'CrossrefAwardProjector=' in text:
        raise ValueError('Existing Crossref award derivation must be reconciled')
    marker = 'Rows=Table.Buffer(Table.FromRecords(Output & StudyEvidence & PubMedEvidence & AwardAliases,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'AwardAliasProjector=' not in text or 'StudyRoot=' not in text:
        raise ValueError('Qualified initial alias and fixed SharePoint root required')
    indent = '\t\t\t\t'
    addition = '''CrossrefArchiveBase=__URL__,
    CrossrefParts=if Text.StartsWith(CrossrefArchiveBase,StudySite&"/Documents/") then Text.Split(Text.AfterDelimiter(CrossrefArchiveBase,StudySite&"/"),"/") else error "Crossref archive site drift",
    CrossrefRawFiles=Table.Buffer(List.Accumulate(CrossrefParts,StudyRoot,(T,N)=>let Matches=Table.SelectRows(T,each [Name]=N) in if Table.RowCount(Matches)=1 and Value.Is(Matches{0}[Content],type table) then Matches{0}[Content] else error "Crossref archive folder missing or duplicated")),
    CrossrefReadFile=(URL as text) as binary => let Name=Text.AfterDelimiter(URL,"/",{0,RelativePosition.FromEnd}),Matches=if URL=CrossrefArchiveBase&"/"&Name then Table.SelectRows(CrossrefRawFiles,each [Name]=Name) else error "Crossref file scope drift" in if Table.RowCount(Matches)=1 and Value.Is(Matches{0}[Content],type binary) then Binary.Buffer(Matches{0}[Content]) else error "Crossref archive file missing or duplicated",
    CrossrefAwardProjector=__FUNCTION__,
    CrossrefAwardEvidence=CrossrefAwardProjector(CrossrefReadFile,CrossrefArchiveBase,__BATCH__),
    '''.replace('__URL__', json.dumps(archive_url)).replace('__BATCH__', json.dumps(batch)).replace('__FUNCTION__', function_source.rstrip())
    text = text.replace(marker, addition.replace('\n', '\n' + indent)
                        + marker.replace('AwardAliases,', 'AwardAliases & CrossrefAwardEvidence,'))
    old = '"ClinicalTrials.gov", "OpenAlex")'
    if text.count(old) != 1:
        raise ValueError('Qualified SourceProvider expression required')
    text = text.replace(old, '"ClinicalTrials.gov", LEFT([SourceWorkID], 9) = "crossref:", "Crossref", "OpenAlex")')
    measures = '''\tmeasure 'Crossref mapped award links' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] = "publication_award_crosswalk", SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

\tmeasure 'Mapped publication award links' = CALCULATE(COUNTROWS(SUMMARIZE(SourceRelationshipEvidence, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[ToKey])), SourceRelationshipEvidence[RelationshipKind] IN {"award_identifier_alias", "publication_award_crosswalk"}, SourceRelationshipEvidence[AdmissionState] = "Source-supported") + 0
\t\tformatString: #,0

'''
    text = text.replace('\tpartition SourceRelationshipEvidence = m', measures + '\tpartition SourceRelationshipEvidence = m')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--archive-url', required=True); p.add_argument('--batch', required=True)
    a = p.parse_args(); d = json.loads(a.source.read_text()); d = d.get('text', d)
    a.output.write_text(json.dumps(prepare(d, a.archive_url, a.batch,
        Path('config/crossref-award-crosswalks.m').read_text()), indent=2))
