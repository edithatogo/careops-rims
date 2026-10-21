"""Append source-supported collaboration and study/award pages to native PBIR."""
from __future__ import annotations
import argparse,copy,json,shutil
from pathlib import Path
from prepare_dashboard_overview import projection,literal
from prepare_dashboard_relationship_summary import text_literal
TABLE='SourceRelationshipEvidence'
PAGES=('SourceCollaboration','SourceStudyAwards')

def category_filter(column,value):
    return {'name':'source-evidence-'+column,'field':{'Column':{'Expression':{'SourceRef':{'Entity':TABLE}},'Property':column}},'type':'Categorical','filter':{'Version':2,'From':[{'Name':'e','Entity':TABLE,'Type':0}],'Where':[{'Condition':{'In':{'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'e'}},'Property':column}}],'Values':[[{'Literal':{'Value':"'"+value+"'"}}]]}}}]}}

def prepare(source:Path,output:Path):
    orderfile=Path('definition/pages/pages.json');order=json.loads((source/orderfile).read_text())
    if 'SourceFreshness' not in order['pageOrder'] or any(p in order['pageOrder'] for p in PAGES):raise ValueError('Fresh source-freshness baseline required')
    if output.exists():raise ValueError('Exclusive output required')
    before={p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()};shutil.copytree(source,output)
    templates=source/'definition/pages/ResearchRelationships';counts={}
    for pageid,title in zip(PAGES,['Source-supported collaboration','Publication, study and award links']):
        page=output/'definition/pages'/pageid;page.mkdir();meta=json.loads((templates/'page.json').read_text());meta.update(name=pageid,displayName=title,width=1920,height=1824 if pageid==PAGES[0] else 1856)
        if 'pageBinding' in meta:meta['pageBinding']['name']=pageid+'Binding'
        (page/'page.json').write_text(json.dumps(meta,indent=2)+'\n');count=0
        def add(name,kind,rect,title,help_text,roles=None,words=None,relationship=None):
            nonlocal count
            v=json.loads((templates/'visuals'/('candidates' if kind=='cardVisual' else 'author-pattern' if kind=='barChart' else 'relationships-guidance')/'visual.json').read_text());v['name']=name;v['position']=dict(zip(('x','y','width','height'),rect),z=count*100,tabOrder=(100-count)*1000)
            a=v['visual'];a['visualType']=kind;a.pop('query',None);a.pop('objects',None);v.pop('filterConfig',None)
            c=a['visualContainerObjects'];c['general']=[{'properties':{'altText':text_literal(title)}}];c['title']=[{'properties':{'show':literal('true' if kind in {'barChart','tableEx'} else 'false'),'text':text_literal(title),'fontSize':literal('16D')}}];c['visualHeaderTooltip']=[{'properties':{'type':text_literal('Default'),'text':text_literal(help_text)}}]
            if kind=='cardVisual':a['objects']=copy.deepcopy(json.loads((templates/'visuals/candidates/visual.json').read_text())['visual']['objects'])
            if roles:a['query']={'queryState':{k:{'projections':ps} for k,ps in roles.items()}}
            if words is not None:a['objects']={'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':words,'textStyle':{'fontFamily':'Segoe UI','fontSize':'24pt' if name=='heading' else '14pt','color':'#172B4D'}}]}]}}]}
            if relationship:
                v['filterConfig']={'filters':[category_filter('RelationshipKind',relationship),category_filter('AdmissionState','Source-supported')]}
                for f in v['filterConfig']['filters']:f['name']=pageid+'-'+name+'-'+f['name']
            d=page/'visuals'/name;d.mkdir(parents=True);(d/'visual.json').write_text(json.dumps(v,indent=2)+'\n');count+=1
        def card(name,measure,x,label,table=TABLE):add(name,'cardVisual',(x,208,440,144),label,label+'; source-supported is separate from reviewed or authenticated.',{'Data':[projection(table,measure,measure=True,label=label)]})
        def table(name,x,columns,kind,title):add(name,'tableEx',(x,984 if pageid==PAGES[0] else 784,912,420),title,'Explicit source IDs and canonical publication mappings; scroll for remaining rows. No name-based identity merge.',{'Values':[projection(TABLE,col,label=label) for col,label in columns]},relationship=kind)
        add('heading','textbox',(32,8,1856,64),title,title,words=title.upper())
        if pageid==PAGES[0]:
            add('guidance','textbox',(32,88,1856,96),'Evidence meaning','Source-supported identifiers do not authenticate a person.',words='Coauthorship uses explicit author IDs and consistent source-stated ORCID aliases. Institution cooccurrence uses affiliations recorded for that publication, not current employment or organisational endorsement. Source-supported, reviewed and authenticated identities remain separate.')
            for n,m,x,l in [('coverage','Covered publications',32,'Publications with mapped source evidence'),('authors','Identified source authors',504,'Distinct qualified author IDs'),('pairs','Researcher pairs',976,'Distinct coauthor ID pairs'),('institutions','Institution pairs',1448,'Distinct institution ID pairs')]:card(n,m,x,l)
            add('provider-authors','barChart',(32,400,1856,200),'Qualified author IDs by source','Select a source to filter all source-evidence cards and tables. Sources overlap; overall cards deduplicate qualified identifiers.',{'Category':[projection(TABLE,'SourceProvider',label='Source provider')],'Y':[projection(TABLE,'Identified source authors',measure=True,label='Qualified author IDs')]})
            for n,m,x,l in [('researcher-pattern','Researcher pairs',32,'Coauthor ID pairs by source'),('institution-pattern','Institution pairs',976,'Institution ID pairs by source')]:add(n,'barChart',(x,640,912,300),l,'Sources overlap. Overall cards deduplicate identifier pairs; do not add source bars together. Select a source to filter the evidence tables.',{'Category':[projection(TABLE,'SourceProvider',label='Source provider')],'Y':[projection(TABLE,m,measure=True,label=l)]})
            table('coauthor-evidence',32,[('CanonicalKey','Publication key'),('FromLabel','Author A'),('FromKey','Author A ID'),('ToLabel','Author B'),('ToKey','Author B ID'),('SourceURL','Source evidence')],'coauthorship','Source-supported coauthor pairs')
            table('affiliation-evidence',976,[('CanonicalKey','Publication key'),('FromKey','Author ID'),('ToLabel','Institution'),('ToKey','Institution ID'),('ROR','Source ROR')],'publication_affiliation','Publication-specific institution assertions')
            for n,m,x,l in [('ambiguous','Ambiguous source works',32,'Source works with ambiguous publication DOI'),('unadmitted','Unresolved source author mentions',976,'Unadmitted source author mentions')]:
                add(n,'cardVisual',(x,1440,912,128),l,'Unadmitted mentions include missing/conflicting author IDs and unmapped/ambiguous publications; these are not people counts.',{'Data':[projection(TABLE,m,measure=True,label=l)]})
            add('limits','textbox',(32,1616,1856,160),'Coverage and uncertainty','Existing unresolved author-label evidence remains in its original page.',words='Coverage is limited to retained source records with a unique canonical mapping. Ambiguous DOI mappings and unresolved author IDs remain retained and excluded from admitted pair counts. Names are display labels; IDs distinguish people. ORCID syntax is checked separately and does not imply authentication. ROR text is retained; institution pairs use provider IDs and explicit Ringgold IDs, without name-based organisation merging. Existing researcher evidence and review history remain preserved.')
        else:
            add('guidance','textbox',(32,88,1856,96),'Relationship states','Provider assertions do not imply confirmed funding or institutional participation.',words='Study links come from explicit ClinicalTrials.gov RESULT/DERIVED references and PubMed trial registry identifiers. Award IDs are explicit OpenAlex assertions; PubMed GrantList references keep their source-scoped agency labels. Neither is automatically a reviewed funding relationship. Background citations are excluded from study-output links.')
            for n,m,x,l,t in [('source-awards','Publication award assertions',32,'Source-supported publication–award assertions',TABLE),('grant-refs','Publication grant references',504,'Source-scoped PubMed grant references',TABLE),('study-links','Publication study links',976,'Distinct publication–trial references',TABLE),('confirmed-links','Confirmed reviewed links',1448,'Existing confirmed reviewed links','Funding Relationship Context')]:card(n,m,x,l,t)
            add('chain-status','textbox',(32,400,1856,120),'Complete chain coverage','No full publication–project–award chain has yet been established.',words='Complete publication–project–award chains: not established. A ClinicalTrials.gov study ID is not a DORA project ID. An internal study ID or shared researcher/organisation does not establish award funding. Source-stated award identifiers remain distinct from existing register awards until a qualified crosswalk exists.')
            add('state-explanation','textbox',(32,560,912,144),'Provenance and review','Human review decisions remain authoritative in their existing register.',words='The source-supported layer retains source work/study ID, publication DOI/PMID, source URL, observation UTC, raw payload hash and reference type. Unmapped and ambiguous publication identities remain retained. Existing candidate/confirmed-reviewed funding views keep their original admission rules and review records.')
            add('candidate-links','cardVisual',(976,560,912,144),'Existing candidate funding links','Existing review register candidates remain separate from provider assertions.',{'Data':[projection('Funding Relationship Context','Candidate links',measure=True,label='Existing candidate funding links')]})
            table('source-award-evidence',32,[('CanonicalKey','Publication key'),('ToLabel','Source funder and award number'),('ToKey','Source award ID'),('SourceURL','Evidence source')],'publication_award','Explicit publication–award assertions')
            table('source-study-evidence',976,[('CanonicalKey','Publication key'),('ToKey','Study source ID'),('ReferenceType','Provider reference type'),('SourceURL','Evidence source')],'publication_study_reference','Explicit publication–study references')
            add('source-grant-references','tableEx',(32,1264,1856,320),'PubMed source-scoped grant references','Explicit GrantList assertions, not a global funder/award crosswalk or reviewed funding attribution.',{'Values':[projection(TABLE,c,label=l) for c,l in [('CanonicalKey','Publication key'),('ToLabel','Source agency and grant number'),('SourceURL','Source evidence'),('SourceVersion','Retained source generation')]]},relationship='publication_grant_reference')
            add('limits','textbox',(32,1640,1856,168),'Scope and recovery','No monetary total or source review decision is inferred.',words='These are evidence summaries, not funding attribution approval, current staff membership or broader collaboration certification. Missing links remain unknown. Some trial IDs are references only, not acquired local study records. Source grant references are not added to provider award-ID counts. No combined research population or monetary total is calculated; existing model totals, source records, human edits, access and schedules are preserved.')
        order['pageOrder'].append(pageid);counts[pageid]=count
    (output/orderfile).write_text(json.dumps(order,indent=2)+'\n');assert all((output/p).read_bytes()==b for p,b in before.items() if p!=orderfile)
    return counts

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(prepare(a.source,a.output)))
