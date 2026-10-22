"""Compile native saved PubMed projections as supported query-scoped VARs.

No I/O or native writes are performed by query generation. Physical Fresh
tables are not read: complete outputs derive from the ready source snapshot
and accepted original imports. Successful queries do not imply table storage.
"""
from __future__ import annotations

import base64
import hashlib
import re

try:
    from build_native_commit_package import page_query, configured_search_profile
except ModuleNotFoundError:
    from scripts.build_native_commit_package import page_query, configured_search_profile

TABLES = {"PubMedPublications": "FreshPubMedPublications",
          "PubMedMetadataChunks": "FreshPubMedMetadataChunks",
          "PubMedAuthorEvidence": "FreshPubMedAuthorEvidence",
          "SearchAudit": "FreshSearchAudit",
          "PubMedIngestionAudit": "FreshPubMedIngestionAudit"}
VARS = {"PubMedPublications": "ProjectedPublications", "PubMedMetadataChunks": "ProjectedMetadata",
        "PubMedAuthorEvidence": "ProjectedAuthors", "SearchAudit": "ProjectedSearch"}


def projection_proof(definition: dict, definition_sha256: str, *, expected_part_count: int = 42) -> dict:
    parts = definition.get("definition", {}).get("parts", [])
    if type(expected_part_count) is not int or expected_part_count < len(TABLES) or len(parts) != expected_part_count:
        raise ValueError("Require the explicitly pinned native definition part count")
    texts = {p["path"]: base64.b64decode(p["payload"]).decode() for p in parts}
    tables = {}
    for logical, physical in TABLES.items():
        text = texts[f"definition/tables/{physical}.tmdl"]
        marker = f"\tpartition {physical}_SourceProjection = calculated\n\t\tmode: import\n\t\tsource ="
        if text.count(marker) != 1:
            raise ValueError("Native calculated projection identity differs")
        expression = "\n".join(line[4:] if line.startswith("\t\t\t\t") else line
                               for line in text.split(marker)[1].strip("\n").splitlines()).strip()
        columns = re.findall(r"^\tcolumn (\w+)$", text, re.M)
        tables[physical] = {"logical_table": logical, "expression": expression,
                            "expression_sha256": hashlib.sha256(expression.encode()).hexdigest(),
                            "columns": columns}
    return {"kind": "saved_native_pubmed_var_projection_v1", "compiler": "saved_projection_var_v1",
            "definition_sha256": definition_sha256, "tables": tables}


def _proof(proof: dict) -> dict:
    if (proof.get("kind") != "saved_native_pubmed_var_projection_v1"
            or proof.get("compiler") != "saved_projection_var_v1"
            or set(proof.get("tables", {})) != set(TABLES.values())):
        raise ValueError("Exact five saved projections are required")
    for physical, entry in proof["tables"].items():
        if (entry.get("logical_table") != next(k for k, v in TABLES.items() if v == physical)
                or hashlib.sha256(entry["expression"].encode()).hexdigest() != entry["expression_sha256"]):
            raise ValueError("Projection identity/hash differs")
    return proof


def _declarations(proof: dict, logicals: tuple[str, ...]) -> str:
    proof = _proof(proof)
    return "\n".join(f"VAR {VARS[t]} = (\n{proof['tables'][TABLES[t]]['expression']}\n)" for t in logicals)


def projection_page_query(proof: dict, table: str, cursor=None) -> str:
    if table in ("SearchAudit", "PubMedIngestionAudit"):
        raise ValueError("Audit tables use the complete bounded validation query")
    query = page_query(table, cursor)
    declaration = _declarations(proof, (table,))
    # Column references inside row iterators are unqualified for VAR tables;
    # all public-snapshot and original-import references in declarations remain native.
    tail = query.split("EVALUATE\n", 1)[1]
    tail = re.sub(r"\b" + table + r"\[", "[", tail)
    tail = re.sub(r"\b" + table + r"\b", VARS[table], tail)
    return "EVALUATE\n" + declaration + "\n" + tail


def projection_bounded_query(proof: dict, table: str, search_profile: dict,
                             after: str = "") -> str:
    """Return complete bounded search/audit rows and their final empty cursor."""
    escaped = after.replace('"', '""')
    if table == "SearchAudit":
        columns = _proof(proof)["tables"][TABLES[table]]["columns"]
        pairs = ",".join('"' + name + '",[' + name + ']' for name in columns)
        return ("EVALUATE\n" + _declarations(proof, (table,))
                + f'\nRETURN SELECTCOLUMNS(FILTER(ProjectedSearch,[FacilityKey]>"{escaped}"),{pairs})'
                + "\nORDER BY [FacilityKey]")
    if table == "PubMedIngestionAudit":
        query = projection_validation_query(proof, search_profile)
        prefix = query.rsplit("RETURN ROW(", 1)[0]
        return (prefix + f'RETURN SELECTCOLUMNS(FILTER(AuditRows,[Check]>"{escaped}"),'
                '"Check",[Check],"Observed",[Observed],"Passed",[Passed])\nORDER BY [Check]')
    raise ValueError("Only search and ingestion audit tables use bounded queries")


def projection_validation_query(proof: dict, search_profile: dict) -> str:
    if search_profile != configured_search_profile():
        raise ValueError("Configured facility search scope differs")
    declarations = _declarations(proof, tuple(VARS))
    keys = sorted(search_profile["ActiveFacilityKeys"] + search_profile["ReviewOnlyFacilityKeys"])
    expected = ",".join('"' + k.replace('"', '""') + '"' for k in keys)
    version = search_profile["QueryVersion"].replace('"', '""')
    # All grouping is over supported table VAR expressions using explicit
    # key filters. CALCULATE/VALUES never pretend a VAR is a physical table.
    return f'''EVALUATE
{declarations}
VAR PKeys = DISTINCT(SELECTCOLUMNS(ProjectedPublications,"PMID",[PMID]))
VAR MKeys = DISTINCT(SELECTCOLUMNS(ProjectedMetadata,"PMID",[PMID]))
VAR AKeys = DISTINCT(SELECTCOLUMNS(ProjectedAuthors,"PMID",[PMID]))
VAR MetadataByKey = ADDCOLUMNS(MKeys,
 "ActualCharacters", VAR K=[PMID] RETURN SUMX(FILTER(ProjectedMetadata,[PMID]=K),LEN([MetadataChunk])),
 "ExpectedCharacters", VAR K=[PMID] RETURN MAXX(FILTER(ProjectedMetadata,[PMID]=K),[MetadataCharacters]),
 "CharacterDeclarations", VAR K=[PMID] RETURN COUNTROWS(DISTINCT(SELECTCOLUMNS(FILTER(ProjectedMetadata,[PMID]=K),"V",[MetadataCharacters]))),
 "ActualChunks", VAR K=[PMID] RETURN COUNTROWS(FILTER(ProjectedMetadata,[PMID]=K)),
 "ExpectedChunks", VAR K=[PMID] RETURN MAXX(FILTER(ProjectedMetadata,[PMID]=K),[ChunkCount]),
 "CountDeclarations", VAR K=[PMID] RETURN COUNTROWS(DISTINCT(SELECTCOLUMNS(FILTER(ProjectedMetadata,[PMID]=K),"V",[ChunkCount]))),
 "DistinctIndices", VAR K=[PMID] RETURN COUNTROWS(DISTINCT(SELECTCOLUMNS(FILTER(ProjectedMetadata,[PMID]=K),"V",[ChunkIndex]))),
 "FirstIndex", VAR K=[PMID] RETURN MINX(FILTER(ProjectedMetadata,[PMID]=K),[ChunkIndex]),
 "LastIndex", VAR K=[PMID] RETURN MAXX(FILTER(ProjectedMetadata,[PMID]=K),[ChunkIndex]))
VAR MetadataStructureFailures=COALESCE(COUNTROWS(FILTER(MetadataByKey,[ActualCharacters]<>[ExpectedCharacters] || [CharacterDeclarations]<>1 || [ActualChunks]<>[ExpectedChunks] || [CountDeclarations]<>1 || [DistinctIndices]<>[ActualChunks] || [FirstIndex]<>0 || [LastIndex]<>[ActualChunks]-1)),0)
VAR MissingMetadataKeys=COALESCE(COUNTROWS(EXCEPT(PKeys,MKeys)),0)
VAR UnexpectedMetadataKeys=COALESCE(COUNTROWS(EXCEPT(MKeys,PKeys)),0)
VAR MetadataEncodingFailures=COALESCE(COUNTROWS(FILTER(ProjectedMetadata,[Encoding]<>"UTF8-HEX")),0)
VAR AuthorEvidenceByPublication=ADDCOLUMNS(ProjectedPublications,
 "ExpectedAuthorCount",[AuthorCount],
 "ObservedAuthorCount", VAR K=[PMID] RETURN COUNTROWS(DISTINCT(SELECTCOLUMNS(FILTER(ProjectedAuthors,[PMID]=K),"I",[AuthorIndex]))),
 "SummaryAuthors",[Authors],
 "EvidenceAuthors", VAR K=[PMID] VAR Indices=DISTINCT(SELECTCOLUMNS(FILTER(ProjectedAuthors,[PMID]=K),"I",[AuthorIndex])) RETURN CONCATENATEX(Indices,VAR I=[I] RETURN MAXX(FILTER(ProjectedAuthors,[PMID]=K && [AuthorIndex]=I),[AuthorName]),"; ",[I],ASC))
VAR AuthorEvidenceCountFailures=COALESCE(COUNTROWS(FILTER(AuthorEvidenceByPublication,[ExpectedAuthorCount]<>[ObservedAuthorCount])),0)
VAR AuthorEvidenceNameFailures=COALESCE(COUNTROWS(FILTER(AuthorEvidenceByPublication,[SummaryAuthors]<>[EvidenceAuthors])),0)
VAR SearchKeys=DISTINCT(SELECTCOLUMNS(ProjectedSearch,"FacilityKey",[FacilityKey]))
VAR SearchExpected=SELECTCOLUMNS({{{expected}}},"FacilityKey",[Value])
VAR SearchDuplicates=COUNTROWS(ProjectedSearch)-COUNTROWS(SearchKeys)
VAR SearchMissing=COALESCE(COUNTROWS(EXCEPT(SearchExpected,SearchKeys)),0)
VAR SearchUnexpected=COALESCE(COUNTROWS(EXCEPT(SearchKeys,SearchExpected)),0)
VAR SearchVersionFailures=COALESCE(COUNTROWS(FILTER(ProjectedSearch,ISBLANK([QueryVersion]) || [QueryVersion]<>"{version}")),0)
VAR SearchCountFailures=COALESCE(COUNTROWS(FILTER(ProjectedSearch,ISBLANK([SearchCount]) || [SearchCount]<0)),0)
VAR SearchTranslationFailures=COALESCE(COUNTROWS(FILTER(ProjectedSearch,ISBLANK([QueryTranslation]) || LEN(TRIM([QueryTranslation]))=0)),0)
VAR CurrentAudit=SELECTCOLUMNS(FILTER(PubMedSourceSnapshot,PubMedSourceSnapshot[SourceKind]="PubMedIngestionAudit"),"Check",PubMedSourceSnapshot[Check],"Observed",PubMedSourceSnapshot[Observed],"Passed",PubMedSourceSnapshot[Passed])
VAR CurrentKeys=SELECTCOLUMNS(FILTER(PubMedSourceSnapshot,PubMedSourceSnapshot[SourceKind]="PubMedPublications"),"PMID",PubMedSourceSnapshot[PMID])
VAR UsesOlder=COUNTROWS(EXCEPT(SELECTCOLUMNS(PubMedPublications,"PMID",PubMedPublications[PMID]),CurrentKeys))>0
VAR SourceAuditFailures=COALESCE(COUNTROWS(FILTER(CurrentAudit,[Passed]<>TRUE())),0)+IF(UsesOlder,COALESCE(COUNTROWS(FILTER(PubMedIngestionAudit,PubMedIngestionAudit[Passed]<>TRUE())),0),0)
VAR SourceAuditNulls=COALESCE(COUNTROWS(FILTER(CurrentAudit,ISBLANK([Passed]))),0)+IF(UsesOlder,COALESCE(COUNTROWS(FILTER(PubMedIngestionAudit,ISBLANK(PubMedIngestionAudit[Passed]))),0),0)
VAR SourceAuditShape=IF(COUNTROWS(CurrentAudit)=9 && (NOT UsesOlder || COUNTROWS(PubMedIngestionAudit)=9),0,1)
VAR ReconstructionFailures=MAXX(FILTER(CurrentAudit,[Check]="Metadata reconstruction failures"),[Observed])+IF(UsesOlder,MAXX(FILTER(PubMedIngestionAudit,PubMedIngestionAudit[Check]="Metadata reconstruction failures"),PubMedIngestionAudit[Observed]),0)+MetadataStructureFailures
VAR FullCount=MAXX(FILTER(CurrentAudit,[Check]="Full metadata publications"),[Observed])+COUNTROWS(EXCEPT(DISTINCT(SELECTCOLUMNS(PubMedMetadataChunks,"PMID",PubMedMetadataChunks[PMID])),CurrentKeys))
VAR DateFailures=COALESCE(COUNTROWS(FILTER(ProjectedPublications,([PublicationDatePrecision] IN {{"year","unknown","range","outside-model-range"}} && NOT ISBLANK([PublicationDate])) || ([PublicationDatePrecision] IN {{"day","month"}} && ISBLANK([PublicationDate])))),0)
VAR BlankTitles=COALESCE(COUNTROWS(FILTER(ProjectedPublications,ISBLANK([Title]) || LEN(TRIM([Title]))=0)),0)
VAR OversizeChunks=COALESCE(COUNTROWS(FILTER(ProjectedMetadata,LEN([MetadataChunk])>20000)),0)
VAR AuditRows=UNION(
 ROW("Check","Full metadata publications","Observed",FullCount,"Passed",FullCount=COUNTROWS(PKeys)),
 ROW("Check","Distinct full-metadata PMIDs","Observed",COUNTROWS(MKeys),"Passed",COUNTROWS(MKeys)=COUNTROWS(PKeys)),
 ROW("Check","Missing metadata PMIDs","Observed",MissingMetadataKeys,"Passed",MissingMetadataKeys=0),
 ROW("Check","Unexpected metadata PMIDs","Observed",UnexpectedMetadataKeys,"Passed",UnexpectedMetadataKeys=0),
 ROW("Check","Metadata reconstruction failures","Observed",ReconstructionFailures,"Passed",ReconstructionFailures=0),
 ROW("Check","Metadata chunk rows","Observed",COUNTROWS(ProjectedMetadata),"Passed",OversizeChunks=0),
 ROW("Check","Author evidence count failures","Observed",AuthorEvidenceCountFailures,"Passed",AuthorEvidenceCountFailures=0),
 ROW("Check","Date precision failures","Observed",DateFailures,"Passed",DateFailures=0),
 ROW("Check","Blank full titles","Observed",BlankTitles,"Passed",BlankTitles=0))
RETURN ROW(
 "CurrentRows",COUNTROWS(ProjectedPublications),"VerifiedPubMedRecords",COUNTROWS(FILTER(ProjectedPublications,NOT ISBLANK([PMID]))),"DistinctCurrentKeys",COUNTROWS(PKeys),
 "CurrentKeysJSON","[" & CONCATENATEX(PKeys,"""" & [PMID] & """",",",[PMID],ASC) & "]",
 "MetadataRows",COUNTROWS(ProjectedMetadata),"DistinctMetadataKeys",COUNTROWS(MKeys),"MetadataKeysJSON","[" & CONCATENATEX(MKeys,"""" & [PMID] & """",",",[PMID],ASC) & "]",
 "MissingMetadataKeys",MissingMetadataKeys,"UnexpectedMetadataKeys",UnexpectedMetadataKeys,"MetadataStructureFailures",MetadataStructureFailures,"MetadataEncodingFailures",MetadataEncodingFailures,"MetadataCharacters",SUMX(MetadataByKey,[ExpectedCharacters]),"ModelRefreshUTC",MAXX(ProjectedPublications,[RefreshedAtUTC]),
 "AuthorEvidenceRows",COUNTROWS(ProjectedAuthors),"DistinctAuthorEvidenceKeys",COUNTROWS(DISTINCT(SELECTCOLUMNS(ProjectedAuthors,"P",[PMID],"I",[AuthorIndex],"F",[AffiliationIndex]))),"OrphanAuthorEvidencePMIDs",COALESCE(COUNTROWS(EXCEPT(AKeys,PKeys)),0),"InvalidAuthorEvidenceIndices",COALESCE(COUNTROWS(FILTER(ProjectedAuthors,[AuthorIndex]<1 || [AffiliationIndex]<1)),0),"AuthorEvidenceCountFailures",AuthorEvidenceCountFailures,"AuthorEvidenceNameFailures",AuthorEvidenceNameFailures,
 "SearchAuditRows",COUNTROWS(ProjectedSearch),"SearchAuditKeyCount",COUNTROWS(SearchKeys),"SearchAuditKeysJSON","[" & CONCATENATEX(SearchKeys,"""" & [FacilityKey] & """",",",[FacilityKey],ASC) & "]","SearchAuditDuplicateKeyRows",SearchDuplicates,"SearchAuditMissingKeys",SearchMissing,"SearchAuditUnexpectedKeys",SearchUnexpected,"SearchAuditVersionFailures",SearchVersionFailures,"SearchAuditInvalidCountRows",SearchCountFailures,"SearchAuditTranslationFailures",SearchTranslationFailures,"SearchAuditWarningRows",COALESCE(COUNTROWS(FILTER(ProjectedSearch,NOT ISBLANK([Warnings]) && [Warnings]<>"")),0),"SearchAuditWarnings",CONCATENATEX(FILTER(ProjectedSearch,NOT ISBLANK([Warnings]) && [Warnings]<>""),[FacilityKey] & ": " & [Warnings],UNICHAR(10),[FacilityKey],ASC),"SearchAuditFailures",SearchDuplicates+SearchMissing+SearchUnexpected+SearchVersionFailures+SearchCountFailures+SearchTranslationFailures,
 "AuditRows",COUNTROWS(AuditRows),"AuditCheckCount",COUNTROWS(DISTINCT(SELECTCOLUMNS(AuditRows,"Check",[Check]))),"AuditCheckNamesJSON","[" & CONCATENATEX(AuditRows,"""" & [Check] & """",",",[Check],ASC) & "]","AuditFailureNamesJSON","[" & CONCATENATEX(FILTER(AuditRows,[Passed]<>TRUE()),"""" & [Check] & """",",",[Check],ASC) & "]","AuditNullCount",SourceAuditNulls,"AuditFailures",COALESCE(COUNTROWS(FILTER(AuditRows,[Passed]<>TRUE())),0)+SourceAuditFailures+SourceAuditShape)'''
