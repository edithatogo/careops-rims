"""Append verified award alias derivation to the existing evidence partition."""
import argparse
import base64
import copy
import json
from pathlib import Path
from urllib.parse import urlparse


def prepare(document, archive_url, batch, function_source):
    parsed = urlparse(archive_url)
    if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.sharepoint.com')
            or parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None
            or archive_url.split('/')[-1] != 'award-crosswalk-' + batch):
        raise ValueError('Exact retained crosswalk batch URL required')
    result = copy.deepcopy(document)
    part = next(p for p in result['definition']['parts']
                if p['path'] == 'definition/tables/SourceRelationshipEvidence.tmdl')
    text = base64.b64decode(part['payload']).decode()
    if 'AwardAliasProjector=' in text:
        raise ValueError('Existing award alias derivation must be reconciled')
    marker = 'Rows=Table.Buffer(Table.FromRecords(Output & StudyEvidence & PubMedEvidence,Columns,MissingField.Error))'
    if text.count(marker) != 1 or 'ReadStudy=' not in text or 'UniqueWorks=' not in text:
        raise ValueError('Qualified existing source partition contract required')
    indent = '\t\t\t\t'
    additions = ('AwardAliasProjector=' + function_source.rstrip() + ',\n'
                 '    AwardAliases=AwardAliasProjector(ReadStudy,' + json.dumps(archive_url)
                 + ',' + json.dumps(batch) + ',UniqueWorks,Output),\n    ')
    text = text.replace(marker, additions.replace('\n', '\n' + indent)
                        + marker.replace('PubMedEvidence,', 'PubMedEvidence & AwardAliases,'))
    measure = ('\tmeasure \'Qualified award aliases\' = CALCULATE(COUNTROWS('
               'SourceRelationshipEvidence), SourceRelationshipEvidence[RelationshipKind] = '
               '"award_identifier_alias", SourceRelationshipEvidence[AdmissionState] = '
               '"Source-supported") + 0\n\t\tformatString: #,0\n\n')
    text = text.replace('\tpartition SourceRelationshipEvidence = m',
                        measure + '\tpartition SourceRelationshipEvidence = m')
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--archive-url', required=True)
    p.add_argument('--batch', required=True)
    a = p.parse_args()
    d = json.loads(a.source.read_text())
    d = d.get('text', d)
    a.output.write_text(json.dumps(prepare(d, a.archive_url, a.batch,
        Path('config/award-identifier-crosswalks.m').read_text()), indent=2))
