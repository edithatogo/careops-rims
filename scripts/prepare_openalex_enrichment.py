"""Prepare a bounded private OpenAlex candidate; never write the source or tenant."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from enrich_openalex import clean_doi, extract_openalex_metrics, fetch_openalex_observation
from project_utils import ROOT


def prepare(input_path: Path, output_path: Path, limit: int = 3) -> dict:
    private = (ROOT / 'private/ops').resolve()
    source = input_path.resolve()
    destination = output_path.resolve()
    if not source.is_relative_to(private) or not destination.is_relative_to(private):
        raise ValueError('Input and output must be under ignored private/ops')
    if source == destination or destination.exists():
        raise ValueError('Output must be a new candidate; source and prior candidates are preserved')
    if not 1 <= limit <= 50:
        raise ValueError('Select between one and fifty DOI requests')
    frozen = source.read_bytes()
    records = json.loads(frozen)
    if not isinstance(records,list) or any(not isinstance(r,dict) for r in records):
        raise ValueError('Input must be an explicit publication-record list from the reviewed snapshot')
    seen = set()
    selected = []
    for record in records:
        doi = clean_doi(record.get('DOI'))
        if doi and doi.casefold() not in seen:
            seen.add(doi.casefold()); selected.append(doi)
    if not selected:
        raise ValueError("Snapshot has no valid DOI identifiers")
    observations = {}; successes = 0
    for doi in selected[:limit]:
        observation = fetch_openalex_observation(doi)
        status = observation.status
        metrics = None
        if status == 'success':
            try:
                metrics = extract_openalex_metrics(observation.payload)
            except (ValueError,TypeError,AttributeError):
                status = 'invalid_response'
        if status == 'success': successes += 1
        observations[doi.casefold()] = {
            'status':status,'attempts':observation.attempts,'http_status':observation.http_status,
            'observed_utc':datetime.now(timezone.utc).isoformat(),
            'raw_payload':observation.payload,
            'raw_response_base64':base64.b64encode(observation.raw_body).decode() if observation.raw_body else None,
            'raw_response_sha256':hashlib.sha256(observation.raw_body).hexdigest() if observation.raw_body else None,
            'metrics':metrics,
        }
        # One access/quota/service failure stops this provider pass, not a cascade.
        if status in ('access_denied','rate_limited','unavailable','http_error'):
            break
    candidate = [dict(r) for r in records]
    for record in candidate:
        doi = clean_doi(record.get('DOI'))
        outcome = observations.get(doi.casefold()) if doi else None
        if outcome:
            record['OpenAlexAttemptStatus'] = outcome['status']
            if outcome['status']=='success':
                record.update({k:v for k,v in outcome['metrics'].items() if v is not None})
                record['CitationMetricsObservedUTC'] = outcome['observed_utc']
    result={'input_sha256':hashlib.sha256(frozen).hexdigest(),
            'native_acceptance':False,'observations':observations,'candidate_records':candidate,
            'summary':{'requests':len(observations),'successes':successes,
                       'failures':sum(x['status'] not in ('success','not_found') for x in observations.values()),
                       'records_preserved':len(candidate)}}
    if source.read_bytes()!=frozen:
        raise ValueError('Source snapshot changed during preparation; candidate not saved')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation, owner-only permissions: never overwrite accepted data.
    import os
    descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as output:
        json.dump(result,output,ensure_ascii=False,indent=2)
    return result['summary']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--limit',type=int,default=3)
    args=parser.parse_args()
    try:
        summary=prepare(args.input,args.output,args.limit)
        print(json.dumps(summary))
        raise SystemExit(1 if summary['failures'] else 0)
    except (ValueError,OSError,TypeError) as error:
        print(json.dumps({'status':'not_prepared','error_type':type(error).__name__}))
        raise SystemExit(1)
