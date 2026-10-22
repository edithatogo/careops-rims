"""Prepare a private, reversible PubMed snapshot definition without native writes.

One imported M partition produces the five source/audit outputs from shared,
buffered local bindings. New hidden staging tables project their exact logical
schemas in DAX; all existing source tables and consumer identities remain intact.
This removes independent cloud evaluations of the same harvest dependency tree.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private/ops"
TABLES = ("PubMedPublications", "PubMedMetadataChunks", "PubMedAuthorEvidence",
          "SearchAudit", "PubMedIngestionAudit")
SNAPSHOT = "PubMedSourceSnapshot"
PROJECTIONS = {t: "Fresh" + t for t in TABLES}
LOCAL_NAMES = {name: "__Snapshot" + name for name in
               (*TABLES, "PubMedHarvest", "PubMedFullMetadata", "CurrentPubMedPublications")}


def local_references(source: str, mapping: dict[str, str]) -> str:
    """Rewrite M identifiers, preserving strings, comments and field selectors."""
    token = re.compile(r'"(?:""|[^"])*"|//[^\n]*|/\*.*?\*/|[A-Za-z_][A-Za-z0-9_]*', re.S)
    def replace(match: re.Match) -> str:
        value = match.group()
        before = source[:match.start()].rstrip()
        if value in mapping and not before.endswith("["):
            return mapping[value]
        return value
    return token.sub(replace, source)


def private(path: Path) -> Path:
    result = path.resolve()
    if not result.is_relative_to(PRIVATE.resolve()) or path.is_symlink():
        raise ValueError("Use a regular ignored private/ops path")
    return result


def expression(source: str, name: str) -> str:
    match = re.search(r"^expression " + re.escape(name)
                      + r" =\n(.*?)(?=\n(?:expression |\tlineageTag:|\tannotation )|\Z)",
                      source, re.M | re.S)
    if not match:
        raise ValueError(f"Exact named M expression missing: {name}")
    body = textwrap.dedent(match[1]).strip()
    if re.search(r"^expression ", body, re.M):
        raise ValueError("Named expression extraction crossed a TMDL object boundary")
    return body


def partition(source: str, name: str) -> tuple[str, str]:
    marker = f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource ="
    if source.count(marker) != 1:
        raise ValueError(f"Require exactly one imported M partition: {name}")
    prefix, body = source.split(marker)
    if re.search(r"^\t(?:annotation|partition|hierarchy|measure) ", body, re.M):
        raise ValueError("Trailing table objects need an explicit preservation adapter")
    return prefix, textwrap.dedent(body).strip()


def columns(source: str) -> list[tuple[str, str]]:
    result = re.findall(r"^\tcolumn (\w+)\n\t\tdataType: (\w+)", source, re.M)
    if not result or len(result) != len(re.findall(r"^\tcolumn ", source, re.M)):
        raise ValueError("Require the existing simple, explicit typed column schema")
    return result


def prepare(input_path: Path, output_path: Path, receipt_path: Path,
            *, additive_projections: bool = True) -> dict:
    if not additive_projections:
        raise ValueError("Native updateDefinition forbids converting existing tables; use additive staging projections")
    input_path, output_path, receipt_path = map(private, (input_path, output_path, receipt_path))
    if output_path.exists() or receipt_path.exists():
        raise ValueError("Recovery outputs already exist; review exact artifacts before replacement")
    raw = input_path.read_bytes()
    original = json.loads(raw)
    result = copy.deepcopy(original)
    definition = result["definition"]
    parts = definition["parts"]
    by_path = {p["path"]: p for p in parts}
    if len(by_path) != len(parts) or f"definition/tables/{SNAPSHOT}.tmdl" in by_path:
        raise ValueError("Unexpected duplicate parts or an existing snapshot")
    texts = {path: base64.b64decode(p["payload"]).decode("utf-8")
             for path, p in by_path.items()}
    shared = texts["definition/expressions.tmdl"]
    bodies = {}
    prefixes = {}
    schemas = {}
    union = {"SourceKind": "string"}
    for table in TABLES:
        path = f"definition/tables/{table}.tmdl"
        prefixes[table], bodies[table] = partition(texts[path], table)
        schemas[table] = columns(prefixes[table])
        for name, dtype in schemas[table]:
            if name in union and union[name] != dtype:
                raise ValueError(f"Incompatible snapshot column types: {name}")
            union[name] = dtype
    retained_body = partition(texts["definition/tables/RetainedPubMedPublications.tmdl"],
                              "RetainedPubMedPublications")[1]
    bindings = [("__RetainedRows", f"Table.Buffer(({retained_body}))"),
                ("__RetainedFull", "Table.Buffer((" + expression(shared, "RetainedPubMedFullMetadata") + "))"),
                ("__SnapshotHarvestRaw", "(" + expression(shared, "PubMedHarvest") + ")"),
                ("PubMedHarvest", 'if Value.Is(__SnapshotHarvestRaw,type record) and '
                 'Record.HasFields(__SnapshotHarvestRaw,{"Publications","Matches","SearchAudit","IDs"}) '
                 'then [Publications=Table.Buffer(__SnapshotHarvestRaw[Publications]),'
                 'Matches=Table.Buffer(__SnapshotHarvestRaw[Matches]),'
                 'SearchAudit=Table.Buffer(__SnapshotHarvestRaw[SearchAudit]),'
                 'IDs=List.Buffer(__SnapshotHarvestRaw[IDs])] '
                 'else error Error.Record("PubMedSnapshotHarvestShape",'
                 '"Harvest must return its complete source/audit record",null)'),
                ("PubMedFullMetadata", "Table.Buffer((" + expression(shared, "PubMedFullMetadata") + "))"),
                ("CurrentPubMedPublications", "Table.Buffer((" + expression(shared, "CurrentPubMedPublications") + "))")]
    bindings += [(table, f"Table.Buffer(({bodies[table]}))") for table in TABLES]
    # Retained source values are also shared locally; table-valued buffers do
    # not provide a cache across independent cloud partition evaluations.
    def retained_local(body: str) -> str:
        body = re.sub(r"\bRetainedPubMedFullMetadata\b", "__RetainedFull", body)
        return re.sub(r"\bRetainedPubMedPublications\b", "__RetainedRows", body)
    m_lines = ["let"]
    m_lines.append('    __SnapshotForce = (stage as text, action as function) as any => '
                   'let Attempt = try action() in if Attempt[HasError] then '
                   'error Error.Record("PubMedSnapshotStage", stage & ": " & '
                   'Text.From(Record.FieldOrDefault(Attempt[Error],"Message","source evaluation failed")), '
                   '[Stage=stage,OriginalError=Attempt[Error]]) else Attempt[Value],')
    for name, body in bindings:
        # The raw harvest has its own internal SearchAudit binding and record
        # field. Keep its lexical scope intact; downstream local names are
        # distinct from every existing global query and table name.
        body = retained_local(body)
        if name not in {"__SnapshotHarvestRaw", "PubMedHarvest"}:
            body = local_references(body, LOCAL_NAMES)
        if name == "PubMedHarvest":
            for field in ("Publications", "Matches", "SearchAudit"):
                before = f"Table.Buffer(__SnapshotHarvestRaw[{field}])"
                after = f'__SnapshotForce("Harvest.{field}",()=>{before})'
                body = body.replace(before, after)
            body = body.replace("List.Buffer(__SnapshotHarvestRaw[IDs])",
                                '__SnapshotForce("Harvest.IDs",()=>List.Buffer(__SnapshotHarvestRaw[IDs]))')
        local_name = LOCAL_NAMES.get(name, name)
        stage = name.replace("__", "")
        wrapped = f'__SnapshotForce("{stage}",()=>({body}))'
        m_lines.append("    " + local_name + " = " + wrapped.replace("\n", "\n    ") + ",")
    tagged = [f'Table.AddColumn({LOCAL_NAMES[table]}, "SourceKind", each "{table}", type text)' for table in TABLES]
    m_lines += ["    Snapshot = Table.Combine({" + ",".join(tagged) + "})",
                'in __SnapshotForce("Snapshot.Final",()=>Table.Buffer(Snapshot))']
    snapshot_m = "\n".join(m_lines)
    snapshot = [f"table {SNAPSHOT}", "\tisHidden", ""]
    for name, dtype in union.items():
        snapshot += [f"\tcolumn {name}", f"\t\tdataType: {dtype}",
                     "\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}", ""]
    snapshot += [f"\tpartition {SNAPSHOT} = m", "\t\tmode: import", "\t\tsource =",
                 textwrap.indent(snapshot_m, "\t\t\t\t"), ""]
    for table in TABLES:
        prefix = prefixes[table]
        projected_table = PROJECTIONS[table] if additive_projections else table
        if additive_projections:
            prefix = f"table {projected_table}\n\tisHidden\n\n"
            for name, dtype in schemas[table]:
                prefix += (f"\tcolumn {name}\n\t\tdataType: {dtype}\n"
                           f"\t\tsummarizeBy: none\n\t\tsourceColumn: [{name}]\n\n")
        else:
            for name, _dtype in schemas[table]:
                exact = f"\t\tsourceColumn: {name}\n"
                if prefix.count(exact) != 1:
                    raise ValueError(f"Require exact original source column: {table}.{name}")
                prefix = prefix.replace(exact, f"\t\tsourceColumn: [{name}]\n")
        pairs = ",\n".join(f'    "{name}", \'{SNAPSHOT}\'[{name}]' for name, _ in schemas[table])
        dax = (f"SELECTCOLUMNS(\n    FILTER('{SNAPSHOT}', '{SNAPSHOT}'[SourceKind] = \"{table}\"),\n"
               + pairs + "\n)")
        # The native engine forbids changing an existing partition's source
        # type. Replace that partition with a new calculated partition name.
        texts[f"definition/tables/{projected_table}.tmdl"] = (prefix + f"\tpartition {projected_table}_SourceProjection = calculated\n"
            + "\t\tmode: import\n\t\tsource =\n" + textwrap.indent(dax, "\t\t\t\t") + "\n")
    model = texts["definition/model.tmdl"]
    if "ref cultureInfo" not in model:
        raise ValueError("Require an explicit insertion point after the original table references")
    refs = f"ref table {SNAPSHOT}\n"
    if additive_projections:
        refs += "".join(f"ref table {PROJECTIONS[t]}\n" for t in TABLES)
    texts["definition/model.tmdl"] = model.replace("ref cultureInfo", refs + "\nref cultureInfo", 1)
    changed = []
    for path, part in by_path.items():
        encoded = base64.b64encode(texts[path].encode()).decode()
        if encoded != part["payload"]:
            part["payload"] = encoded
            changed.append(path)
    new_path = f"definition/tables/{SNAPSHOT}.tmdl"
    parts.append({"path": new_path, "payload": base64.b64encode("\n".join(snapshot).encode()).decode(),
                  "payloadType": "InlineBase64"})
    changed.append(new_path)
    if additive_projections:
        for table in TABLES:
            path = f"definition/tables/{PROJECTIONS[table]}.tmdl"
            if path in by_path:
                raise ValueError("A fresh projection already exists; reconcile its identity")
            parts.append({"path": path, "payload": base64.b64encode(texts[path].encode()).decode(),
                          "payloadType": "InlineBase64"})
            changed.append(path)
    expected = {f"definition/tables/{PROJECTIONS[t] if additive_projections else t}.tmdl"
                for t in TABLES} | {"definition/model.tmdl", new_path}
    if set(changed) != expected:
        raise ValueError("Recovery must change only the five source partitions, model reference, and new snapshot")
    candidate = (json.dumps(result, indent=2) + "\n").encode()
    receipt = {"kind": "pubmed_single_evaluation_candidate_v1", "status": "PREPARED_NOT_DEPLOYED",
               "preimage": str(input_path.relative_to(ROOT)), "preimage_sha256": hashlib.sha256(raw).hexdigest(),
               "candidate": str(output_path.relative_to(ROOT)), "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
               "changed_parts": changed, "source_tables": list(TABLES), "snapshot_table": SNAPSHOT,
               "projection_mode": "additive_staging" if additive_projections else "replace_existing_partition",
               "logical_source_to_projection": PROJECTIONS if additive_projections else {t: t for t in TABLES},
               "retained_original_column_schemas_and_lineage": True, "unrelated_parts_unchanged": True,
               "rollback": "Restore the complete exact preimage definition; use the accepted source/archive evidence for reprocessing if required.",
               "commissioning": "One isolated transactional Full refresh of PubMedSourceSnapshot plus its five calculated output tables; native validation and complete source pages must reconcile before commit.",
               "limitations": ["Native M/DAX parsing and dependent refresh are unverified until bounded isolated commissioning.",
                               "This addresses independently repeated evaluation; the failed run exposed no per-query execution metrics."]}
    output_path.write_bytes(candidate)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preimage", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--additive-projections", action="store_true", default=True,
                        help="Add new staging projections; retain existing source tables unchanged")
    args = parser.parse_args()
    print(json.dumps(prepare(args.preimage, args.output, args.receipt,
                             additive_projections=args.additive_projections), indent=2))


if __name__ == "__main__":
    main()
