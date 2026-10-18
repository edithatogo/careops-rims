"""Build the scoped browser-TMDL ingestion deployment; does not deploy or refresh.
Requires the existing isolated model's FacilityDefinitions and optional pNCBIEmail.
"""
from pathlib import Path
from project_utils import ROOT


def expression(name):
    code=(ROOT/'powerquery'/f'{name}.m').read_text().rstrip()
    return '\texpression '+name+' =\n'+'\n'.join('\t\t'+line for line in code.splitlines())+'\n'


def table(name,fields,source):
    columns='\n'.join(f'\t\tcolumn {n}\n\t\t\tdataType: {t}\n\t\t\tsummarizeBy: none\n\t\t\tsourceColumn: {n}\n' for n,t in fields)
    return '\ttable '+name+'\n'+columns+'\n\t\tpartition '+name+' = m\n\t\t\tmode: import\n\t\t\tsource =\n'+'\n'.join('\t\t\t\t'+line for line in source.rstrip().splitlines())+'\n'


def source(name):
    return (ROOT/'powerquery'/f'{name}.m').read_text()


def build():
    text='createOrReplace\n'+''.join(expression(n) for n in ['fnParsePubDate','fnNCBIJson','fnPubMedXML','PubMedHarvest','PubMedFullMetadata','DoraHistoricalMetadata'])
    chunks=[('PMID','string'),('ChunkIndex','int64'),('ChunkCount','int64'),('MetadataChunk','string'),('MetadataCharacters','int64'),('Encoding','string')]
    audit=[('Check','string'),('Observed','int64'),('Passed','boolean')]
    pubs=['PMID','Title','Journal','Authors','DOI','PubMedURL','PublicationDate','PublicationDateRaw','PublicationDatePrecision','PublicationMonth','PublicationYear','OnlineDate','OnlineDateRaw','AuthorCount','PublicationTypes','PublicationClass','IsClinicalTrial','IsEvidenceSynthesis','MatchedFacilities','AttributionStatus','AttributionEvidence','PublicationNotice','FacilityMatchCount','RefreshedAtUTC','Abstract']
    pub_fields=[(n,'dateTime' if n in ['PublicationDate','OnlineDate','RefreshedAtUTC'] else 'int64' if n in ['PublicationYear','AuthorCount','FacilityMatchCount'] else 'boolean' if n in ['IsClinicalTrial','IsEvidenceSynthesis'] else 'string') for n in pubs]
    author=[('PMID','string'),('AuthorIndex','int64'),('AuthorName','string'),('AffiliationIndex','int64'),('AffiliationText','string'),('EvidenceKind','string')]
    dora=['DORAKey','DORAURL','Title','Authors','Abstract','CHHHSAffiliatedAuthors','AttributionEvidence','PublicationDate','PublicationDateRaw','PublicationDatePrecision','PublicationYear','NormalizedTitle','PMID','DOI','Journal','CoverageStatus','CollectionExpectedCount']
    dora_fields=[(n,'dateTime' if n=='PublicationDate' else 'int64' if n in ['PublicationYear','CollectionExpectedCount'] else 'string') for n in dora]
    for name,fields in [('PubMedMetadataChunks',chunks),('PubMedIngestionAudit',audit),('PubMedPublications',pub_fields),('PubMedAuthorEvidence',author),('DoraMetadataChunks',[('DORAKey' if n=='PMID' else n,t) for n,t in chunks]),('DoraIngestionAudit',audit)]:
        text+=table(name,fields,source(name))
    text+=table('DoraPublications',dora_fields,'Table.SelectColumns(DoraHistoricalMetadata,{'+','.join('"'+n+'"' for n in dora)+'})')
    path=ROOT/'config/native-ingestion.tmdl'
    path.write_text(text)
    print('Built scoped ingestion script; no tenant action performed.')


if __name__=='__main__':
    build()
