"""Offline reference checks for the M ingestion contract, not an executed M engine."""
from __future__ import annotations
from typing import Any

def reconcile_search(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    if 'error' in payload: raise ValueError(str(payload['error']))
    search=payload.get('esearchresult')
    if not isinstance(search,dict): raise ValueError('Missing esearchresult')
    if 'ERROR' in search: raise ValueError(str(search['ERROR']))
    errors=search.get('errorlist',{})
    if not isinstance(errors,dict): raise ValueError('Unexpected errorlist')
    if any(value for key,value in errors.items() if key!='phrasesnotfound'):
        raise ValueError('Fatal ESearch query error')
    count=int(search['count']);ids=[str(x) for x in search['idlist']]
    if count>10000: raise ValueError('Search needs segmentation above 10000 PMIDs')
    if count<0 or count!=len(set(ids)): raise ValueError('ESearch count mismatch')
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate ESearch PMIDs')
    warnings=dict(search.get('warninglist',{}))
    if errors.get('phrasesnotfound'): warnings['phrasesnotfound']=errors['phrasesnotfound']
    return ids,warnings

def reconcile_summary(expected: list[str],payload: dict[str,Any]) -> list[dict[str,Any]]:
    result=payload.get('result')
    if not isinstance(result,dict): raise ValueError('Missing ESummary result')
    returned=[str(x) for x in result.get('uids',[])]
    if set(expected)!=set(returned) or len(expected)!=len(returned) or len(returned)!=len(set(returned)):
        raise ValueError('ESummary PMID reconciliation failed')
    rows=[]
    for pmid in returned:
        row=result.get(pmid)
        if not isinstance(row,dict) or 'error' in row or str(row.get('uid'))!=pmid: raise ValueError('Invalid summary record')
        rows.append(row)
    return rows

def facility_union(matches: dict[str,list[str]]) -> tuple[set[str],set[tuple[str,str]]]:
    pairs={(str(pmid),facility) for facility,ids in matches.items() for pmid in ids}
    return {p for p,_ in pairs},pairs
