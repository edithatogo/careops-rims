import base64
import copy
import json
import unittest

from scripts.prepare_pubmed_raw_source_capture import (
    FIELDS, PART, RAW_KIND, build_candidate, reconstruct_responses, public_snapshot_m,
)


def definition():
    # Synthetic native-shape inputs; no tenant identifiers or publication rows.
    expressions = {
        "fnNCBIJson": '(endpoint as text, parameters as record) as record => let Body=Text.ToBinary("{}"),QueryParameters=parameters,Fetch=()=>[Body=Binary.Buffer(Body)],Final=Fetch(),Parsed=Json.Document(Final[Body]),Result=Parsed in Result',
        "fnPubMedXML": '(ids as list) as table => let Body=Text.ToBinary("<root/>"),Parameters=[id=Text.Combine(ids,",")],Fetch=()=>[Body=Binary.Buffer(Body)],Final=Fetch(),XML=Xml.Document(Final[Body]),Records={},Result=Table.FromRecords(Records,type table [PMID=text]),Returned=Result[PMID],Reconciled=Result in Reconciled',
        "PubMedHarvest": '''let
    SearchOne=(definition as record)=>let
            Payload = fnNCBIJson("esearch.fcgi", [term=definition[PubMedQuery], retmax="10000", sort="pub_date"]),
            Warnings="",Complete={},Count=0,Translation=""
        in [FacilityKey=definition[FacilityKey], IDs=Complete, SearchCount=Count, QueryTranslation=Translation, Warnings=Warnings],
    SearchResults={},ScopeSearch=SearchOne(),AllIDs={},Batches={},
    FetchBatch=(ids)=>let Payload=fnNCBIJson("esummary.fcgi",[]),Rows={} in List.Buffer(Rows),
    RawRows = List.Buffer(List.Accumulate(Batches, {}, (state,batch) => state & FetchBatch(batch))),
    VerifiedPublications = if List.Count(AllIDs)=0 then #table(type table [PMID=text],{}) else error "fixture",Matches=VerifiedPublications,SearchAudit=VerifiedPublications
in [Publications=VerifiedPublications, Matches=Matches, SearchAudit=SearchAudit, IDs=AllIDs]''',
        "PubMedFullMetadata": '''let IDs={},Batches={},
 Tables=List.Accumulate(Batches,{},(state,batch)=>let T=Table.Buffer(fnPubMedXML(batch)),N=Table.RowCount(T) in if N=List.Count(batch) then state&{T} else error "incomplete"),
 Empty=type table [PMID=text],Result=Table.Combine(Tables,Empty),Verified=Result
in Verified''',
        "CurrentPubMedPublications": "PubMedHarvest[Publications]",
    }
    shared = "\n".join("expression " + name + " =\n\t\t" + body.replace("\n", "\n\t\t") for name, body in expressions.items()) + "\n"
    tables = {
        "FacilityDefinitions": '#table(type table [FacilityKey=text,Active=logical,PubMedQuery=text],{})',
        "PubMedMetadataChunks": 'let Full=Table.Buffer(VerifiedUnion),Rows=List.Combine({{}}) in #table(type table [PMID=text],{})',
        "PubMedAuthorEvidence": 'let Full=Table.Buffer(VerifiedUnion),Rows=List.Combine({{}}) in #table(type table [PMID=text],{})',
        "PubMedIngestionAudit": 'let Full=Table.Buffer(VerifiedUnion) in #table(type table [Check=text],{})',
        "PubMedSourceSnapshot": '#table(type table [SourceKind=text,PMID=text],{})',
    }
    def part(path, text):
        return {"path": path, "payloadType": "InlineBase64", "payload": base64.b64encode(text.encode()).decode()}
    parts = [part("definition/expressions.tmdl", shared)]
    for name, source in tables.items():
        prefix = f"table {name}\n\tcolumn PMID\n\t\tdataType: string\n"
        parts.append(part(f"definition/tables/{name}.tmdl", prefix + f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n" + "\t\t\t\t" + source))
    for i in range(42 - len(parts)):
        parts.append(part(f"definition/tables/Sentinel{i}.tmdl", f"table Sentinel{i}\n"))
    texts = {p["path"]: base64.b64decode(p["payload"]).decode() for p in parts}
    snapshot = next(p for p in parts if p["path"] == PART)
    prefix = "table PubMedSourceSnapshot\n\tcolumn SourceKind\n\t\tdataType: string\n\tcolumn PMID\n\t\tdataType: string\n\tpartition PubMedSourceSnapshot = m\n\t\tmode: import\n\t\tsource =\n"
    import textwrap
    snapshot["payload"] = base64.b64encode((prefix + textwrap.indent(public_snapshot_m(texts), "\t\t\t\t")).encode()).decode()
    return {"definition": {"format": "TMDL", "parts": parts}}


def chunks(body=b'{"newField":{"nested":[null,"unknown"]}}', schema=None):
    schema = schema or {"Kind": "record", "Fields": [{"Name": "newField", "Schema": {"Kind": "record"}}]}
    schema_bytes = json.dumps(schema).encode()
    payload64, schema64 = base64.b64encode(body).decode(), base64.b64encode(schema_bytes).decode()
    count = max(1, (len(payload64) + 23999) // 24000, (len(schema64) + 23999) // 24000)
    return [{"SourceKind": RAW_KIND, "RawResponseIndex": 0, "RawEndpoint": "efetch.fcgi",
        "RawRequestJSON": '{"db":"pubmed","id":"1"}', "RawAcquiredUTC": "2026-10-13T01:00:00+00:00",
        "RawByteCount": len(body), "RawSchemaByteCount": len(schema_bytes), "RawHTTPStatus": 200, "RawChunkIndex": i,
        "RawChunkCount": count, "RawPayloadBase64": payload64[i*24000:(i+1)*24000],
        "RawSchemaBase64": schema64[i*24000:(i+1)*24000]} for i in range(count)]


class RawSourceCaptureTests(unittest.TestCase):
    def test_explicit_raw_table_schema_preserves_every_response_carrier_field(self):
        import re
        candidate, _ = build_candidate(definition())
        snapshot = next(p for p in candidate["definition"]["parts"] if p["path"] == PART)
        source = base64.b64decode(snapshot["payload"]).decode()
        schema = re.search(r"RawTable=Table.FromRecords\(RawRows,type table \[([^]]+)\]", source)[1]
        carried = set(re.findall(r"(\w+)\s*=", schema))
        self.assertEqual(carried, {"SourceKind", *FIELDS} - {"RawProjectionError"})

    def test_missing_readback_is_not_an_accepted_empty_collection(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            reconstruct_responses([])

    def test_changes_one_part_and_preserves_all_existing_fields_and_shared_functions(self):
        before = definition()
        pristine = copy.deepcopy(before)
        after, receipt = build_candidate(before)
        self.assertEqual(before, pristine)
        changes = [a["path"] for a, b in zip(after["definition"]["parts"], before["definition"]["parts"]) if a != b]
        self.assertEqual(changes, [PART])
        text = base64.b64decode(next(p["payload"] for p in after["definition"]["parts"] if p["path"] == PART)).decode()
        for field in FIELDS:
            self.assertIn("\tcolumn " + field + "\n", text)
        self.assertIn("\tcolumn PMID\n\t\tdataType: string", text)
        self.assertEqual(receipt["preserved_parts"], 41)
        self.assertFalse(receipt["native_acceptance"])

    def test_repeat_preparation_is_identical(self):
        self.assertEqual(build_candidate(definition()), build_candidate(definition()))

    def test_transport_drift_fails_before_a_candidate(self):
        before = definition()
        part = before["definition"]["parts"][0]
        text = base64.b64decode(part["payload"]).decode().replace("Body=Binary.Buffer(Body)]", "Body=Body]")
        part["payload"] = base64.b64encode(text.encode()).decode()
        with self.assertRaisesRegex(ValueError, "structure drift|baseline drift"):
            build_candidate(before)

    def test_native_source_repairs_are_not_overwritten(self):
        before = definition()
        part = next(p for p in before["definition"]["parts"] if p["path"] == PART)
        text = base64.b64decode(part["payload"]).decode().replace('"Snapshot.Final"', '"NativeRepair.Final"')
        part["payload"] = base64.b64encode(text.encode()).decode()
        with self.assertRaisesRegex(ValueError, "baseline drift"):
            build_candidate(before)

    def test_existing_raw_columns_are_not_duplicated(self):
        candidate, _ = build_candidate(definition())
        with self.assertRaisesRegex(ValueError, "already present"):
            build_candidate(candidate)

    def test_unknown_nested_fields_unicode_and_xml_bytes_round_trip_without_projection(self):
        bodies = [json.dumps({"unmapped": [None, {"new": "café"}]}).encode(), b'<root future="yes"><unknown>\x00</unknown><!--retained--></root>', b"binary\xff\xfe"]
        for body in bodies:
            result = reconstruct_responses(chunks(body))
            self.assertEqual(result[0]["body"], body)
            self.assertEqual(result[0]["schema"]["Fields"][0]["Name"], "newField")

    def test_long_response_and_long_schema_round_trip(self):
        body = b"x" * 100000
        schema = {"Kind": "record", "Fields": [{"Name": "unknown" + str(i), "Schema": {"Kind": "null"}} for i in range(2000)]}
        result = reconstruct_responses(chunks(body, schema))[0]
        self.assertEqual(result["body"], body)
        self.assertEqual(result["schema"], schema)

    def test_missing_and_duplicate_chunks_fail(self):
        rows = chunks(b"x" * 40000)
        for bad in [rows[:-1], rows + [rows[0]]]:
            with self.assertRaisesRegex(ValueError, "Missing or duplicate"):
                reconstruct_responses(bad)

    def test_mixed_generation_metadata_fails(self):
        rows = chunks(b"x" * 40000)
        rows[-1]["RawAcquiredUTC"] = "2026-10-13T01:01:00+00:00"
        with self.assertRaisesRegex(ValueError, "Mixed"):
            reconstruct_responses(rows)

    def test_boolean_counts_and_byte_loss_fail(self):
        for field, value in [("RawChunkCount", True), ("RawByteCount", 2)]:
            rows = chunks()
            rows[0][field] = value
            with self.assertRaises(ValueError):
                reconstruct_responses(rows)

    def test_timezone_and_request_credentials_fail(self):
        for field, value in [("RawAcquiredUTC", "2026-10-13T01:00:00"), ("RawRequestJSON", '{"api_key":"never-copy"}')]:
            rows = chunks()
            rows[0][field] = value
            with self.assertRaises(ValueError):
                reconstruct_responses(rows)


if __name__ == "__main__":
    unittest.main()
