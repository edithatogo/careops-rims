"""Produce auditable attribution and duplicate recommendations; never merge by title."""
import argparse
import datetime as dt
from collections import defaultdict
import json
from pathlib import Path
import re
import unicodedata
from collect_pubmed import atomic_json
from publication_registry import Registry


def normal(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', value).casefold()))


def recommendations(registry, facilities):
    rules=[]
    for facility in facilities['rows']:
        if facility['Active']:
            aliases=re.findall(r'"([^"]+)"\[Affiliation\]', facility['PubMedQuery'])
            rules.append((facility['FacilityName'],[normal(a) for a in aliases], 'AND' in facility['PubMedQuery']))
    results=[]
    titles=defaultdict(list)
    for row in registry.records():
        pid=row['CanonicalKey']
        evidence=[];authors=set();matched=set();warnings=[]
        versions=registry.db.execute('''SELECT v.payload FROM source_record s JOIN source_version v
            ON v.source=s.source AND v.source_id=s.source_id AND v.content_hash=s.latest_hash
            WHERE s.publication_id=?''',(pid,))
        for version in versions:
            payload=json.loads(version[0])
            if payload.get('identifier_warnings'):
                warnings.append('Malformed source identifier requires review')
            for author in payload.get('authors',[]):
                for aff in author.get('affiliations',[]):
                    text=' '+normal(aff)+' '
                    for facility,aliases,geo in rules:
                        if any(' '+alias+' ' in text for alias in aliases) and (not geo or re.search(r'\b(australia|queensland|qld)\b',text)):
                            matched.add(facility);authors.add(author['name']);evidence.append(aff)
            attribution=payload.get('attribution_evidence','')
            if re.search(r'^(?:Cairns\s*(?:&|and)\s*Hinterland(?: Hospital and Health Service)?(?:\s*\(CHHHS\))?|CHHHS)\s+affiliated authors?\s*:',attribution,re.I):
                evidence.append(attribution)
                statement = re.search(r'affiliated authors?\s*:\s*(.+)', attribution, re.I)
                if statement:
                    authors.add(statement.group(1).strip())
        results.append({'CanonicalKey':pid,'current_status':row['ReviewStatus'],
                        'recommendation':'included' if evidence and not warnings else 'needs_review',
                        'basis':'; '.join(warnings) if warnings else ('Explicit source affiliation under configured rules' if evidence else 'No decisive author affiliation retained'),
                        'authors':sorted(authors),'facilities':sorted(matched),'evidence':sorted(set(evidence))})
        titles[(normal(row['Title']),row['PublicationYear'])].append(pid)
    duplicate_groups=[{'normalized_title':title,'year':year,'keys':keys,'action':'manual_identifier_review_no_auto_merge'}
                      for (title,year),keys in titles.items() if len(keys)>1]
    return {'attribution':results,'duplicate_candidates':duplicate_groups,'human_review':False}


def apply_supported_recommendations(registry, report, decided_at):
    """Apply evidence-supported inclusion only; preserve all existing decisions."""
    applied = 0
    for item in report['attribution']:
        current = registry.db.execute('SELECT review_status FROM publication WHERE id=?', (item['CanonicalKey'],)).fetchone()
        reviewed = registry.db.execute('SELECT count(*) FROM review_event WHERE publication_id=?', (item['CanonicalKey'],)).fetchone()[0]
        if current and current[0] == 'needs_review' and not reviewed and item['recommendation'] == 'included':
            registry.record_attribution(item['CanonicalKey'], item['authors'], item['facilities'], item['evidence'])
            registry.review(item['CanonicalKey'], 'included', item['basis'] + '; automated evidence review, not human approval',
                            'codex-source-evidence-review', decided_at)
            applied += 1
    return applied

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--apply-supported',action='store_true',help='Record supported inclusions without overriding existing decisions')
    args=parser.parse_args();db=Registry(args.database,'live_export')
    try:
        report=recommendations(db,json.loads((Path(__file__).resolve().parents[1]/'config/facilities.json').read_text()))
        report['decided_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        if args.apply_supported:
            report['applied']=apply_supported_recommendations(db,report,report['decided_at'])
        atomic_json(args.output,report)
    finally:db.close()
