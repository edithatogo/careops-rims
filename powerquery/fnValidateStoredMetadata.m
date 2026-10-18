// Read only: validates staged files without promoting a commit or changing history.
(Files as table, BatchID as text) as table =>
let
    ReadPages=(TableName as text) as table =>
        let
            Prefix="uncommitted-" & BatchID & "-" & TableName & "-",
            Selected=Table.SelectRows(Files,each Text.StartsWith([Name],Prefix) and Text.EndsWith([Name],".json")),
            Indexed=Table.AddColumn(Selected,"Page",each Number.FromText(Text.BetweenDelimiters([Name],Prefix,".json"),"en-US"),Int64.Type),
            Sorted=Table.Sort(Indexed,{{"Page",Order.Ascending}}),
            Complete=Table.RowCount(Sorted)>0 and Sorted[Page]=List.Numbers(0,Table.RowCount(Sorted)),
            Pages=if Complete then List.Transform(Table.ToRecords(Sorted),each
                let Rows=Json.Document([Content])
                in if Value.Is(Rows,type list) and not List.IsEmpty(Rows) then Table.FromRecords(Rows) else error "Empty or invalid staged page") else error "Missing or duplicate staged page",
            Combined=Table.Combine(Pages),
            Normal=Table.TransformColumnNames(Combined,each if Text.StartsWith(_,"[") and Text.EndsWith(_, "]") then Text.Middle(_,1,Text.Length(_)-2) else _)
        in Normal,
    Sources={[Source="PubMed",Table="PubMedPublications",Chunks="PubMedMetadataChunks",Key="PMID"],
        [Source="DORA",Table="DoraPublications",Chunks="DoraMetadataChunks",Key="DORAKey"]},
    PayloadIdentity=(Source as text,Payload as list) as text =>
        if Source="DORA" then
            let URIs=List.Distinct(List.RemoveNulls(List.Transform(List.Select(Payload,each Record.FieldOrDefault(_,"Field",null)="dc.identifier.uri"),each [Value])))
            in if List.Count(URIs)=1 and Value.Is(URIs{0},type text) then "DORA:" & Text.Replace(URIs{0},"http://","https://") else error "Missing or ambiguous retained DORA identity"
        else
            let Citations=List.Select(Payload,each Record.FieldOrDefault(_,"Name",null)="MedlineCitation"),
                Citation=if List.Count(Citations)=1 then Citations{0}[Value] else error "Missing or ambiguous retained Medline citation",
                IDs=List.Select(Citation,each Record.FieldOrDefault(_,"Name",null)="PMID")
            in if List.Count(IDs)=1 then Text.From(IDs{0}[Value],"en-US") else error "Missing or ambiguous retained PMID",
    Results=List.Transform(Sources,(S)=>
        let
            Expected=Table.Column(ReadPages(S[Table]),S[Key]),
            Reconstructed=Table.Buffer(fnReconstructMetadata(ReadPages(S[Chunks]),S[Key])),
            Keys=Reconstructed[SourceID],
            Exact=List.Count(Expected)=List.Count(List.Distinct(Expected)) and List.Sort(Expected)=List.Sort(Keys),
            Lengths=List.Transform(Reconstructed[MetadataJSON],each Text.Length(_)),
            Structured=List.AllTrue(List.Transform(Reconstructed[MetadataJSON],each
                let M=Json.Document(_)
                in Value.Is(M,type list) and not List.IsEmpty(M) and
                    List.AllTrue(List.Transform(M,(r)=>Value.Is(r,type record) and
                        Record.HasFields(r,if S[Source]="DORA" then {"Field","Value"} else {"Name","Value"}))))),
            Identities=if Structured then List.AllTrue(List.Transform(Table.ToRecords(Reconstructed),each
                PayloadIdentity(S[Source],Json.Document([MetadataJSON]))=[SourceID])) else false,
            Result=if Exact and Structured and Identities then [Source=S[Source],ExpectedRecords=List.Count(Expected),
                ReconstructedRecords=List.Count(Keys),MetadataCharacters=List.Sum(Lengths),KeysMatch=true,MetadataValid=true,PayloadIdentitiesMatch=true]
                else error "Stored metadata identity set or source structure mismatch"
        in Result),
    Output=Table.FromRecords(Results,type table [Source=text,ExpectedRecords=number,ReconstructedRecords=number,MetadataCharacters=number,KeysMatch=logical,MetadataValid=logical,PayloadIdentitiesMatch=logical])
in Output
