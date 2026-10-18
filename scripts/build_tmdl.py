"""Serialize the generated semantic-model snapshot into Fabric Git TMDL files."""
from __future__ import annotations
import json, shutil
from pathlib import Path
from project_utils import ROOT

SEM=ROOT/'powerbi/CHHHS Research Publications.SemanticModel'
SNAP=ROOT/'audit/model.snapshot.json'

def q(name:str)->str:
    if name and all(c.isalnum() or c=='_' for c in name) and not name[0].isdigit(): return name
    return "'"+name.replace("'","''")+"'"

def flag(name:str,value:bool)->list[str]: return [f'\t{name}'] if value else []
def indent_expr(text:str, level:int)->str:
    pad='\t'*level
    return '\n'.join(pad+line for line in text.splitlines())

def build() -> None:
    if not SNAP.exists(): raise FileNotFoundError('Run scripts/build_model.py first to create audit/model.snapshot.json')
    data=json.loads(SNAP.read_text())
    db=data; model=data['model']
    target=SEM/'definition'
    if target.exists(): shutil.rmtree(target)
    (target/'tables').mkdir(parents=True)
    (target/'database.tmdl').write_text(f"database {q(db.get('name','CHHHS Research Publications'))}\n\tcompatibilityLevel: {db.get('compatibilityLevel',1600)}\n")
    model_lines=['model Model',f"\tculture: {model.get('culture','en-AU')}",f"\tdefaultPowerBIDataSourceVersion: {model.get('defaultPowerBIDataSourceVersion','powerBI_V3')}",f"\tsourceQueryCulture: {model.get('sourceQueryCulture','en-AU')}"]
    for ann in model.get('annotations',[]):
        model_lines.append(f"\tannotation {q(ann['name'])} = {ann['value']}")
    for expr in model.get('expressions',[]):
        text='\n'.join(expr['expression'])
        if '\n' in text:
            model_lines.append(f"\nexpression {q(expr['name'])} =")
            model_lines.append(indent_expr(text,1))
        else:
            model_lines.append(f"\nexpression {q(expr['name'])} = {text}")
        if expr.get('lineageTag'): model_lines.append(f"\tlineageTag: {expr['lineageTag']}")
    (target/'model.tmdl').write_text('\n'.join(model_lines)+'\n')
    for table in model['tables']:
        lines=[f"table {q(table['name'])}"]
        if table.get('description'): lines.append(f"\tdescription: {json.dumps(table['description'])}")
        if table.get('isHidden'): lines.append('\tisHidden')
        if table.get('dataCategory'): lines.append(f"\tdataCategory: {table['dataCategory']}")
        if table.get('lineageTag'): lines.append(f"\tlineageTag: {table['lineageTag']}")
        for col in table.get('columns',[]):
            lines.append(f"\n\tcolumn {q(col['name'])}")
            lines.append(f"\t\tdataType: {col['dataType']}")
            if col.get('formatString') is not None: lines.append(f"\t\tformatString: {col['formatString']}")
            if col.get('isHidden'): lines.append('\t\tisHidden')
            if col.get('isKey'): lines.append('\t\tisKey')
            if col.get('dataCategory'): lines.append(f"\t\tdataCategory: {col['dataCategory']}")
            if col.get('lineageTag'): lines.append(f"\t\tlineageTag: {col['lineageTag']}")
            lines.append(f"\t\tsummarizeBy: {col.get('summarizeBy','none')}")
            lines.append(f"\t\tsourceColumn: {q(col.get('sourceColumn',col['name']))}")
            if col.get('sortByColumn'): lines.append(f"\t\tsortByColumn: {q(col['sortByColumn'])}")
        for meas in table.get('measures',[]):
            expr=meas['expression']
            if '\n' in expr:
                lines.append(f"\n\tmeasure {q(meas['name'])} =")
                lines.append(indent_expr(expr,2))
            else:
                lines.append(f"\n\tmeasure {q(meas['name'])} = {expr}")
            if meas.get('formatString'): lines.append(f"\t\tformatString: {meas['formatString']}")
            if meas.get('lineageTag'): lines.append(f"\t\tlineageTag: {meas['lineageTag']}")
        for part in table.get('partitions',[]):
            src=part['source']; lines.append(f"\n\tpartition {q(part['name'])} = {src['type']}")
            lines.append(f"\t\tmode: {part.get('mode','import')}")
            lines.append('\t\tsource =')
            lines.append(indent_expr('\n'.join(src['expression']),3))
        (target/'tables'/f"{table['name']}.tmdl").write_text('\n'.join(lines)+'\n')
    rel=[]
    for r in model.get('relationships',[]):
        rel.append(f"relationship {q(r['name'])}")
        if not r.get('isActive',True): rel.append('\tisActive: false')
        rel.append(f"\tfromColumn: {q(r['fromTable'])}.{q(r['fromColumn'])}")
        rel.append(f"\ttoColumn: {q(r['toTable'])}.{q(r['toColumn'])}")
        if r.get('crossFilteringBehavior'): rel.append(f"\tcrossFilteringBehavior: {r['crossFilteringBehavior']}")
        rel.append('')
    (target/'relationships.tmdl').write_text('\n'.join(rel))
    print(f'Built TMDL definition with {len(model["tables"])} tables and {len(model.get("relationships",[]))} relationships.')

if __name__=='__main__': build()
