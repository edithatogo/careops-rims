"""Add a derived evidence table to a fresh native semantic-model definition."""
from __future__ import annotations
import argparse,base64,copy,json,re,uuid
from pathlib import Path

TABLE='SourceRelationshipEvidence'
COLUMNS=['EvidenceKey','RelationshipKind','SourceWorkID','PublicationDOI','PublicationPMID','ReferenceType','FromKey','ToKey','FromLabel','ToLabel','ORCID','ORCIDStatus','ROR','IdentityStatus','SourceURL','ObservedUTC','RawSHA256','SourceVersion','ReviewState','AuthenticationState']

def table_definition(m_source):
    name=TABLE
    lines=[f'/// Source-stated evidence only. One row per work, relationship kind and ordered identifier pair. No human review or authenticated identity is inferred.',f'table {name}','']
    for c in COLUMNS:
        lines += [f'\tcolumn {c}','\t\tdataType: string','\t\tsummarizeBy: none',f'\t\tsourceColumn: {c}','']
    match='FILTER(ALLNOBLANKROW(Publication[CanonicalKey], Publication[RelationshipDOIKey], Publication[PMID]), IF(D <> "", Publication[RelationshipDOIKey] = D, Publication[PMID] = P && P <> ""))'
    lines += ['\tcolumn SourceProvider = SWITCH(TRUE(), LEFT([SourceWorkID], 7) = \"pubmed:\", \"PubMed\", LEFT([SourceWorkID], 19) = \"clinicaltrials.gov:\", \"ClinicalTrials.gov\", \"OpenAlex\")','\t\tdataType: string','\t\tsummarizeBy: none','']
    lines += [f'\tcolumn CanonicalMatchCount = VAR D = [PublicationDOI] VAR P = [PublicationPMID] RETURN COUNTROWS({match})','\t\tdataType: int64','\t\tsummarizeBy: none','',f'\tcolumn CanonicalKey = VAR D = [PublicationDOI] VAR P = [PublicationPMID] VAR Matches = {match} RETURN IF(COUNTROWS(Matches) = 1, MAXX(Matches, Publication[CanonicalKey]), BLANK())','\t\tdataType: string','\t\tsummarizeBy: none','', '\tcolumn AdmissionState = SWITCH(TRUE(), [CanonicalMatchCount] = 0, "Unmapped publication", [CanonicalMatchCount] > 1, "Ambiguous DOI", [IdentityStatus] <> "Source-supported", [IdentityStatus], "Source-supported")','\t\tdataType: string','\t\tsummarizeBy: none','']
    for label,kind in [('Covered publications','publication'),('Coauthored publications','coauthorship'),('Institution cooccurrence publications','institution_cooccurrence')]:
        lines += [f'\tmeasure \'{label}\' = CALCULATE(DISTINCTCOUNT({name}[CanonicalKey]), {name}[RelationshipKind] = "{kind}", {name}[AdmissionState] = "Source-supported") + 0','\t\tformatString: #,0','']
    lines += [f'\tmeasure \'Identified source authors\' = CALCULATE(DISTINCTCOUNT({name}[ToKey]), {name}[RelationshipKind] = "authorship", {name}[AdmissionState] = "Source-supported") + 0','\t\tformatString: #,0','']
    for label,kind in [('Researcher pairs','coauthorship'),('Institution pairs','institution_cooccurrence'),('Publication award assertions','publication_award'),('Publication study links','publication_study_reference'),('Publication grant references','publication_grant_reference')]:
        cols=f'{name}[CanonicalKey], {name}[ToKey]' if kind in {'publication_award','publication_study_reference','publication_grant_reference'} else f'{name}[FromKey], {name}[ToKey]'
        lines += [f'\tmeasure \'{label}\' = CALCULATE(COUNTROWS(SUMMARIZE({name}, {cols})), {name}[RelationshipKind] = "{kind}", {name}[AdmissionState] = "Source-supported") + 0','\t\tformatString: #,0','']
    lines += [f'\tmeasure \'Ambiguous source works\' = CALCULATE(COUNTROWS({name}), {name}[RelationshipKind] = "publication", {name}[AdmissionState] = "Ambiguous DOI") + 0','\t\tformatString: #,0','',f'\tmeasure \'Unresolved source author mentions\' = CALCULATE(COUNTROWS({name}), {name}[RelationshipKind] = "authorship", {name}[AdmissionState] <> "Source-supported") + 0','\t\tformatString: #,0','', f'\tpartition {name} = m','\t\tmode: import','\t\tsource =']
    lines += ['\t\t\t\t'+line for line in m_source.splitlines()]
    return '\n'.join(lines)+'\n'

def prepare(document,m_source):
    result=copy.deepcopy(document);parts=result['definition']['parts'];paths={p['path']:p for p in parts};newpath=f'definition/tables/{TABLE}.tmdl'
    if newpath in paths:raise ValueError('Evidence table already exists; reconcile current version')
    for path,addition in [('definition/model.tmdl',f'\nref table {TABLE}\n'),('definition/relationships.tmdl',f'\nrelationship {uuid.uuid5(uuid.NAMESPACE_URL,"rims/source-relationships/publication")}\n\tfromColumn: {TABLE}.CanonicalKey\n\ttoColumn: Publication.CanonicalKey\n')]:
        raw=base64.b64decode(paths[path]['payload']).decode();paths[path]['payload']=base64.b64encode((raw+addition).encode()).decode()
    study=base64.b64decode(paths['definition/tables/Study register.tmdl']['payload']).decode().split('\n\t\tsource =',1)[1].strip()
    site=re.search(r'SharePoint\.Tables\("([^"]+)"',study)
    if not site:raise ValueError('Qualified fixed study source site required')
    m_source=m_source.replace('__PUBMED_RELATIONSHIP_FUNCTION__',Path('config/pubmed-relationship-evidence.m').read_text()).replace('__STUDY_REGISTER_SOURCE__',study).replace('__STUDY_SITE_URL__',json.dumps(site.group(1)))
    pubpath='definition/tables/Publication.tmdl'
    publication=base64.b64decode(paths[pubpath]['payload']).decode()
    if 'column RelationshipDOIKey' in publication:raise ValueError('Existing normalisation column requires reconciliation')
    prefixes=['https://doi.org/','http://doi.org/','http://dx.doi.org/','https://dx.doi.org/']
    clauses=', '.join(f'LEFT(Raw, {len(v)}) = "{v}", MID(Raw, {len(v)+1}, LEN(Raw))' for v in prefixes)
    column='\n\tcolumn RelationshipDOIKey = VAR Raw = LOWER(TRIM(Publication[DOI])) RETURN SWITCH(TRUE(), '+clauses+', Raw)\n\t\tdataType: string\n\t\tisHidden\n\t\tsummarizeBy: none\n'
    publication=publication.replace('\n\tpartition Publication = m',column+'\n\tpartition Publication = m')
    paths[pubpath]['payload']=base64.b64encode(publication.encode()).decode()
    parts.append({'path':newpath,'payload':base64.b64encode(table_definition(m_source).encode()).decode(),'payloadType':'InlineBase64'})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();x=json.loads(a.source.read_text());x=x.get('text',x);out=prepare(x,Path('config/source-relationship-evidence.m').read_text());a.output.write_text(json.dumps(out,indent=2));print('Prepared',len(out['definition']['parts']),'parts')
