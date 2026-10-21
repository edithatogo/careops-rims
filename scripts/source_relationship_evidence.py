"""Project explicit retained-source assertions; never infer identities from names."""
from __future__ import annotations
import base64
import hashlib
import itertools
import json
import re
from collections import defaultdict


def normalise_doi(value):
    if not isinstance(value,str): return ''
    value=value.strip().lower()
    for prefix in ('https://doi.org/','http://doi.org/','http://dx.doi.org/','https://dx.doi.org/'):
        if value.startswith(prefix): value=value[len(prefix):]
    return value if re.fullmatch(r'10\.\d{4,9}/\S+',value) else ''


def orcid_status(value):
    if not value:return 'Absent'
    s=value.removeprefix('https://orcid.org/').removeprefix('http://orcid.org/')
    if not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]',s):return 'Invalid'
    total=0
    for c in s.replace('-','')[:15]:total=(total+int(c))*2
    check=(12-total%11)%11
    return 'Valid syntax; unauthenticated' if s[-1]==('X' if check==10 else str(check)) else 'Invalid'


def provider_id(value,kind):
    return value if isinstance(value,str) and re.fullmatch(r'https://openalex\.org/'+kind+r'[0-9]+',value) else ''


def project(envelopes,publications):
    """Return all evidence, including unknown/ambiguous canonical assignments."""
    mappings=defaultdict(set)
    for p in publications:
        doi=normalise_doi(p.get('DOI'))
        if doi:mappings[doi].add(p['CanonicalKey'])
    parsed=[];seen_work=set();author_orcids=defaultdict(set)
    for e in envelopes:
        raw=base64.b64decode(e['raw_response_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=e['raw_response_sha256']:raise ValueError('Raw source hash mismatch')
        w=json.loads(raw)
        if not provider_id(w.get('id'),'W') or e['work_id']!=w['id']:raise ValueError('Work identity mismatch')
        if normalise_doi(e['requested_doi'])!=normalise_doi(w.get('doi')) or not normalise_doi(w.get('doi')):raise ValueError('DOI identity mismatch')
        if w['id'] in seen_work:raise ValueError('Duplicate retained work')
        seen_work.add(w['id']);parsed.append((e,w))
        for a in w.get('authorships',[]):
            author=a.get('author') or {};aid=provider_id(author.get('id'),'A');o=author.get('orcid') or ''
            if aid and orcid_status(o).startswith('Valid'):author_orcids[aid].add(o.removeprefix('https://orcid.org/').removeprefix('http://orcid.org/'))
    reverse=defaultdict(set)
    for aid,values in author_orcids.items():
        for o in values:reverse[o].add(aid)
    actor_keys={aid:'orcid:'+next(iter(values)) for aid,values in author_orcids.items() if len(values)==1 and len(reverse[next(iter(values))])==1}
    result={}
    for e,w in parsed:
        doi=normalise_doi(w['doi']);ks=sorted(mappings[doi]);canonical=ks[0] if len(ks)==1 else ''
        def add(kind,from_key,to_key,from_label='',to_label='',orcid='',identity='Source-supported',ror=''):
            k='|'.join([w['id'],kind,from_key,to_key])
            row=dict(EvidenceKey=k,RelationshipKind=kind,SourceWorkID=w['id'],PublicationDOI=doi,PublicationPMID='',ReferenceType='',FromKey=from_key,ToKey=to_key,FromLabel=from_label or '',ToLabel=to_label or '',ORCID=orcid,ORCIDStatus=orcid_status(orcid),ROR=ror,IdentityStatus=identity,SourceURL=w['id'],ObservedUTC=e['observed_utc'],RawSHA256=e['raw_response_sha256'],SourceVersion=e['raw_response_sha256'],CanonicalKey=canonical,CanonicalMatchCount=len(ks),ReviewState='Not reviewed',AuthenticationState='Not authenticated')
            if k in result and result[k]!=row:raise ValueError('Conflicting repeated assertion')
            result[k]=row
        add('publication','doi:'+doi,w['id'])
        aids={};iids={}
        for i,a in enumerate(w.get('authorships',[]),1):
            author=a.get('author') or {};aid=provider_id(author.get('id'),'A');o=author.get('orcid') or '';state='Source-supported'
            if not aid:aid=w['id']+'/unresolved-author/'+str(i);state='Unresolved identity'
            elif len(author_orcids[aid])>1:state='Conflicting identifiers'
            provider_actor=aid
            aid=actor_keys.get(aid,aid)
            if provider_actor in actor_keys and orcid_status(o).startswith('Valid'):
                add('identity_alias',provider_actor,aid,author.get('display_name'),o,o,state)
            add('authorship','doi:'+doi,aid,to_label=author.get('display_name') or a.get('raw_author_name') or '',orcid=o,identity=state)
            if state=='Source-supported':aids[aid]=author.get('display_name') or ''
            for inst in a.get('institutions',[]):
                iid=provider_id(inst.get('id'),'I')
                if iid:
                    add('publication_affiliation',aid,iid,author.get('display_name'),inst.get('display_name'),o,state,inst.get('ror') or '')
                    iids[iid]=inst.get('display_name') or ''
        for a,b in itertools.combinations(sorted(aids),2):add('coauthorship',a,b,aids[a],aids[b])
        for a,b in itertools.combinations(sorted(iids),2):add('institution_cooccurrence',a,b,iids[a],iids[b])
        for award in w.get('awards',[]):
            gid=provider_id(award.get('id'),'G');funder=provider_id(award.get('funder_id'),'F');number=award.get('funder_award_id') or ''
            if gid:add('publication_award','doi:'+doi,gid,to_label=(award.get('funder_display_name') or '')+' | '+number)
            elif funder and number:add('publication_award','doi:'+doi,funder+'/award/'+number,to_label=number)
    return sorted(result.values(),key=lambda r:r['EvidenceKey'])


def study_references(studies,publications):
    """Explicit result/derived references only; no background citation as output."""
    index=defaultdict(set)
    for p in publications:
        if p.get('PMID'):index[str(p['PMID'])].add(p['CanonicalKey'])
    out=[]
    for item in studies:
        s=item['record'];nct=s['protocolSection']['identificationModule']['nctId']
        if not re.fullmatch(r'NCT[0-9]{8}',nct):raise ValueError('Invalid study identifier')
        raw=item['raw'];h=hashlib.sha256(raw).hexdigest()
        for ref in s['protocolSection'].get('referencesModule',{}).get('references',[]):
            pmid=ref.get('pmid') or '';kind=ref.get('type')
            if kind not in {'RESULT','DERIVED'} or not pmid.isdecimal():continue
            ks=sorted(index[pmid]);source='clinicaltrials.gov:'+nct
            out.append(dict(EvidenceKey='|'.join([source,'publication_study_reference','pmid:'+pmid,source]),RelationshipKind='publication_study_reference',SourceWorkID=source,PublicationDOI='',PublicationPMID=pmid,ReferenceType=kind,FromKey='pmid:'+pmid,ToKey=source,FromLabel='',ToLabel=nct,ORCID='',ORCIDStatus='Absent',ROR='',IdentityStatus='Source-supported',SourceURL='https://clinicaltrials.gov/study/'+nct,ObservedUTC=item['observed_utc'],RawSHA256=h,SourceVersion=h,CanonicalKey=ks[0] if len(ks)==1 else '',CanonicalMatchCount=len(ks),ReviewState='Not reviewed',AuthenticationState='Not authenticated'))
    dedup={}
    for r in out:
        k=r['EvidenceKey']
        if k in dedup and dedup[k]!=r:raise ValueError('Conflicting study reference')
        dedup[k]=r
    return sorted(dedup.values(),key=lambda r:r['EvidenceKey'])


def orcid_normalised(value):
    return (value or '').strip().removeprefix('https://orcid.org/').removeprefix('http://orcid.org/')


def pubmed_projection(records,publications):
    """Structured Author identifiers and explicit GrantList/DataBankList only."""
    index=defaultdict(set)
    for p in publications:
        if p.get('PMID'):index[str(p['PMID'])].add(p['CanonicalKey'])
    def children(node,name):
        xs=node if isinstance(node,list) else node.get('Value',[]) if isinstance(node,dict) else []
        return [x for x in xs if isinstance(x,dict) and x.get('Name')==name] if isinstance(xs,list) else []
    def child(node,name):return next(iter(children(node,name)),{})
    def text(node):
        v=node.get('Value','') if isinstance(node,dict) else node
        return ''.join(text(x) for x in v) if isinstance(v,list) else str(v or '')
    # Accepted PubMed metadata supplies batch lineage, not original raw bytes.
    # Empty RawSHA256 is unavailable provenance; never hash reserialized metadata
    # and misrepresent it as a fingerprint of the original provider payload.
    result={}
    for record in records:
        pmid=record['pmid'];citation=child(record['metadata'],'MedlineCitation')
        if text(child(citation,'PMID'))!=pmid:raise ValueError('PubMed payload PMID mismatch')
        article=child(citation,'Article');source='pubmed:'+pmid;ks=sorted(index[pmid]);canonical=ks[0] if len(ks)==1 else ''
        def add(kind,f,t,fl='',tl='',orcid='',identity='Source-supported',ref=''):
            k='|'.join([source,kind,f,t])
            if kind=='publication_affiliation':k+='|'+tl.encode().hex().upper()
            r=dict(EvidenceKey=k,RelationshipKind=kind,SourceWorkID=source,PublicationDOI='',PublicationPMID=pmid,ReferenceType=ref,FromKey=f,ToKey=t,FromLabel=fl,ToLabel=tl,ORCID=orcid,ORCIDStatus=orcid_status(orcid),ROR='',IdentityStatus=identity,SourceURL='https://pubmed.ncbi.nlm.nih.gov/'+pmid+'/',ObservedUTC=record.get('observed_utc',''),RawSHA256='',SourceVersion=record.get('source_version',''),CanonicalKey=canonical,CanonicalMatchCount=len(ks),ReviewState='Not reviewed',AuthenticationState='Not authenticated')
            if k in result and result[k]!=r:raise ValueError('Conflicting PubMed source assertion')
            result[k]=r
        add('publication','pmid:'+pmid,source)
        people={};institutions={}
        for i,a in enumerate(children(child(article,'AuthorList'),'Author'),1):
            name=text(child(a,'CollectiveName')) or ' '.join(filter(None,[text(child(a,'ForeName')) or text(child(a,'Initials')),text(child(a,'LastName')),text(child(a,'Suffix'))]))
            ids=[]
            for node in children(a,'Identifier'):
                attrs={x.get('Name'):x.get('Value') for x in node.get('Attributes',[])}
                if attrs.get('Source')=='ORCID':ids.append(orcid_normalised(text(node)))
            ids=sorted(set(ids));o=ids[0] if len(ids)==1 else ''
            good=len(ids)==1 and orcid_status(o).startswith('Valid')
            actor='orcid:'+o if good else source+'/unresolved-author/'+str(i)
            state='Source-supported' if good else 'Conflicting identifiers' if len(ids)>1 else 'Unresolved identity'
            add('authorship','pmid:'+pmid,actor,tl=name,orcid=o,identity=state)
            if good:people[actor]=name
            for af in children(a,'AffiliationInfo'):
                label=text(child(af,'Affiliation'))
                for node in children(af,'Identifier'):
                    attrs={x.get('Name'):x.get('Value') for x in node.get('Attributes',[])};value=text(node).strip()
                    if attrs.get('Source')=='RINGGOLD' and value.isdecimal():
                        iid='ringgold:'+value;institutions.setdefault(iid,label)
                        add('publication_affiliation',actor,iid,name,label,o,state)
        for a,b in itertools.combinations(sorted(people),2):add('coauthorship',a,b,people[a],people[b])
        for a,b in itertools.combinations(sorted(institutions),2):add('institution_cooccurrence',a,b,institutions[a],institutions[b])
        for i,g in enumerate(children(child(article,'GrantList'),'Grant'),1):
            number=text(child(g,'GrantID'));agency=text(child(g,'Agency'));country=text(child(g,'Country'))
            if not number:continue
            key='pubmed:grant:'+'|'.join(v.encode().hex().upper() for v in [agency,country,number])
            state='Source-supported' if agency else 'Unresolved award namespace'
            add('publication_grant_reference','pmid:'+pmid,key,tl=agency+' | '+number,identity=state,ref='PubMed GrantList; source-scoped agency label')
        for db in children(child(article,'DataBankList'),'DataBank'):
            name=text(child(db,'DataBankName')).casefold()
            schemes={'clinicaltrials.gov':('clinicaltrials.gov',r'NCT[0-9]{8}'),'anzctr':('anzctr',r'ACTRN[0-9]{14}'),'isrctn':('isrctn',r'ISRCTN[0-9]{8}')}
            if name not in schemes:continue
            scheme,pattern=schemes[name]
            for n in children(child(db,'AccessionNumberList'),'AccessionNumber'):
                value=text(n).strip().upper()
                if re.fullmatch(pattern,value):add('publication_study_reference','pmid:'+pmid,scheme+':'+value,tl=value,ref='PubMed DataBankList')
    return sorted(result.values(),key=lambda r:r['EvidenceKey'])
