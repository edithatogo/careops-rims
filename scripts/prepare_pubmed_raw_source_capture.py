"""Extend the accepted public snapshot with raw response/schema chunk output.

This prepares a private candidate; it never deploys, refreshes or archives.
Existing typed projections and original shared functions remain unchanged.
Raw response bytes are captured from existing buffered request bindings, not
recreated from selected fields. Native request-count behaviour remains unproven.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import textwrap
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.prepare_pubmed_privacy_safe_snapshot import public_snapshot_m
from scripts.prepare_pubmed_single_evaluation import expression, partition, private

ROOT = Path(__file__).resolve().parents[1]
PART = "definition/tables/PubMedSourceSnapshot.tmdl"
RAW_KIND = "PubMedRawResponseChunks"
FIELDS = {
    "RawResponseIndex": "int64", "RawEndpoint": "string",
    "RawRequestJSON": "string", "RawAcquiredUTC": "string",
    "RawByteCount": "int64", "RawChunkIndex": "int64",
    "RawSchemaByteCount": "int64", "RawChunkCount": "int64",
    "RawPayloadBase64": "string", "RawSchemaBase64": "string",
    "RawProjectionError": "string", "RawHTTPStatus": "int64",
}


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Source structure drift at: " + old[:90])
    return text.replace(old, new, 1)


def instrument(texts: dict[str, str]) -> tuple[str, str, str, str]:
    shared = texts["definition/expressions.tmdl"]
    captured_time = 'if Binary.Length(Body)>=0 then DateTimeZone.ToText(DateTimeZone.UtcNow(),"yyyy-MM-ddTHH:mm:ss.fffzzz") else error "Raw response bytes unavailable"'
    json_fn = expression(shared, "fnNCBIJson")
    json_fn = replace_once(json_fn, "Body=Binary.Buffer(Body)]",
                           "Body=Binary.Buffer(Body),AcquiredUTC=" + captured_time + "]")
    json_fn = replace_once(json_fn, "in Result", '''in let Attempt=try Result,Decoded=try Json.Document(Final[Body]),
        Safe=if Attempt[HasError] then [] else Attempt[Value],
        Raw=Record.AddField(__RawEnvelope(endpoint,QueryParameters,Final[Body],Final[AcquiredUTC],if Decoded[HasError] then [DecodeFailure=true] else Decoded[Value]),"RawHTTPStatus",Final[Status])
        in Value.ReplaceMetadata(Safe,[RawResponse=Raw,ProjectionFailed=Attempt[HasError]])''')
    xml_fn = expression(shared, "fnPubMedXML")
    xml_fn = replace_once(xml_fn, "Body=Binary.Buffer(Body)]",
                          "Body=Binary.Buffer(Body),AcquiredUTC=" + captured_time + "]")
    import re
    schema = re.search(r'Result=Table.FromRecords\(Records,(type table \[[^\n]+?\])\),Returned=', xml_fn)
    if not schema:
        raise ValueError("Exact XML projected schema missing")
    xml_fn = replace_once(xml_fn, "in Reconciled", '''in let Attempt=try Table.Buffer(Reconciled),Decoded=try Xml.Document(Final[Body]),
        Safe=if Attempt[HasError] then #table(''' + schema[1] + ''',{}) else Attempt[Value],
        Raw=Record.AddField(__RawEnvelope("efetch.fcgi",Parameters,Final[Body],Final[AcquiredUTC],if Decoded[HasError] then [DecodeFailure=true] else Decoded[Value]),"RawHTTPStatus",Final[Status])
        in Value.ReplaceMetadata(Safe,[RawResponse=Raw,ProjectionFailed=Attempt[HasError]])''')
    harvest = expression(shared, "PubMedHarvest")
    harvest = replace_once(harvest, "Warnings=Warnings],",
                           "Warnings=Warnings,RawResponse=Value.Metadata(Payload)[RawResponse]],")
    # Catch each typed search/summary projection while keeping its independently
    # buffered response. The final typed gate still rejects any failed search.
    search_start = 'let\n            Payload = fnNCBIJson("esearch.fcgi", [term=definition[PubMedQuery], retmax="10000", sort="pub_date"]),'
    harvest = replace_once(harvest, search_start,
        'let\n            Payload = fnNCBIJson("esearch.fcgi", [term=definition[PubMedQuery], retmax="10000", sort="pub_date"]),\n'
        '            Projection=try (let Payload=Payload,')
    search_end = 'in [FacilityKey=definition[FacilityKey], IDs=Complete, SearchCount=Count, QueryTranslation=Translation, Warnings=Warnings,RawResponse=Value.Metadata(Payload)[RawResponse]],'
    harvest = replace_once(harvest, search_end,
        # M records are lazy: try(record) does not catch errors in their fields.
        # Force the search outputs inside the try before using IDs to acquire
        # dependent summary/XML responses. Keep the received error body as raw
        # evidence, while the existing typed-generation gate remains closed.
        'in let SearchRecord=[FacilityKey=definition[FacilityKey], IDs=Complete, SearchCount=Count, QueryTranslation=Translation, Warnings=Warnings],\n'
        '            Forced=List.Count(List.Buffer(SearchRecord[IDs]))>=0 and Value.Is(SearchRecord[SearchCount],type number) and Text.Length(SearchRecord[QueryTranslation])>=0 and Text.Length(SearchRecord[Warnings])>=0\n'
        '        in if Forced then SearchRecord else error "Typed search fields unavailable"),\n'
        '            Safe=if Projection[HasError] then [FacilityKey=definition[FacilityKey],IDs={},SearchCount=null,QueryTranslation="",Warnings="Typed source projection failed"] else Projection[Value]\n'
        '        in Record.Combine({Safe,[RawResponse=Value.Metadata(Payload)[RawResponse],ProjectionFailed=Projection[HasError]]}),')
    # The nested let must reference the outer response without recursive shadowing.
    harvest = replace_once(harvest, 'Projection=try (let Payload=Payload,', 'Projection=try (let CapturedPayload=Payload,')
    # Original search code uses Payload; an outer alias avoids changing it.
    harvest = replace_once(harvest, 'let CapturedPayload=Payload,', 'let __PayloadAlias=Payload,')
    harvest = replace_once(harvest, "in List.Buffer(Rows),",
                           "in let Attempt=try List.Buffer(Rows),Safe=if Attempt[HasError] then {} else Attempt[Value] in Value.ReplaceMetadata(Safe,[RawResponse=Value.Metadata(Payload)[RawResponse],ProjectionFailed=Attempt[HasError]]),")
    harvest = replace_once(harvest,
        "RawRows = List.Buffer(List.Accumulate(Batches, {}, (state,batch) => state & FetchBatch(batch))),",
        'SummaryBatches = List.Buffer(List.Accumulate(Batches, {}, (state,batch) => let R=FetchBatch(batch),N=List.Count(R) in if N>=0 then state & {R} else error "Invalid summary batch")),\n'
        '    RawRows = List.Buffer(List.Combine(SummaryBatches)),')
    harvest = replace_once(harvest, "SearchAudit=SearchAudit, IDs=AllIDs]",
        "SearchAudit=SearchAudit, IDs=AllIDs, RawResponses=List.Transform(SearchResults & {ScopeSearch},each [RawResponse]) & List.Transform(SummaryBatches,each Value.Metadata(_)[RawResponse])]")
    harvest = replace_once(harvest, 'VerifiedPublications = if ',
        'VerifiedPublications = if List.AnyTrue(List.Transform(SearchResults & {ScopeSearch},each [ProjectionFailed])) then error "Typed search projection rejected captured response" else if ')
    full = expression(shared, "PubMedFullMetadata")
    full = replace_once(full,
        'T=Table.Buffer(fnPubMedXML(batch)),N=Table.RowCount(T) in if N=List.Count(batch) then state&{T}',
        'T=fnPubMedXML(batch),Buffered=Table.Buffer(T),N=Table.RowCount(Buffered) in if N>=0 then state&{[Rows=Buffered,Raw=Value.Metadata(T)[RawResponse],Valid=N=List.Count(batch) and not Value.Metadata(T)[ProjectionFailed]]}')
    full = replace_once(full, "Table.Combine(Tables,Empty)", "Table.Combine(List.Transform(Tables,each [Rows]),Empty)")
    full = replace_once(full, "in Verified", 'in let Attempt=try Table.Buffer(Verified),Safe=if Attempt[HasError] or not List.AllTrue(List.Transform(Tables,each [Valid])) then #table(Empty,{}) else Attempt[Value] in Value.ReplaceMetadata(Safe,[RawResponses=List.Transform(Tables,each [Raw])])')
    return json_fn, xml_fn, harvest, full


def build_source(texts: dict[str, str]) -> str:
    json_fn, xml_fn, harvest, full = instrument(texts)
    source = public_snapshot_m(texts)
    # Scope the wrappers inside this one partition, preserving shared functions.
    envelope = (ROOT / "config/pubmed-raw-response-envelope.m").read_text()
    helpers = "\n".join(f"    {name}=({body})," for name, body in (
        ("__RawEnvelope", envelope), ("fnNCBIJson", json_fn), ("fnPubMedXML", xml_fn)))
    if not source.startswith("let\n"):
        raise ValueError("Snapshot outer let binding missing")
    source = "let\n" + helpers + "\n" + source[4:]
    from scripts.prepare_pubmed_single_evaluation import local_references, LOCAL_NAMES
    scope = {"FacilityDefinitions": "__SnapshotFacilities"}
    original_harvest = local_references("(" + expression(texts["definition/expressions.tmdl"], "PubMedHarvest") + ")", scope)
    raw_harvest = local_references("(" + harvest + ")", scope)
    source = replace_once(source, original_harvest.replace("\n", "\n    "), raw_harvest.replace("\n", "\n    "))
    source = replace_once(source, 'IDs=__SnapshotForce("Harvest.IDs",()=>List.Buffer(__SnapshotHarvestRaw[IDs]))]',
        'IDs=__SnapshotForce("Harvest.IDs",()=>List.Buffer(__SnapshotHarvestRaw[IDs])),RawResponses=__SnapshotHarvestRaw[RawResponses]]')
    old_full = "Table.Buffer((" + expression(texts["definition/expressions.tmdl"], "PubMedFullMetadata") + "))"
    # Preserve custom metadata explicitly across buffering; native engine metadata
    # propagation must not be inferred from Table.Buffer alone.
    old_full = local_references(old_full, LOCAL_NAMES)
    new_full = local_references('let T=(' + full + ') in Value.ReplaceMetadata(Table.Buffer(T),Value.Metadata(T))', LOCAL_NAMES)
    source = replace_once(source, old_full.replace("\n", "\n    "), new_full.replace("\n", "\n    "))
    final = 'in __SnapshotForce("Snapshot.Final",()=>Table.Buffer(Snapshot))'
    raw = '''    RawResponses=__SnapshotHarvestRaw[RawResponses] & Value.Metadata(__SnapshotPubMedFullMetadata)[RawResponses],
    RawRows=List.Combine(List.Transform(List.Positions(RawResponses),(r)=>let
        V=RawResponses{r},P=Binary.ToText(V[RawBinary],BinaryEncoding.Base64),
        S=Binary.ToText(Text.ToBinary(V[RawSchemaJSON],TextEncoding.Utf8),BinaryEncoding.Base64),
        N=List.Max({1,Number.RoundUp(Text.Length(P)/24000),Number.RoundUp(Text.Length(S)/24000)})
        in List.Transform({0..N-1},(i)=>[SourceKind="PubMedRawResponseChunks",RawResponseIndex=r,
            RawEndpoint=V[RawEndpoint],RawRequestJSON=V[RawRequestJSON],RawAcquiredUTC=V[RawAcquiredUTC],
            RawByteCount=V[RawByteCount],RawHTTPStatus=V[RawHTTPStatus],RawSchemaByteCount=Binary.Length(Text.ToBinary(V[RawSchemaJSON],TextEncoding.Utf8)),RawChunkIndex=i,RawChunkCount=N,
            RawPayloadBase64=Text.Range(P,List.Min({Text.Length(P),i*24000}),List.Min({24000,List.Max({0,Text.Length(P)-i*24000})})),
            RawSchemaBase64=Text.Range(S,List.Min({Text.Length(S),i*24000}),List.Min({24000,List.Max({0,Text.Length(S)-i*24000})}))]))),
    RawTable=Table.FromRecords(RawRows,type table [SourceKind=text,RawResponseIndex=Int64.Type,
        RawEndpoint=text,RawRequestJSON=text,RawAcquiredUTC=text,RawByteCount=Int64.Type,RawHTTPStatus=Int64.Type,
        RawSchemaByteCount=Int64.Type,RawChunkIndex=Int64.Type,RawChunkCount=Int64.Type,RawPayloadBase64=text,RawSchemaBase64=text])
    ,TypedAttempt=try Table.Buffer(Snapshot),
    TypedRows=if TypedAttempt[HasError] then #table(type table [SourceKind=text,RawProjectionError=text],{{"PubMedSourceProjectionFailure","Typed projection rejected captured raw response; this generation is not accepted"}}) else TypedAttempt[Value]
in __SnapshotForce("Snapshot.Final",()=>Table.Buffer(Table.SelectColumns(Table.Combine({TypedRows,RawTable}),__RawOutputColumns,MissingField.UseNull)))'''
    source = replace_once(source, final, raw)
    # Previous final binding had no trailing comma.
    source = replace_once(source, "})\n    RawResponses=", "}),\n    RawResponses=")
    return source


def build_candidate(original: dict, *, expected_part_count: int = 42) -> tuple[dict, dict]:
    candidate = copy.deepcopy(original)
    parts = candidate["definition"]["parts"]
    by_path = {p["path"]: p for p in parts}
    if type(expected_part_count) is not int or len(parts) != expected_part_count or len(by_path) != expected_part_count:
        raise ValueError("Require the explicitly pinned complete native definition")
    texts = {name: base64.b64decode(p["payload"], validate=True).decode() for name, p in by_path.items()}
    prefix, current_source = partition(texts[PART], "PubMedSourceSnapshot")
    if any("\tcolumn " + n + "\n" in prefix for n in FIELDS):
        raise ValueError("Raw capture already present; do not duplicate it")
    if current_source.strip() != public_snapshot_m(texts).strip():
        raise ValueError("Snapshot baseline drift; preserve native repairs before raw expansion")
    additions = []
    for name, dtype in FIELDS.items():
        tag = uuid.uuid5(uuid.NAMESPACE_URL, "rims/pubmed-raw-response/v1/" + name)
        additions.append(f"\tcolumn {name}\n\t\tdataType: {dtype}\n\t\tsummarizeBy: none\n\t\tsourceColumn: {name}\n\t\tlineageTag: {tag}\n")
    snapshot = prefix + "\n" + "\n".join(additions) + "\tpartition PubMedSourceSnapshot = m\n\t\tmode: import\n\t\tsource =\n" + textwrap.indent(build_source(texts), "\t\t\t\t") + "\n"
    import re
    original_columns = re.findall(r'^\tcolumn (\w+)\s*$', prefix, re.M)
    if len(original_columns) != len(re.findall(r'^\tcolumn ', prefix, re.M)) or "SourceKind" not in original_columns:
        raise ValueError("Complete explicit snapshot column schema required")
    column_list = '{' + ','.join('"' + n + '"' for n in original_columns + list(FIELDS)) + '}'
    snapshot = snapshot.replace('\t\t\t\tlet\n', '\t\t\t\tlet\n\t\t\t\t    __RawOutputColumns=' + column_list + ',\n', 1)
    by_path[PART]["payload"] = base64.b64encode(snapshot.encode()).decode()
    receipt = {"kind": "pubmed_raw_source_candidate_v1", "status": "PREPARED_NOT_DEPLOYED",
        "changed_parts": [PART], "preserved_parts": len(parts) - 1, "raw_source_kind": RAW_KIND,
        "endpoints": ["esearch.fcgi", "esummary.fcgi", "efetch.fcgi"],
        "source_scope": "Unchanged accepted facility and scope-review queries",
        "raw_encoding": "Exact returned binary encoded as Base64; 24000-character chunks",
        "schema_encoding": "Observed recursive JSON/XML shape as chunked Base64 UTF-8 JSON",
        "acquisition_time": "UTC response observation after bytes forced; not publication date or historical source generation",
        "additional_http_request_calls_added": False, "native_request_count_verified": False,
        "successful_typed_projection_policy_changed": False,
        "typed_failure_representation_changed": True,
        "credentials_in_request_descriptors": False, "native_acceptance": False,
        "failure_boundary": "Typed/decode rejection emits an explicit projection-failure row and raw chunks; no successful typed generation or archive commit is inferred. Transport failures before any response still fail capture."}
    return candidate, receipt


def reconstruct_responses(rows: list[dict]) -> list[dict]:
    """Read back raw snapshot chunks without accepting holes or mixed responses.

    Used by the native readback/next archive integration, not a hosted collector.
    Caller must separately reconcile response count/request set to its source run.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("Raw response readback is missing")
    groups: dict[int, list[dict]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("SourceKind") != RAW_KIND:
            raise ValueError("Expected explicit raw response source kind")
        for name in ("RawResponseIndex", "RawChunkIndex", "RawByteCount", "RawSchemaByteCount", "RawChunkCount"):
            value = row.get(name)
            if type(value) is not int or value < (1 if name == "RawChunkCount" else 0):
                raise ValueError("Invalid raw integer: " + name)
        groups.setdefault(row["RawResponseIndex"], []).append(row)
    if sorted(groups) != list(range(len(groups))):
        raise ValueError("Raw response indices contain gaps")
    result = []
    for index in sorted(groups):
        chunks = sorted(groups[index], key=lambda row: row["RawChunkIndex"])
        first = chunks[0]
        if [r["RawChunkIndex"] for r in chunks] != list(range(first["RawChunkCount"])):
            raise ValueError("Missing or duplicate raw chunks")
        metadata = ("RawEndpoint", "RawRequestJSON", "RawAcquiredUTC", "RawByteCount", "RawSchemaByteCount", "RawChunkCount", "RawHTTPStatus")
        if any(any(r.get(k) != first.get(k) for k in metadata) for r in chunks):
            raise ValueError("Mixed raw response metadata")
        if first["RawEndpoint"] not in {"esearch.fcgi", "esummary.fcgi", "efetch.fcgi"}:
            raise ValueError("Unqualified raw endpoint")
        if type(first.get("RawHTTPStatus")) is not int or not 100 <= first["RawHTTPStatus"] <= 599:
            raise ValueError("Raw response HTTP status is missing")
        instant = datetime.fromisoformat(first["RawAcquiredUTC"].replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset().total_seconds() != 0:
            raise ValueError("Raw acquisition time must be timezone-aware UTC")
        request = json.loads(first["RawRequestJSON"])
        allowed = {"db", "retmode", "tool", "term", "retmax", "retstart", "sort", "id", "usehistory"}
        if not isinstance(request, dict) or set(request) - allowed:
            raise ValueError("Raw request descriptor contains unqualified fields")
        decoded = {}
        for column, size in (("RawPayloadBase64", "RawByteCount"), ("RawSchemaBase64", "RawSchemaByteCount")):
            if any(not isinstance(r.get(column), str) or len(r[column]) > 24000 for r in chunks):
                raise ValueError("Invalid or oversized raw chunk")
            body = base64.b64decode("".join(r[column] for r in chunks), validate=True)
            if len(body) != first[size]:
                raise ValueError("Raw byte count mismatch")
            decoded[column] = body
        schema = json.loads(decoded["RawSchemaBase64"].decode("utf-8"))
        if not isinstance(schema, dict) or not isinstance(schema.get("Kind"), str):
            raise ValueError("Raw observed schema is missing")
        result.append({"endpoint": first["RawEndpoint"], "request": request,
            "acquired_at_utc": first["RawAcquiredUTC"], "http_status": first["RawHTTPStatus"],
            "body": decoded["RawPayloadBase64"], "schema": schema})
    return result


def prepare(preimage: Path, output: Path, receipt_path: Path) -> dict:
    preimage, output, receipt_path = map(private, (preimage, output, receipt_path))
    if output.exists() or receipt_path.exists() or output == receipt_path:
        raise ValueError("Use distinct new outputs; never overwrite input or prior evidence")
    raw = preimage.read_bytes()
    candidate, receipt = build_candidate(json.loads(raw))
    encoded = (json.dumps(candidate, indent=2) + "\n").encode()
    receipt.update(preimage=str(preimage), preimage_sha256=hashlib.sha256(raw).hexdigest(),
        candidate=str(output), candidate_sha256=hashlib.sha256(encoded).hexdigest())
    output.write_bytes(encoded)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preimage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.preimage, args.output, args.receipt), indent=2))


if __name__ == "__main__":
    main()
