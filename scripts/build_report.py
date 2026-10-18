"""Create documented PBIR report files; never reuse legacy visual state."""
from __future__ import annotations
import argparse
import json
import shutil
import zipfile
from pathlib import Path
from project_utils import ROOT, save_json

REPORT = ROOT/'powerbi/CHHHS Research Publications.Report'
BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'
MANIFEST: list[dict] = []

def literal(value: str) -> dict:
    return {'expr':{'Literal':{'Value':"'"+value.replace("'","''")+"'"}}}

def field(table: str, name: str, kind: str='Column') -> dict:
    return {kind:{'Expression':{'SourceRef':{'Entity':table}},'Property':name}}

def col(table: str, name: str, label: str|None=None) -> dict:
    return {'field':field(table,name),'queryRef':f'{table}.{name}','nativeQueryRef':name,'displayName':label or name}

def met(name: str, label: str|None=None) -> dict:
    return {'field':field('Publication',name,'Measure'),'queryRef':'Publication.'+name,'nativeQueryRef':name,'displayName':label or name}

def release_col(name: str, label: str|None=None) -> dict:
    return {'field':field('ReleaseMetadata',name),'queryRef':f'ReleaseMetadata.{name}','nativeQueryRef':name,'displayName':label or name}

def grant_col(name: str, label: str|None=None) -> dict:
    return {'field':field('GrantsRegistry',name),'queryRef':f'GrantsRegistry.{name}','nativeQueryRef':name,'displayName':label or name}

def grant_met(name: str, label: str|None=None) -> dict:
    return {'field':field('GrantsRegistry',name,'Measure'),'queryRef':f'GrantsRegistry.{name}','nativeQueryRef':name,'displayName':label or name}

def list_col(table: str, name: str, label: str|None=None) -> dict:
    """Reference an additive SharePoint-backed grant experience table."""
    return {'field':field(table,name),'queryRef':f'{table}.{name}','nativeQueryRef':name,'displayName':label or name}

def visual(page: str, name: str, kind: str, title: str, xywh: tuple, roles: dict|None=None, text: str|None=None, sort_field: dict|None=None, descending: bool=False) -> None:
    x,y,w,h=xywh
    order=sum(m['page']==page for m in MANIFEST)
    config={'visualType':kind,'drillFilterOtherVisuals':True}
    if roles:
        config['query']={'queryState':{role:{'projections':projections} for role,projections in roles.items()}}
        if sort_field:
            config['query']['sortDefinition']={'sort':[{'field':sort_field,'direction':'Descending' if descending else 'Ascending'}],'isDefaultSort':False}
    if text is not None:
        config['objects']={'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':text,'textStyle':{'fontFamily':'Segoe UI','fontSize':'27px' if name=='heading' else '16px'}}]}]}}]}
    config['visualContainerObjects'] = {
        'title': [{'properties': {
            'show': {'expr': {'Literal': {'Value': 'false' if kind == 'textbox' else 'true'}}},
            'text': literal(title),
            'fontSize': {'expr': {'Literal': {'Value': '15D'}}},
        }}]
    }
    if kind in ('lineChart','clusteredColumnChart','barChart'):
        config.setdefault('objects',{})['valueAxis']=[{'properties':{'logAxisScale':{'expr':{'Literal':{'Value':'false'}}}}}]
    if kind=='tableEx':
        config.setdefault('objects',{})['columnHeaders']=[{'properties':{'wordWrap':{'expr':{'Literal':{'Value':'true'}}}}}]
        config['objects']['values']=[{'properties':{'wordWrap':{'expr':{'Literal':{'Value':'true'}}}}}]
    if kind=='card':
        is_footer = 'refresh' in name or 'footer' in name
        font_size = '16D' if is_footer else '30D'
        config.setdefault('objects',{})['labels']=[{'properties':{'fontSize':{'expr':{'Literal':{'Value':font_size}}}}}]
        config['objects']['categoryLabels']=[{'properties':{'show':{'expr':{'Literal':{'Value':'false'}}}}}]
    if kind=='slicer':
        config.setdefault('objects',{})['data']=[{'properties':{'mode':{'expr':{'Literal':{'Value':"'Dropdown'"}}}}}]
        config['objects']['header']=[{'properties':{'show':{'expr':{'Literal':{'Value':'false'}}}}}]
    obj={'$schema':BASE+'visualContainer/2.0.0/schema.json','name':name,'position':{'x':x,'y':y,'z':order,'width':w,'height':h,'tabOrder':order},'visual':config}
    save_json(REPORT/f'definition/pages/{page}/visuals/{name}/visual.json',obj)
    MANIFEST.append({'page':page,'visual':name,'type':kind,'title':title or text,'position':xywh})

def heading(page: str, title: str, caption: str) -> None:
    visual(page,'heading','textbox','',(32,16,1856,48),text='CHHHS RESEARCH PUBLICATIONS  |  '+title)
    visual(page,'caption','textbox','',(32,64,1856,40),text=caption)

def footer(page: str, text: str) -> None:
    visual(page,'footer','textbox','',(32,1016,1856,32),text=text)

def card(page: str, name: str, title: str, measure: str, index: int) -> None:
    xs = [32, 504, 976, 1448]
    visual(page,name,'card',title,(xs[index],112,440,96),{'Values':[met(measure)]})

def build(source_pbix: Path | None = None) -> None:
    MANIFEST.clear()
    if (REPORT/'definition').exists(): shutil.rmtree(REPORT/'definition')
    pages=[
        ('PublicationRegister','CHHHS Publications'),
        ('MonthlyPublications','Monthly Publications'),
        ('SourceReconciliation','Source Reconciliation'),
        ('ClinicalAnalytics','Clinical Analytics'),
        ('FundingOpportunities','Funding Opportunities'),
        ('FundingCalendar','Funding Calendar'),
        ('MyFundingWatchlist','My Funding Watchlist')
    ]
    for page,label in pages:
        save_json(REPORT/f'definition/pages/{page}/page.json',{'$schema':BASE+'page/2.0.0/schema.json','name':page,'displayName':label,'displayOption':'FitToPage','height':1080,'width':1920})
    save_json(REPORT/'definition/pages/pages.json',{'$schema':BASE+'pagesMetadata/1.0.0/schema.json','pageOrder':[p for p,_ in pages],'activePageName':'PublicationRegister'})
    save_json(REPORT/'definition/version.json',{'$schema':BASE+'versionMetadata/1.0.0/schema.json','version':'4.0.0'})
    theme_name='Fluent2-CY26SU08'
    theme_file = REPORT/'StaticResources/SharedResources/BaseThemes'/f'{theme_name}.json'
    if source_pbix is not None:
        with zipfile.ZipFile(source_pbix) as archive:
            theme = archive.read('Report/StaticResources/SharedResources/BaseThemes/'+theme_name+'.json')
        theme_file.parent.mkdir(parents=True, exist_ok=True); theme_file.write_bytes(theme)
    elif not theme_file.exists():
        raise FileNotFoundError('Bundled theme missing. Supply the original PBIX to restore the theme.')
    save_json(REPORT/'definition/report.json',{
        '$schema':BASE+'report/3.0.0/schema.json',
        'themeCollection':{'baseTheme':{'name':theme_name,'reportVersionAtImport':{'visual':'2.0.0','report':'3.0.0','page':'2.0.0'},'type':'SharedResources'}},
        'resourcePackages':[{'name':'SharedResources','type':'SharedResources','items':[{'name':theme_name,'path':f'BaseThemes/{theme_name}.json','type':'BaseTheme'}]}],
        'settings':{'useEnhancedTooltips':True,'exportDataMode':'AllowSummarized','isPersistentUserStateDisabled':True}
    })
    save_json(REPORT/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../CHHHS Research Publications.SemanticModel'}}})
    save_json(ROOT/'powerbi/CHHHS Research Publications.pbip',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json','version':'1.0','artifacts':[{'report':{'path':'CHHHS Research Publications.Report'}}],'settings':{'enableAutoRecovery':True}})

    # Page 1: CHHHS Publications (PublicationRegister)
    p='PublicationRegister'
    heading(p,'CHHHS Publications','PubMed and DORA publication records. Counts remain provisional while identity and institutional scope reviews are open.')
    for i,(n,t,m) in enumerate([
        ('all-papers','Canonical publications','Publications'),
        ('pubmed','Found in PubMed','PubMed Publications'),
        ('dora','Found in DORA','DORA Publications'),
        ('overlap','Found in both sources','Cross-source Matches')
    ]): card(p,n,t,m,i)
    visual(p,'facility-filter','slicer','Facility / service',(32,224,520,72),{'Values':[col('Facility','FacilityName','Facility / service')]})
    visual(p,'year-filter','slicer','Publication year',(568,224,280,72),{'Values':[col('Publication','PublicationYear','Year')]})
    visual(p,'source-filter','slicer','Source provenance',(864,224,440,72),{'Values':[col('Publication','SourceSet','Source')]})
    visual(p,'review-filter','slicer','Attribution status',(1320,224,568,72),{'Values':[col('Publication','AttributionStatus','Status')]})
    
    # Executive Analytics Visuals (Replacing raw publication title table)
    visual(p,'annual-trajectory','lineChart','Annual publication trajectory (2014–2026)',(32,312,912,312),{
        'Category':[col('Publication','PublicationYear','Year')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','PublicationYear'),descending=False)
    
    visual(p,'facility-breakdown','barChart','Publications by CHHHS facility / service',(960,312,928,312),{
        'Category':[col('Facility','FacilityName','Facility')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','Publications','Measure'),descending=True)
    
    visual(p,'attribution-breakdown','barChart','Institutional attribution status breakdown',(32,640,912,304),{
        'Category':[col('Publication','AttributionStatus','Attribution')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','Publications','Measure'),descending=True)
    
    visual(p,'provenance-breakdown','donutChart','Source provenance distribution',(960,640,928,304),{
        'Category':[col('Publication','SourceSet','Source')],
        'Y':[met('Publications','Publications')]
    })
    
    visual(p,'release-version','card','Software version',(32,960,912,80),{'Values':[release_col('SoftwareVersion')]})
    visual(p,'release-batch','card','Accepted batch identity',(976,960,912,80),{'Values':[release_col('AcceptedBatchID')]})

    # Page 2: Monthly Publications (MonthlyPublications)
    p='MonthlyPublications'
    heading(p,'Monthly Publications','Select one publication month; clear the selection for the previous complete Brisbane month. Publication dates determine inclusion.')
    for i,(n,t,m) in enumerate([
        ('month','Reporting month','Reporting Month'),
        ('monthly-papers','Publications in reporting month','Selected Month Publications'),
        ('undated','Records without usable month','Publications Without Usable Month')
    ]):
        visual(p,n,'card',t,(32+472*(3 if n=='undated' else i),112,440,96),{'Values':[met(m)]})
    visual(p,'month-yoy','slicer','Publication month (choose one; clear for default)',(976,112,440,96),{'Values':[col('Date','YearMonth','Month')]})
    visual(p,'publication-trend','barChart','Facility / service matches in reporting month (overlapping)',(32,224,1200,328),{'Category':[col('Facility','FacilityName','Facility')],'Y':[met('Selected Month Publications','Publications')]},sort_field=field('Publication','Selected Month Publications','Measure'),descending=True)
    visual(p,'monthly-source','donutChart','Source provenance',(1256,224,632,328),{'Category':[col('Publication','SourceSet','Source')],'Y':[met('Selected Month Publications','Publications')]})
    
    # Executive Monthly Analytics (Replacing raw monthly title table)
    visual(p,'monthly-history-trend','lineChart','Monthly publication trend (Last 24 complete months)',(32,568,1200,432),{
        'Category':[col('Date','YearMonth','Month')],
        'Y':[met('Selected Month Publications','Publications')]
    })
    visual(p,'monthly-attribution','barChart','Reporting month attribution status',(1256,568,632,432),{
        'Category':[col('Publication','AttributionStatus','Attribution')],
        'Y':[met('Selected Month Publications','Publications')]
    },sort_field=field('Publication','Selected Month Publications','Measure'),descending=True)
    
    footer(p,'Indexing delays can revise prior months. Partial and absent dates are not silently assigned to January or the refresh date.')

    # Page 3: Source Reconciliation (SourceReconciliation)
    p='SourceReconciliation'
    heading(p,'Source Reconciliation','Audit PubMed and DORA coverage, deduplication and institutional-attribution evidence before using counts externally.')
    for i,(n,t,m) in enumerate([
        ('pubmed','PubMed publications','PubMed Publications'),
        ('dora','DORA publications','DORA Publications'),
        ('dora-only','DORA-only publications','DORA-only Publications'),
        ('needs-review','Needs reconciliation review','Reconciliation Needs Review')
    ]): card(p,n,t,m,i)
    visual(p,'source-overlap','donutChart','Canonical publications by source provenance',(32,224,736,312),{'Category':[col('Publication','SourceSet','Source')],'Y':[met('Publications')]})
    visual(p,'dedup-method','barChart','Reconciliation method',(792,224,528,312),{'Category':[col('Publication','DedupMethod','Method')],'Y':[met('Publications')]},sort_field=field('Publication','Publications','Measure'),descending=True)
    visual(p,'facility-contributions','tableEx','PubMed search coverage and warnings',(1344,224,544,312),{'Values':[col('SearchAudit','FacilityKey','Search key'),col('SearchAudit','SearchCount','Source matches'),col('SearchAudit','Warnings','Warnings'),col('SearchAudit','QueryVersion','Query version')]})
    visual(p,'reconciliation-register','tableEx','Reconciliation and attribution register',(32,552,1856,352),{'Values':[
        col('Publication','Title','Publication'),col('Publication','AttributionEvidence','Attribution evidence'),col('Publication','SourceSet','Source'),
        col('Publication','DedupMethod','Deduplication'),col('Publication','AttributionStatus','Attribution status'),
        col('Publication','CHHHSAffiliatedAuthors','DORA CHHHS-affiliated author(s)'),col('Publication','MatchedFacilities','PubMed facility/service matches'),
        col('Publication','PMID','PMID'),col('Publication','DORAURL','DORA')
    ]})
    visual(p,'refresh-time','card','Last model refresh (UTC)',(32,912,584,96),{'Values':[met('Refresh Timestamp UTC')]})
    visual(p,'warnings','card','PubMed queries with warnings',(640,912,584,96),{'Values':[met('Query Warnings')]})
    visual(p,'searches','card','Configured PubMed affiliation searches',(1248,912,640,96),{'Values':[met('Configured Facility Searches')]})
    footer(p,'Identifier conflicts and title/year candidates remain separate for review. DORA coverage is an observed collection snapshot; durable history and native count acceptance remain pending.')

    # Page 4: Clinical Analytics & Research Intelligence (ClinicalAnalytics)
    p='ClinicalAnalytics'
    heading(p,'Clinical Analytics','Clinical directorate specialty mapping, ANZSRC Field of Research (FoR) classification, Open Access compliance, and clinical trial activity.')
    for i,(n,t,m) in enumerate([
        ('oa-rate','Open access compliance rate','Open Access Rate'),
        ('oa-papers','Open access publications','Open Access Publications'),
        ('trials-count','Clinical trial linked papers','Clinical Trials Count'),
        ('funded-papers','Grant-funded publications','Funded Publications')
    ]): card(p,n,t,m,i)
    
    visual(p,'facility-filter','slicer','Clinical facility / service',(32,224,608,72),{'Values':[col('Facility','FacilityName','Facility / service')]})
    visual(p,'year-filter','slicer','Publication year',(656,224,304,72),{'Values':[col('Publication','PublicationYear','Year')]})
    visual(p,'oa-filter','slicer','Open access status',(976,224,440,72),{'Values':[col('Publication','OpenAccessStatus','Open Access')]})
    visual(p,'study-filter','slicer','Study design',(1432,224,456,72),{'Values':[col('Publication','StudyDesign','Study Design')]})

    visual(p,'specialty-distribution','barChart','Publications by clinical directorate and specialty',(32,312,912,312),{
        'Category':[col('Facility','FacilityName','Facility / Directorate')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','Publications','Measure'),descending=True)
    
    visual(p,'for-division','barChart','ANZSRC 2020 Field of Research (FoR) division',(960,312,928,312),{
        'Category':[col('Publication','FieldOfResearch','FoR Division')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','Publications','Measure'),descending=True)

    visual(p,'oa-distribution','donutChart','Open access distribution (Gold / Green / Hybrid / Closed)',(32,640,912,304),{
        'Category':[col('Publication','OpenAccessStatus','Open Access')],
        'Y':[met('Publications','Publications')]
    })

    visual(p,'study-design-breakdown','barChart','Evidence hierarchy and study designs',(960,640,928,304),{
        'Category':[col('Publication','StudyDesign','Study Design')],
        'Y':[met('Publications','Publications')]
    },sort_field=field('Publication','Publications','Measure'),descending=True)

    visual(p,'footer','textbox','',(32,960,1856,40),text='Field of Research mapped using ANZSRC 2020 2-digit divisions. Open access classification verified via Europe PMC and OpenAlex APIs in accordance with the NHMRC Open Access Policy.')

    # Page 5: Funding Opportunities (FundingOpportunities)
    p='FundingOpportunities'
    heading(p,'Funding Opportunities','Canonical grant opportunities from reviewed federal, Queensland and institutional sources. Live list ingestion remains pending native acceptance.')
    for i,(n,t,m) in enumerate([
        ('grant-count','Opportunities','Grant Opportunities'),
        ('grant-open','Open opportunities','Open Grant Opportunities'),
        ('grant-review','Needs review','Grant Opportunities Needing Review'),
    ]):
        visual(p,n,'card',t,(32+472*i,112,440,96),{'Values':[grant_met(m)]})
    visual(p,'grant-status-filter','slicer','Opportunity status',(32,224,440,72),{'Values':[grant_col('Status','Status')]})
    visual(p,'grant-relevance-filter','slicer','CHHHS relevance',(504,224,440,72),{'Values':[grant_col('CHHHSRelevance','Relevance')]})
    visual(p,'grant-review-filter','slicer','Review state',(976,224,440,72),{'Values':[grant_col('ReviewStatus','Review status')]})
    visual(p,'grant-source-filter','slicer','Source',(1448,224,440,72),{'Values':[grant_col('Source','Source')]})
    visual(p,'grant-register','tableEx','Opportunity register',(32,328,1856,560),{'Values':[
        grant_col('Title','Opportunity'),grant_col('Funder'),grant_col('Source'),grant_col('Deadline'),
        grant_col('DeadlinePrecision','Deadline precision'),grant_col('Status'),grant_col('CHHHSRelevance','CHHHS relevance'),
        grant_col('ReviewStatus','Review status'),grant_col('URL','Source link')
    ]})
    footer(p,'Source links and review state are required. A blank or failed source batch must not replace the last accepted registry.')

    # Page 6: Funding Calendar (FundingCalendar)
    p='FundingCalendar'
    heading(p,'Funding Calendar','External deadlines are distinct from institutional dates. Cancellation and review state remain explicit.')
    visual(p,'calendar-review-filter','slicer','Review state',(32,112,440,72),{'Values':[list_col('FundingCalendar','ReviewStatus','Review status')]})
    visual(p,'calendar-cancelled-filter','slicer','Cancellation state',(504,112,440,72),{'Values':[list_col('FundingCalendar','Cancelled','Cancelled')]})
    visual(p,'calendar-policy-filter','slicer','Policy key',(976,112,440,72),{'Values':[list_col('FundingCalendar','PolicyKey','Policy')]})
    visual(p,'calendar-register','tableEx','Funding calendar data',(32,224,1856,632),{'Values':[
        list_col('FundingCalendar','CalculatedDate','Calculated date'),list_col('FundingCalendar','DeadlineKey','Deadline key'),
        list_col('FundingCalendar','ReviewStatus','Review status'),list_col('FundingCalendar','SourceURL','Source link')
    ]})
    visual(p,'calendar-note','textbox','',(32,896,1856,72),text='Institutional dates are policy-driven projections; the external source date and cancellation/review decisions remain separately traceable.')
    footer(p,'Never infer a day from a month or year-only deadline. Preserve source-stated date precision and timezone uncertainty.')

    # Page 7: My Funding Watchlist (MyFundingWatchlist)
    p='MyFundingWatchlist'
    heading(p,'My Funding Watchlist','A current-user view over explicit category or individual-opportunity subscriptions; delivery remains a separate gate.')
    visual(p,'watchlist-active-filter','slicer','Active',(32,112,440,72),{'Values':[list_col('MyFundingWatchlist','Active','Active')]})
    visual(p,'watchlist-scope-filter','slicer','Scope',(504,112,440,72),{'Values':[list_col('MyFundingWatchlist','Scope','Scope')]})
    visual(p,'watchlist-target-filter','slicer','Target',(976,112,440,72),{'Values':[list_col('MyFundingWatchlist','TargetKey','Target key')]})
    visual(p,'watchlist-note','textbox','',(1448,112,440,72),text='Personal subscription rows are persisted separately from opportunity content; no notification is implied.')
    visual(p,'watchlist-register','tableEx','Candidate watchlist',(32,224,1856,632),{'Values':[
        list_col('MyFundingWatchlist','Active','Active'),list_col('MyFundingWatchlist','OpportunityKey','Opportunity key'),
        list_col('MyFundingWatchlist','Scope','Scope'),list_col('MyFundingWatchlist','TargetKey','Target key')
    ]})
    footer(p,'Categories and individual-opportunity watches are explicit list-backed preferences; reminder/calendar delivery remains separately controlled.')

    save_json(ROOT/'audit/report-build.json',{'pages':len(pages),'visuals':len(MANIFEST),'manifest':MANIFEST,'legacy_visuals_copied':0,'legacy_filters_copied':0,'native_render_tested':False})
    print(f'Built {len(pages)} pages and {len(MANIFEST)} research-only visuals.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source_pbix',type=Path,nargs='?');args=parser.parse_args();build(args.source_pbix)
