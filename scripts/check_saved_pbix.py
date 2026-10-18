"""Reject known old model/cache and metadata regressions in a saved PBIX.

A passing result is NOT an attestation about opaque binary model contents.
Re-open in Desktop and validate a saved PBIP as required by T05.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from project_utils import ROOT,save_json
from audit_pbix import decode
from validate_project import LEGACY

def inspect(path:Path)->dict:
    old=json.loads((ROOT/'audit/source-audit.json').read_text())['original']['entries']['DataModel']['sha256']
    flags=[];scanned=0
    with zipfile.ZipFile(path) as archive:
        if 'DataModel' in archive.namelist():
            digest=hashlib.sha256(archive.read('DataModel')).hexdigest()
            if digest==old: flags.append('Active model equals the original employment model byte-for-byte')
        else: digest=None
        for name in archive.namelist():
            if name in {'Report/Layout','Report/LinguisticSchema','DiagramLayout','DiagramState'} or name.endswith(('.tmdl','.json')):
                data=archive.read(name)
                if not data: continue
                try: text=decode(data)
                except UnicodeError: continue
                scanned+=1
                if LEGACY.search(text): flags.append('Employment vocabulary in '+name)
                if 'Sql.Database' in text: flags.append('SQL query remains in '+name)
    return {'status':'FAIL' if flags else 'PASS_METADATA_GATE_ONLY','flags':flags,'active_model_sha256':digest,'metadata_entries_scanned':scanned,'binary_model_semantics_decoded':False,'required_next_check':'Reopen in Desktop and inspect active model; save PBIP and validate its definitions.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pbix',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
    result=inspect(args.pbix)
    if args.output: save_json(args.output,result)
    print(json.dumps(result,indent=2));raise SystemExit(1 if result['flags'] else 0)
