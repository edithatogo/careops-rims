"""Add stricter coauthorship summaries without replacing accepted source totals.

The evidence projector admits ORCID keys only after checksum and source-identity
qualification. These measures describe publication-specific source assertions;
they do not authenticate a person or establish current employment.
"""
import base64
import copy
from collections import defaultdict

from source_relationship_evidence import orcid_status

TABLE = 'SourceRelationshipEvidence'
PATH = 'definition/tables/' + TABLE + '.tmdl'
QUALIFIED = '''CALCULATETABLE(
    SUMMARIZE(SourceRelationshipEvidence,
        SourceRelationshipEvidence[CanonicalKey],
        SourceRelationshipEvidence[FromKey],
        SourceRelationshipEvidence[ToKey],
        SourceRelationshipEvidence[SourceProvider]),
    SourceRelationshipEvidence[RelationshipKind] = "coauthorship",
    SourceRelationshipEvidence[AdmissionState] = "Source-supported",
    LEFT(SourceRelationshipEvidence[FromKey], 6) = "orcid:",
    LEFT(SourceRelationshipEvidence[ToKey], 6) = "orcid:")'''
CORROBORATED = '''FILTER(
    GROUPBY(AllProviders,
        SourceRelationshipEvidence[CanonicalKey],
        SourceRelationshipEvidence[FromKey],
        SourceRelationshipEvidence[ToKey],
        "ProviderCount", SUMX(CURRENTGROUP(), 1)),
    [ProviderCount] >= 2)'''
# Establish cross-source support independently of the current provider bar.
ALL_PROVIDERS = QUALIFIED[:-1] + ',\n    REMOVEFILTERS(SourceRelationshipEvidence[SourceProvider]))'
SELECTED_CORROBORATED = """INTERSECT(
    SUMMARIZE(Corroborated, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey]),
    SUMMARIZE(Qualified, SourceRelationshipEvidence[CanonicalKey], SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey]))"""
MEASURES = {
    'ORCID-qualified researcher pairs': 'VAR Qualified = ' + QUALIFIED + '\nRETURN COUNTROWS(SUMMARIZE(Qualified, SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey])) + 0',
    'ORCID-qualified coauthored publications': 'VAR Qualified = ' + QUALIFIED + '\nRETURN COUNTROWS(SUMMARIZE(Qualified, SourceRelationshipEvidence[CanonicalKey])) + 0',
    'Cross-source corroborated researcher pairs': 'VAR Qualified = ' + QUALIFIED + '\nVAR AllProviders = ' + ALL_PROVIDERS + '\nVAR Corroborated = ' + CORROBORATED + '\nVAR SelectedCorroborated = ' + SELECTED_CORROBORATED + '\nRETURN COUNTROWS(SUMMARIZE(SelectedCorroborated, SourceRelationshipEvidence[FromKey], SourceRelationshipEvidence[ToKey])) + 0',
    'Cross-source corroborated publications': 'VAR Qualified = ' + QUALIFIED + '\nVAR AllProviders = ' + ALL_PROVIDERS + '\nVAR Corroborated = ' + CORROBORATED + '\nVAR SelectedCorroborated = ' + SELECTED_CORROBORATED + '\nRETURN COUNTROWS(SUMMARIZE(SelectedCorroborated, SourceRelationshipEvidence[CanonicalKey])) + 0',
}


def reference_summaries(rows, selected_providers=None):
    """Independent row-grain comparison for native DAX verification."""
    assertions = defaultdict(set)
    for row in rows:
        if (row['RelationshipKind'] != 'coauthorship'
                or row['AdmissionState'] != 'Source-supported'):
            continue
        keys = (row['FromKey'], row['ToKey'])
        if not all(k.startswith('orcid:') for k in keys):
            continue
        if not row['CanonicalKey'] or not all(orcid_status(k[6:]).startswith('Valid') for k in keys):
            raise ValueError('Admitted ORCID pair violates the qualified source contract')
        if keys[0] >= keys[1]:
            raise ValueError('Ordered distinct pair required')
        assertions[(row['CanonicalKey'], *keys)].add(row['SourceProvider'])
    selected = {key for key, providers in assertions.items()
                if selected_providers is None or providers.intersection(selected_providers)}
    corroborated = [key for key in selected if len(assertions[key]) >= 2]
    return dict(zip(MEASURES, [
        len({key[1:] for key in selected}), len({key[0] for key in selected}),
        len({key[1:] for key in corroborated}), len({key[0] for key in corroborated}),
    ]))


def prepare(document):
    result = copy.deepcopy(document)
    parts = [p for p in result['definition']['parts'] if p['path'] == PATH]
    if len(parts) != 1:
        raise ValueError('Unique accepted evidence table required')
    part = parts[0]
    text = base64.b64decode(part['payload'], validate=True).decode()
    marker = '\n\tpartition SourceRelationshipEvidence = m'
    if text.count(marker) != 1 or any("measure '" + name + "'" in text for name in MEASURES):
        raise ValueError('Unmodified accepted measure baseline required')
    additions = []
    for name, expression in MEASURES.items():
        additions.append('\n\t/// Identifier-qualified source coauthorship; not authenticated identity or employment.\n'
                         "\tmeasure '" + name + "' =\n"
                         + '\n'.join('\t\t\t' + line for line in expression.splitlines())
                         + '\n\t\tformatString: #,0\n')
    text = text.replace(marker, ''.join(additions) + marker)
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result
