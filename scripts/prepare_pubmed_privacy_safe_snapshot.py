"""Prepare an NCBI-only snapshot and audits over its retained model projections.

Private retained files never enter the M harvest. The three child/publication
projections combine the public snapshot with accepted imported rows in DAX.
This module makes private artifacts only; it does not change native objects.
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

from prepare_pubmed_single_evaluation import (
    TABLES, LOCAL_NAMES, expression, local_references, partition, private,
)

CHECKS = (
    "Full metadata publications", "Distinct full-metadata PMIDs",
    "Missing metadata PMIDs", "Unexpected metadata PMIDs",
    "Metadata reconstruction failures", "Metadata chunk rows",
    "Author evidence count failures", "Date precision failures", "Blank full titles",
)


def public_snapshot_m(texts: dict[str, str]) -> str:
    expressions = texts["definition/expressions.tmdl"]
    facility_table = texts["definition/tables/FacilityDefinitions.tmdl"]
    facility_marker = "\tpartition FacilityDefinitions = m\n\t\tmode: import\n\t\tsource ="
    if facility_table.count(facility_marker) != 1:
        raise ValueError("Require the exact native facility partition")
    facility = textwrap.dedent(facility_table.split(facility_marker)[1].split("\n\tannotation ", 1)[0]).strip()
    if not facility.startswith("#table(") or not facility.endswith("})"):
        raise ValueError("Facility definitions must be the accepted literal table, not another source")
    current = expression(expressions, "CurrentPubMedPublications")
    metadata = partition(texts["definition/tables/PubMedMetadataChunks.tmdl"], "PubMedMetadataChunks")[1]
    author = partition(texts["definition/tables/PubMedAuthorEvidence.tmdl"], "PubMedAuthorEvidence")[1]
    audit = partition(texts["definition/tables/PubMedIngestionAudit.tmdl"], "PubMedIngestionAudit")[1]
    # Preserve the native row reconstruction code; eliminate only its retained
    # union inputs. Complete source/key checks remain mandatory in the snapshot.
    def current_full_prefix() -> str:
        return ('let\n CurrentFull=Table.Buffer(PubMedFullMetadata),\n'
                ' ExpectedKeys=List.Buffer(CurrentPubMedPublications[PMID]),\n'
                ' FullKeys=List.Buffer(CurrentFull[PMID]),\n'
                ' VerifiedUnion=if List.Count(FullKeys)=List.Count(List.Distinct(FullKeys)) '
                'and List.Count(ExpectedKeys)=List.Count(FullKeys) '
                'and List.IsEmpty(List.Difference(ExpectedKeys,FullKeys)) '
                'and List.IsEmpty(List.Difference(FullKeys,ExpectedKeys)) '
                'then CurrentFull else error "Current summary/full metadata keys do not reconcile",\n ')
    for name, body in (("metadata", metadata), ("author", author)):
        if body.count("Rows=List.Combine(") != 1:
            raise ValueError(f"Unexpected native {name} row projection")
    metadata = current_full_prefix() + metadata[metadata.index("Rows=List.Combine("):]
    author = current_full_prefix() + author[author.index("Rows=List.Combine("):]
    marker = "Full=Table.Buffer(VerifiedUnion)"
    if audit.count(marker) != 1:
        raise ValueError("Unexpected native nine-check audit source")
    audit = current_full_prefix() + audit[audit.index(marker):]
    bindings = [
        ("__SnapshotFacilities", f"Table.Buffer(({facility}))"),
        ("__SnapshotHarvestRaw", "(" + expression(expressions, "PubMedHarvest") + ")"),
        ("PubMedHarvest", 'if Value.Is(__SnapshotHarvestRaw,type record) and '
         'Record.HasFields(__SnapshotHarvestRaw,{"Publications","Matches","SearchAudit","IDs"}) '
         'then [Publications=__SnapshotForce("Harvest.Publications",()=>Table.Buffer(__SnapshotHarvestRaw[Publications])),'
         'Matches=__SnapshotForce("Harvest.Matches",()=>Table.Buffer(__SnapshotHarvestRaw[Matches])),'
         'SearchAudit=__SnapshotForce("Harvest.SearchAudit",()=>Table.Buffer(__SnapshotHarvestRaw[SearchAudit])),'
         'IDs=__SnapshotForce("Harvest.IDs",()=>List.Buffer(__SnapshotHarvestRaw[IDs]))] '
         'else error Error.Record("PubMedSnapshotHarvestShape","Complete harvest record required",null)'),
        ("PubMedFullMetadata", "Table.Buffer((" + expression(expressions, "PubMedFullMetadata") + "))"),
        ("CurrentPubMedPublications", "Table.Buffer((" + current + "))"),
        ("PubMedPublications", "Table.Buffer(CurrentPubMedPublications)"),
        ("PubMedMetadataChunks", "Table.Buffer((" + metadata + "))"),
        ("PubMedAuthorEvidence", "Table.Buffer((" + author + "))"),
        ("SearchAudit", "Table.Buffer(PubMedHarvest[SearchAudit])"),
        ("PubMedIngestionAudit", "Table.Buffer((" + audit + "))"),
    ]
    lines = ["let", '    __SnapshotForce = (stage as text, action as function) as any => '
             'let Attempt=try action() in if Attempt[HasError] then '
             'error Error.Record("PubMedSnapshotStage",stage & ": " & '
             'Text.From(Record.FieldOrDefault(Attempt[Error],"Message","source evaluation failed")),'
             '[Stage=stage,OriginalError=Attempt[Error]]) else Attempt[Value],']
    for name, body in bindings:
        if name == "__SnapshotHarvestRaw":
            body = local_references(body, {"FacilityDefinitions": "__SnapshotFacilities"})
        elif name != "PubMedHarvest":
            body = local_references(body, LOCAL_NAMES)
        local = LOCAL_NAMES.get(name, name)
        wrapped = f'__SnapshotForce("{name}",()=>({body}))'
        lines.append("    " + local + " = " + wrapped.replace("\n", "\n    ") + ",")
    tagged = [f'Table.AddColumn({LOCAL_NAMES[t]},"SourceKind",each "{t}",type text)' for t in TABLES]
    lines += ["    Snapshot=Table.Combine({" + ",".join(tagged) + "})",
              'in __SnapshotForce("Snapshot.Final",()=>Table.Buffer(Snapshot))']
    result = "\n".join(lines)
    forbidden = ("RetainedArchiveFiles", "RetainedSourceObservations", "RetainedPubMed",
                 "SharePoint.", "OneDrive", "fnReadCommittedHistory", "fnReadRetainedPublicationRows")
    if any(word in result for word in forbidden):
        raise ValueError("A retained/private M source remains in the public snapshot")
    return result


def combined_audit_dax() -> str:
    expected = ",".join('{"' + check + '"}' for check in CHECKS)
    return f'''VAR CurrentKeys = SELECTCOLUMNS(FILTER('PubMedSourceSnapshot', 'PubMedSourceSnapshot'[SourceKind] = "PubMedPublications"), "PMID", 'PubMedSourceSnapshot'[PMID])
VAR OlderKept = EXCEPT(SELECTCOLUMNS('PubMedPublications', "PMID", 'PubMedPublications'[PMID]), CurrentKeys)
VAR UsesOlder = COUNTROWS(OlderKept) > 0
VAR CurrentAudit = SELECTCOLUMNS(FILTER('PubMedSourceSnapshot', 'PubMedSourceSnapshot'[SourceKind] = "PubMedIngestionAudit"), "Check", 'PubMedSourceSnapshot'[Check], "Observed", 'PubMedSourceSnapshot'[Observed], "Passed", 'PubMedSourceSnapshot'[Passed])
VAR ExpectedChecks = DATATABLE("Check", STRING, {{{expected}}})
VAR CurrentCheckNames = SELECTCOLUMNS(CurrentAudit, "Check", [Check])
VAR OlderCheckNames = SELECTCOLUMNS('PubMedIngestionAudit', "Check", 'PubMedIngestionAudit'[Check])
VAR CurrentAuditValid = COUNTROWS(CurrentAudit) = 9 && COUNTROWS(EXCEPT(ExpectedChecks, CurrentCheckNames)) = 0 && COUNTROWS(EXCEPT(CurrentCheckNames, ExpectedChecks)) = 0 && COUNTROWS(FILTER(CurrentAudit, [Passed] <> TRUE())) = 0
VAR OlderAuditValid = COUNTROWS('PubMedIngestionAudit') = 9 && COUNTROWS(EXCEPT(ExpectedChecks, OlderCheckNames)) = 0 && COUNTROWS(EXCEPT(OlderCheckNames, ExpectedChecks)) = 0 && COUNTROWS(FILTER('PubMedIngestionAudit', 'PubMedIngestionAudit'[Passed] <> TRUE())) = 0
VAR SourceEvidenceGate = IF(CurrentAuditValid && (NOT UsesOlder || OlderAuditValid), 1, ERROR("Current and retained source reconstruction audits must be complete and passing"))
VAR PublicationKeys = SELECTCOLUMNS('FreshPubMedPublications', "PMID", 'FreshPubMedPublications'[PMID])
VAR MetadataKeys = SELECTCOLUMNS(SUMMARIZE('FreshPubMedMetadataChunks', 'FreshPubMedMetadataChunks'[PMID]), "PMID", 'FreshPubMedMetadataChunks'[PMID])
VAR CurrentFullCount = MAXX(FILTER(CurrentAudit, [Check] = "Full metadata publications"), [Observed])
VAR RetainedMetadataKeys = EXCEPT(SELECTCOLUMNS(SUMMARIZE('PubMedMetadataChunks', 'PubMedMetadataChunks'[PMID]), "PMID", 'PubMedMetadataChunks'[PMID]), CurrentKeys)
VAR FullCount = CurrentFullCount + COUNTROWS(RetainedMetadataKeys)
VAR MetadataKeyCount = COUNTROWS(MetadataKeys)
VAR MissingCount = COUNTROWS(EXCEPT(PublicationKeys, MetadataKeys))
VAR UnexpectedCount = COUNTROWS(EXCEPT(MetadataKeys, PublicationKeys))
VAR ChunkGroups = ADDCOLUMNS(SUMMARIZE('FreshPubMedMetadataChunks', 'FreshPubMedMetadataChunks'[PMID]),
    "Rows", CALCULATE(COUNTROWS('FreshPubMedMetadataChunks')),
    "Indices", CALCULATE(DISTINCTCOUNT('FreshPubMedMetadataChunks'[ChunkIndex])),
    "MinIndex", CALCULATE(MIN('FreshPubMedMetadataChunks'[ChunkIndex])),
    "MaxIndex", CALCULATE(MAX('FreshPubMedMetadataChunks'[ChunkIndex])),
    "MinDeclared", CALCULATE(MIN('FreshPubMedMetadataChunks'[ChunkCount])),
    "MaxDeclared", CALCULATE(MAX('FreshPubMedMetadataChunks'[ChunkCount])),
    "MinCharacters", CALCULATE(MIN('FreshPubMedMetadataChunks'[MetadataCharacters])),
    "MaxCharacters", CALCULATE(MAX('FreshPubMedMetadataChunks'[MetadataCharacters])),
    "Characters", CALCULATE(SUMX('FreshPubMedMetadataChunks', LEN('FreshPubMedMetadataChunks'[MetadataChunk]))))
VAR ChunkStructureFailures = COUNTROWS(FILTER(ChunkGroups, [Rows] <> [Indices] || [MinIndex] <> 0 || [MaxIndex] <> [Rows] - 1 || [MinDeclared] <> [Rows] || [MaxDeclared] <> [Rows] || [MinCharacters] <> [MaxCharacters] || [Characters] <> [MaxCharacters]))
VAR CurrentReconstructionFailures = MAXX(FILTER(CurrentAudit, [Check] = "Metadata reconstruction failures"), [Observed])
VAR OlderReconstructionFailures = IF(UsesOlder, MAXX(FILTER('PubMedIngestionAudit', 'PubMedIngestionAudit'[Check] = "Metadata reconstruction failures"), 'PubMedIngestionAudit'[Observed]), 0)
VAR ReconstructionFailures = CurrentReconstructionFailures + OlderReconstructionFailures + ChunkStructureFailures
VAR ChunkRows = COUNTROWS('FreshPubMedMetadataChunks')
VAR OversizeChunks = COUNTROWS(FILTER('FreshPubMedMetadataChunks', LEN('FreshPubMedMetadataChunks'[MetadataChunk]) > 20000))
VAR AuthorFailures = SUMX('FreshPubMedPublications', VAR Pmid = 'FreshPubMedPublications'[PMID] VAR Expected = 'FreshPubMedPublications'[AuthorCount] VAR Actual = COUNTROWS(SUMMARIZE(FILTER('FreshPubMedAuthorEvidence', 'FreshPubMedAuthorEvidence'[PMID] = Pmid), 'FreshPubMedAuthorEvidence'[AuthorIndex])) RETURN IF(Actual = Expected, 0, 1))
VAR DateFailures = COUNTROWS(FILTER('FreshPubMedPublications', ('FreshPubMedPublications'[PublicationDatePrecision] IN {{"year","unknown","range","outside-model-range"}} && NOT ISBLANK('FreshPubMedPublications'[PublicationDate])) || ('FreshPubMedPublications'[PublicationDatePrecision] IN {{"day","month"}} && ISBLANK('FreshPubMedPublications'[PublicationDate]))))
VAR BlankTitles = COUNTROWS(FILTER('FreshPubMedPublications', ISBLANK('FreshPubMedPublications'[Title]) || LEN(TRIM('FreshPubMedPublications'[Title])) = 0))
VAR AuditRows = UNION(
    ROW("Check","Full metadata publications","Observed",FullCount,"Passed",FullCount = COUNTROWS(PublicationKeys)),
    ROW("Check","Distinct full-metadata PMIDs","Observed",MetadataKeyCount,"Passed",MetadataKeyCount = COUNTROWS(PublicationKeys)),
    ROW("Check","Missing metadata PMIDs","Observed",MissingCount,"Passed",MissingCount = 0),
    ROW("Check","Unexpected metadata PMIDs","Observed",UnexpectedCount,"Passed",UnexpectedCount = 0),
    ROW("Check","Metadata reconstruction failures","Observed",ReconstructionFailures,"Passed",ReconstructionFailures = 0),
    ROW("Check","Metadata chunk rows","Observed",ChunkRows,"Passed",OversizeChunks = 0),
    ROW("Check","Author evidence count failures","Observed",AuthorFailures,"Passed",AuthorFailures = 0),
    ROW("Check","Date precision failures","Observed",DateFailures,"Passed",DateFailures = 0),
    ROW("Check","Blank full titles","Observed",BlankTitles,"Passed",BlankTitles = 0))
RETURN FILTER(AuditRows, SourceEvidenceGate = 1)'''


def prepare(preimage_path: Path, projection_path: Path, output: Path, receipt_path: Path) -> dict:
    preimage_path, projection_path, output, receipt_path = map(private, (preimage_path, projection_path, output, receipt_path))
    if output.exists() or receipt_path.exists():
        raise ValueError("Review existing artifacts before replacement")
    raw = preimage_path.read_bytes()
    original = json.loads(raw)
    candidate = copy.deepcopy(original)
    parts = candidate["definition"]["parts"]
    if len(parts) != 42:
        raise ValueError("Require the exact existing 42-part staging definition")
    by_path = {p["path"]: p for p in parts}
    texts = {name: base64.b64decode(part["payload"]).decode() for name, part in by_path.items()}
    snapshot_path = "definition/tables/PubMedSourceSnapshot.tmdl"
    prefix = partition(texts[snapshot_path], "PubMedSourceSnapshot")[0]
    snapshot = prefix + "\tpartition PubMedSourceSnapshot = m\n\t\tmode: import\n\t\tsource =\n" + textwrap.indent(public_snapshot_m(texts), "\t\t\t\t") + "\n"
    replacements = {snapshot_path: snapshot}
    projection = json.loads(projection_path.read_text())
    required_projection = {f"definition/tables/Fresh{t}.tmdl" for t in TABLES[:3]}
    if {p["path"] for p in projection["parts"]} != required_projection or len(projection["parts"]) != 3:
        raise ValueError("Require exactly the reviewed three projection parts")
    replacements.update({p["path"]: base64.b64decode(p["payload"]).decode() for p in projection["parts"]})
    audit_path = "definition/tables/FreshPubMedIngestionAudit.tmdl"
    audit = texts[audit_path]
    marker = "\t\tsource ="
    if audit.count(marker) != 1:
        raise ValueError("Require one existing calculated audit partition")
    replacements[audit_path] = audit.split(marker)[0] + marker + "\n" + textwrap.indent(combined_audit_dax(), "\t\t\t\t") + "\n"
    for path, text in replacements.items():
        by_path[path]["payload"] = base64.b64encode(text.encode()).decode()
    encoded = (json.dumps(candidate, indent=2) + "\n").encode()
    receipt = {"kind":"pubmed_privacy_safe_snapshot_candidate_v1", "status":"PREPARED_NOT_DEPLOYED",
               "preimage":str(preimage_path), "preimage_sha256":hashlib.sha256(raw).hexdigest(),
               "candidate":str(output), "candidate_sha256":hashlib.sha256(encoded).hexdigest(),
               "changed_parts":sorted(replacements), "source_privacy":"NCBI only; literal facility definitions; retained inputs combined only in DAX over existing imports",
               "source_scope":"Complete current facility/review searches and full metadata; older imported keys retained by current-PMID anti-join",
               "audit_proof":"All nine combined checks recalculated; current reconstruction proof and complete passing prior audit evidence required when older rows are retained; combined chunks/keys/authors/dates/titles rechecked",
               "processing":"One DataOnly snapshot import; inspect materialization; Calculate the exact five Fresh tables without source refetch; correlate both native operation receipts before package",
               "native_save_refresh_acceptance":False}
    output.write_bytes(encoded)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preimage", required=True, type=Path)
    parser.add_argument("--projection-parts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.preimage, args.projection_parts, args.output, args.receipt), indent=2))


if __name__ == "__main__":
    main()
