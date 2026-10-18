"""Validate project contracts and legacy removal; this is NOT a Power BI engine.

Exit nonzero on a failed local gate. Native M/DAX evaluation and visual rendering
remain separate acceptance gates even when every local check passes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from project_utils import ROOT, save_json

LEGACY = re.compile(r'\b(?:Employee|EmplID|Gender|Ethnicity|New Hires|Bad Hires|Separations|TermReason|Business unit|Age group|Employee type|Part-Time|Full-Time|Male|Female|SALES AND MARKETING)\b', re.I)
FORBIDDEN_NAMES = {'cache.abf','DataModel','Connections','SecurityBindings','unappliedChanges.json','mobileState.json','LinguisticSchema','semanticModelDiagramLayout.json'}
ROLES = {
    'card': {'Values'}, 'slicer': {'Values'}, 'tableEx': {'Values'},
    'lineChart': {'Category','Y','Series','Tooltips'},
    'clusteredColumnChart': {'Category','Y','Series','Tooltips'},
    'barChart': {'Category','Y','Series','Tooltips'},
    'donutChart': {'Category','Y','Series','Tooltips'}, 'textbox': set(),
}

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def walk(value: Any):
    yield value
    if isinstance(value,dict):
        for sub in value.values(): yield from walk(sub)
    elif isinstance(value,list):
        for sub in value: yield from walk(sub)

def m_lexical_errors(code: str) -> list[str]:
    """Check balanced delimiters and correct M quotes, not a grammar/type check."""
    stack=[];i=0;errors=[]; pairs={')':'(',']':'[','}':'{'}
    while i<len(code):
        if code.startswith('//',i):
            end=code.find('\n',i);i=len(code) if end<0 else end+1;continue
        if code.startswith('/*',i):
            end=code.find('*/',i+2)
            if end<0: return ['Unterminated M comment']
            i=end+2;continue
        c=code[i]
        if c=='"':
            i+=1
            while i<len(code):
                if code[i]=='"':
                    if i+1<len(code) and code[i+1]=='"': i+=2;continue
                    break
                if code[i]=='\\' and i+1<len(code) and code[i+1]=='"': errors.append('Backslash-escaped quote is not an M quote escape')
                i+=1
            if i==len(code): errors.append('Unterminated M string')
        elif c in '([{': stack.append(c)
        elif c in ')]}':
            if not stack or stack.pop()!=pairs[c]: errors.append('Unbalanced M delimiter at offset '+str(i))
        i+=1
    if stack: errors.append('Unclosed M delimiters: '+''.join(stack))
    return errors

def reference_errors(report_object: dict, model: dict) -> list[str]:
    tables={t['name']:t for t in model['tables']};errors=[]
    for obj in walk(report_object):
        if not isinstance(obj,dict): continue
        for kind,collection in [('Column','columns'),('Measure','measures')]:
            if kind not in obj: continue
            ref=obj[kind]
            if not isinstance(ref,dict) or 'Property' not in ref: continue
            table=ref.get('Expression',{}).get('SourceRef',{}).get('Entity')
            name=ref['Property']
            if table not in tables: errors.append(f'Unknown model table: {table}')
            elif name not in {x['name'] for x in tables[table].get(collection,[])}:
                errors.append(f'Unknown {kind}: {table}.{name}')
    return errors

def dax_reference_errors(code: str, model: dict) -> list[str]:
    """Check qualified model references, not DAX grammar or evaluation."""
    tables={t['name']:t for t in model['tables']};errors=[]
    for quoted,plain,column in re.findall(r"(?:'([^']+)'|([A-Za-z_][A-Za-z_0-9]*))\[([^\]]+)\]",code):
        name=quoted or plain
        if name not in tables: errors.append('Unknown DAX table '+name)
        elif column not in {c['name'] for c in tables[name]['columns']+tables[name].get('measures',[])}:
            errors.append('Unknown DAX field '+name+'.'+column)
    return errors

def validate(root: Path=ROOT) -> dict:
    checks=[]
    def check(name: str, passed: bool, detail: Any='') -> None:
        checks.append({'check':name,'result':'PASS' if passed else 'FAIL','detail':detail})
    pbip=root/'powerbi/CHHHS Research Publications.pbip'
    try:
        shortcut=load(pbip)
        report=(pbip.parent/shortcut['artifacts'][0]['report']['path']).resolve()
        pbir=load(report/'definition.pbir')
        modeldir=(report/pbir['datasetReference']['byPath']['path']).resolve()
        definition=load(modeldir/'definition.pbism')
        fullmodel=load(root/'audit/model.snapshot.json');model=fullmodel['model']
        tmdl=modeldir/'definition'
        expected_tmdl={'database.tmdl','model.tmdl','relationships.tmdl'}
        table_tmdl={f'{name}.tmdl' for name in ['Publication','PublicationFacility','Facility','Date','SearchAudit','ReportingWindow','ReleaseMetadata','GrantsRegistry','FundingCalendar','MyFundingWatchlist','FundingDeliveryLedger','FundingCalendarChanges','DoraActivityRegistry','GrantRelationships']}
        tmdl_ok=tmdl.is_dir() and expected_tmdl <= {p.name for p in tmdl.glob('*.tmdl')} and table_tmdl == {p.name for p in (tmdl/'tables').glob('*.tmdl')} and not (modeldir/'model.bim').exists()
        check('PBIP points directly to Fabric TMDL report and model',root.resolve() in modeldir.parents and definition['version']=='5.0' and tmdl_ok)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        check('Project entry points',False,str(exc));return {'status':'FAIL','checks':checks}
    tables={t['name']:t for t in model['tables']}
    expected={'Publication','PublicationFacility','Facility','Date','SearchAudit','ReportingWindow','ReleaseMetadata','GrantsRegistry','FundingCalendar','MyFundingWatchlist','FundingDeliveryLedger','FundingCalendarChanges','DoraActivityRegistry','GrantRelationships'}
    check('Canonical research and current-user grant tables only',set(tables)==expected and len(model['tables'])==len(expected),list(tables))
    tmdl_text='\n'.join(p.read_text(encoding='utf-8') for p in sorted((modeldir/'definition').rglob('*.tmdl')))
    check('Fabric TMDL contains canonical model objects',all(token in tmdl_text for token in ['table Publication','expression DoraHarvest','expression CanonicalPublications','relationship']) and 'table Employee' not in tmdl_text)
    for t in model['tables']:
        names=[x['name'] for x in t['columns']]
        measures=[x['name'] for x in t.get('measures',[])]
        check(f"Unique fields: {t['name']}",len(names+measures)==len(set(names+measures)))
        for part in t['partitions']:
            source=part['source'];errors=m_lexical_errors('\n'.join(source['expression']))
            check(f"M lexical check: partition {t['name']}",source['type']=='m' and not errors,errors)
    for t in model['tables']:
        for measure in t.get('measures',[]):
            errors=dax_reference_errors(measure['expression'],model)
            check('DAX qualified references: '+measure['name'],not errors,errors)
    relationships=model['relationships'];bad=[]
    for rel in relationships:
        for prefix in ['from','to']:
            table=rel[prefix+'Table'];column=rel[prefix+'Column']
            if table not in tables or column not in {c['name'] for c in tables[table]['columns']}: bad.append(rel['name'])
    check('Relationship endpoints and single-direction filter paths',not bad and len(relationships)==4 and all(r['crossFilteringBehavior']=='oneDirection' for r in relationships),bad)
    expressions={e['name']:'\n'.join(e['expression']) for e in model['expressions']}
    for name,code in expressions.items():
        errors=m_lexical_errors(code)
        check('M lexical check: '+name,not errors,errors)
        source=root/'powerquery'/f'{name}.m'
        if source.exists(): check('Source/model expression synchronisation: '+name,source.read_text().strip()==code.strip())
    checksums={};legacy=[];badfiles=[];invalidjson=[]
    for file in (root/'powerbi').rglob('*'):
        if not file.is_file(): continue
        if file.name in FORBIDDEN_NAMES or file.suffix.lower() in {'.pbix','.pbit','.abf'} or '.pbi' in file.parts or 'TMDLScripts' in file.parts: badfiles.append(str(file.relative_to(root)))
        content=file.read_bytes();checksums[str(file.relative_to(root))]=hashlib.sha256(content).hexdigest()
        try: text=content.decode('utf-8')
        except UnicodeDecodeError: badfiles.append(str(file));continue
        if LEGACY.search(text): legacy.append(str(file.relative_to(root)))
        if re.search(r'Sql\.Database|Date\.Year[^\n]{0,80}2014L|2014L|REPLACE_WITH_VALID_EMAIL',text): legacy.append(str(file.relative_to(root)))
        if file.suffix in {'.json','.bim','.pbir','.pbism','.pbip'}:
            try: json.loads(text)
            except ValueError: invalidjson.append(str(file))
    check('All project JSON files parse',not invalidjson,invalidjson)
    check('No old binary caches, scripts, connections or unpublished changes',not badfiles,badfiles)
    check('No legacy employment terms, SQL or hidden 2014 filter',not legacy,legacy)
    outcomes=load(root/'contracts/outcomes.contract.json')
    source_contract=load(root/'contracts/source.contract.json')
    dedup_contract=load(root/'contracts/dedup.contract.json')
    dashboard_contract=load(root/'contracts/dashboard.contract.json')
    pages=load(report/'definition/pages/pages.json')['pageOrder']
    contracted_pages=[p['name'] for p in dashboard_contract['pages']]
    check('Dashboard contract strictly enforced',pages==contracted_pages and len(pages)==dashboard_contract['page_count'],{'actual':pages,'contract':contracted_pages})
    measure_text=tables['Publication']['measures'][0]['expression']
    check('Deduplication counting contract strictly enforced',dedup_contract['counting_rule'] in measure_text)
    source_text='\n'.join(expressions.values())
    check('Source contract strictly enforced',all(src['origin'].split('/qldresearchjspui')[0] in source_text or src['origin'].split('/entrez')[0] in source_text for src in source_contract['sources']))
    forbidden_primary='|'.join(re.escape(x) for x in outcomes['forbidden_primary_outcomes'])
    report_text='\n'.join(f.read_text(encoding='utf-8') for f in report.rglob('*.json'))
    check('Forbidden primary outcomes absent from report',not re.search(forbidden_primary,report_text,re.I))
    visual_count=0;binding_count=0;geometry=[]
    for name in pages:
        folder=report/'definition/pages'/name;page=load(folder/'page.json')
        check('Page identity '+name,page['name']==name and page['width']==1920 and page['height']==1080)
        rects=[]
        for file in sorted((folder/'visuals').glob('*/visual.json')):
            obj=load(file);v=obj['visual'];n=name+'/'+obj['name'];visual_count+=1
            check('Visual schema metadata '+n,obj.get('$schema','').endswith('/visualContainer/2.0.0/schema.json') and obj['name']==file.parent.name)
            errors=reference_errors(obj,model);check('Model bindings '+n,not errors,errors)
            roles=v.get('query',{}).get('queryState',{});projections=[p for role in roles.values() for p in role['projections']];binding_count+=len(projections)
            refs=[p['queryRef'] for p in projections]
            check('Visual query contract '+n,v['visualType'] in ROLES and set(roles)<=ROLES.get(v['visualType'],set()) and len(refs)==len(set(refs)))
            rectangle=obj['position'];x,y,w,h=(rectangle[k] for k in ['x','y','width','height'])
            if x<0 or y<0 or w<=0 or h<=0 or x+w>page['width'] or y+h>page['height']: geometry.append('Off-canvas '+n)
            for old,ox,oy,ow,oh in rects:
                if min(x+w,ox+ow)>max(x,ox) and min(y+h,oy+oh)>max(y,oy): geometry.append(f'Overlap {n} and {old}')
            rects.append((n,x,y,w,h))
            forbidden={'filter','filterConfig','filters','bookmarks','syncGroup'}
            check('No inherited filter/bookmark state '+n,not any(isinstance(o,dict) and forbidden.intersection(o) for o in walk(obj)))
    check('All visuals within canvas with no overlapping containers',not geometry,geometry)
    check('Expected complete visual count',visual_count==83,visual_count)
    defs=load(root/'config/facilities.json')['rows'];keys=[d['FacilityKey'] for d in defs]
    check('28 unique facility/service search definitions',len(defs)==28 and len(keys)==len(set(keys)))
    check('No bare locality-only Yarrabah attribution',all('Yarrabah[Affiliation]' not in d['PubMedQuery'] and '"Yarrabah"[Affiliation]' not in d['PubMedQuery'] for d in defs))
    harvest=expressions['PubMedHarvest'];http=expressions['fnNCBIJson']
    check('Search and summary counts reconciled',all(token in harvest for token in ['Count > 10000','Count <> List.Count(List.Distinct(IDs))','ESummary PMID reconciliation failed','Final publication row count mismatch']))
    check('Retrieval errors are not replaced by empty data', 'otherwise #table' not in harvest and 'otherwise {}' not in harvest and all(x in http for x in ['List.Generate','each [N]<=4','Final[Status]<>200','error Error.Record']))
    check('Batched, fixed-origin, throttled NCBI queries',all(s in harvest+http for s in ['List.Split(AllIDs,100)','RelativePath','Query=QueryParameters','if n=0 then 1.1 else Number.Power(2,n)']))
    check('PubMed phrase warnings retained without hiding real errors',all(s in harvest for s in ['phrasesnotfound','HasFatalErrors','WarningParts']))
    canonical=expressions['CanonicalPublications']; dora=expressions['DoraHarvest']
    check('PubMed+DORA canonical deduplication and many-facility attribution',all(token in canonical for token in ['CanonicalKey','NormalizeDOI','NormalizePMID','conflicting-identifiers-needs-review','possible-title+year-needs-review','ambiguous-title+year','DORA-only','Canonical publication key is not unique']) and 'DISTINCTCOUNT(Publication[CanonicalKey])' in tables['Publication']['measures'][0]['expression'] and 'TREATAS(MatchedKeys' in tables['Publication']['measures'][0]['expression'])
    check('DORA feed is live and provenance fields are retained',all(token in dora for token in ['dora.health.qld.gov.au','CHHHSAffiliatedAuthors','DORAKey']) and all(name in {c['name'] for c in tables['Publication']['columns']} for name in ['DORAURL','SourceSet','DedupMethod','CHHHSAffiliatedAuthors']))
    check('Reporting date range supported by model', '#date(1900,1,1)' in '\n'.join(tables['Date']['partitions'][0]['source']['expression']) and 'outside-model-range' in harvest)
    monthly_measure=next(m for m in tables['Publication']['measures'] if m['name']=='Publications Last Complete Month')
    check('Month selection uses Brisbane calendar and exclusive end', 'SwitchZone(NowUTC,10)' in '\n'.join(tables['ReportingWindow']['partitions'][0]['source']['expression']) and 'ReportMonthEndExclusive' in monthly_measure['expression'])
    check('No invented first-seen dates or sample publications', 'FirstSeen' not in json.dumps(model) and all('example PMID' not in d['PubMedQuery'] for d in defs))
    platforms=list((root/'powerbi').glob('*.Report/.platform'))+list((root/'powerbi').glob('*.SemanticModel/.platform'))
    check('Fabric Git system files present',len(platforms)==2 and all(load(x).get('config',{}).get('logicalId') for x in platforms),[str(x) for x in platforms])
    return {'status':'PASS' if all(c['result']=='PASS' for c in checks) else 'FAIL','validation_scope':'Local contracts, field bindings, lexical checks and source scans; NOT the native Power BI engine or full Microsoft JSON Schema validation.','checks':checks,'passed':sum(c['result']=='PASS' for c in checks),'failed':sum(c['result']=='FAIL' for c in checks),'visuals':visual_count,'visual_field_projections':binding_count,'runtime_files':len(checksums),'runtime_sha256':checksums,'not_run':['Power BI Desktop open/render','Power Query M execution','Tabular/DAX engine execution','Live PubMed+DORA harvest','Power BI Service refresh/export','Power Automate deployment and delivery']}

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path);args=p.parse_args()
    result=validate(args.root)
    if args.output: save_json(args.output,result)
    print(f"{result['status']}: {result.get('passed',0)} local checks passed, {result.get('failed',0)} failed.")
    for check in result['checks']:
        if check['result']=='FAIL': print('FAIL',check['check'],check['detail'])
    raise SystemExit(0 if result['status']=='PASS' else 1)
if __name__=='__main__': main()
