"""Conservative identity policy for the legacy M model; not the durable registry."""
from __future__ import annotations
import re


def normalize_title(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


def normalize_doi(value: str | None) -> str | None:
    text = (value or '').strip().lower()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/', 'doi:'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text if re.fullmatch(r'10\.[0-9]{4,9}/\S+', text) else None


def normalize_pmid(value: str | None) -> str | None:
    text = (value or '').strip()
    return text if re.fullmatch(r'[1-9][0-9]*', text) else None


def reconcile_sources(pubmed: list[dict], dora: list[dict]) -> list[dict]:
    out = [dict(row, CanonicalKey='PMID:'+row['PMID'], SourceSet='PubMed', DedupMethod='PMID') for row in pubmed]
    by_pmid = {row['PMID']: row for row in out}
    for d in dora:
        doi, pmid = normalize_doi(d.get('DOI')), normalize_pmid(d.get('PMID'))
        exact = [p for p in pubmed if (doi is not None and normalize_doi(p.get('DOI')) == doi)
                 or (pmid is not None and normalize_pmid(p.get('PMID')) == pmid)]
        conflict = any((doi is not None and normalize_doi(p.get('DOI')) is not None and normalize_doi(p['DOI']) != doi)
                       or (pmid is not None and normalize_pmid(p.get('PMID')) is not None and normalize_pmid(p['PMID']) != pmid)
                       for p in exact)
        invalid = any(p.get(field) not in (None, '') and normalizer(p.get(field)) is None
                      for p in [d, *exact] for field, normalizer in [('PMID', normalize_pmid), ('DOI', normalize_doi)])
        title = normalize_title(d.get('Title'))
        candidates = [p for p in pubmed if title and d.get('PublicationYear') is not None
                      and p.get('PublicationYear') == d['PublicationYear'] and normalize_title(p.get('Title')) == title]
        if len(exact) == 1 and not conflict and not invalid:
            row = by_pmid[exact[0]['PMID']]
            row['SourceSet'] = 'PubMed; DORA'
            row['DedupMethod'] = 'PMID' if pmid == normalize_pmid(exact[0].get('PMID')) else 'DOI'
            authors = [row.get('CHHHSAffiliatedAuthors'), d.get('CHHHSAffiliatedAuthors')]
            row['CHHHSAffiliatedAuthors'] = '; '.join(dict.fromkeys(a for a in authors if a)) or None
        else:
            method = ('invalid-identifiers-needs-review' if invalid else
                      'conflicting-identifiers-needs-review' if conflict else
                      'ambiguous-identifiers-needs-review' if len(exact) > 1 else
                      'ambiguous-title+year' if len(candidates) > 1 else
                      'possible-title+year-needs-review' if candidates else 'DORA-only')
            out.append(dict(d, CanonicalKey=d['DORAKey'], SourceSet='DORA', DedupMethod=method,
                            CandidateCount=len(exact) if exact else len(candidates)))
    keys = [r['CanonicalKey'] for r in out]
    if len(keys) != len(set(keys)):
        raise ValueError('Canonical keys are not unique')
    return out
