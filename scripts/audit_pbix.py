"""Inspect a PBIX without executing embedded queries or loading cached data."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

LEGACY = re.compile(r'\b(?:Employee|EmplID|Gender|Ethnicity|New Hires|Bad Hires|Separations|TermReason|Business unit|Age group|Part-Time|Full-Time|Male|Female|SALES AND MARKETING)\b', re.I)

def decode(data: bytes) -> str:
    if data.startswith(b'\xff\xfe'):
        return data.decode('utf-16')
    if b'\x00' in data[:100]:
        return data.decode('utf-16-le')
    return data.decode('utf-8-sig')

def expand(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v) for v in value]
    if isinstance(value, str) and value.lstrip().startswith(('{', '[')):
        try:
            return expand(json.loads(value))
        except json.JSONDecodeError:
            pass
    return value

def strings(value: Any, path: str = '$') -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(strings(v, f'{path}.{k}'))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.extend(strings(v, f'{path}[{i}]'))
    elif isinstance(value, str):
        out.append((path, value))
    return out

def audit(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        entries = {name: {'bytes': len(archive.read(name)), 'sha256': hashlib.sha256(archive.read(name)).hexdigest()} for name in archive.namelist()}
        layout = expand(json.loads(decode(archive.read('Report/Layout'))))
        pages = []
        for section in layout['sections']:
            hits = [{'path': p, 'matches': sorted(set(LEGACY.findall(t)))} for p,t in strings(section) if LEGACY.search(t)]
            literals = [{'path':p, 'value':t} for p,t in strings(section.get('filters', [])) if t in ('2014L', "'Dec'")]
            entities = sorted({t for p,t in strings(section) if p.endswith('.Entity')})
            pages.append({'name':section['displayName'], 'visuals':len(section['visualContainers']), 'legacy_string_locations':len(hits), 'legacy_hits':hits, 'entities':entities, 'legacy_date_filters':literals})
        scripts = []
        for name in archive.namelist():
            if name.endswith('.tmdl'):
                text = decode(archive.read(name))
                scripts.append({'entry':name, 'legacy_term_count':len(LEGACY.findall(text)), 'sql_database_calls':text.count('Sql.Database'), 'tables':re.findall(r'^\s*table (.+)$',text,re.M)})
        return {'filename':path.name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'entries':entries, 'pages':pages, 'scripts':scripts, 'zip_integrity_error':archive.testzip()}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('original',type=Path)
    parser.add_argument('adapted',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    original, adapted = audit(args.original), audit(args.adapted)
    unchanged = sorted(set(original['entries']) & set(adapted['entries']))
    unchanged = [n for n in unchanged if original['entries'][n]['sha256']==adapted['entries'][n]['sha256']]
    result={'audit_date':'2026-09-11', 'original':original,'adapted':adapted,'unchanged_entries':unchanged, 'data_model_identical': 'DataModel' in unchanged, 'total_legacy_layout_locations':sum(p['legacy_string_locations'] for p in adapted['pages'])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'data_model_identical':result['data_model_identical'],'legacy_locations':result['total_legacy_layout_locations'],'unchanged_entries':unchanged},indent=2))

if __name__=='__main__':
    main()
