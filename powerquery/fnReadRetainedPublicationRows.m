// Read summary rows belonging to each observation's latest accepted batch.
// History must come from fnReadCommittedHistory over the same scoped Files.
// Complete long text is restored from retained metadata before reporting.
(Files as table, History as table, SourceName as text) as table =>
let
    Definition=if SourceName="PubMed" then [Table="PubMedPublications",Key="PMID"] else if SourceName="DORA" then [Table="DoraPublications",Key="DORAKey"] else error "Unsupported retained source",
    Selected=Table.SelectRows(History,each [Source]=SourceName),
    Read=(Name as text) as any=>let Matches=Table.SelectRows(Files,each [Name]=Name)
        in if Table.RowCount(Matches)<>1 then error "Missing or duplicate retained file" else Json.Document(Binary.Buffer(Matches{0}[Content])),
    Batches=List.Distinct(Selected[LastBatchID]),
    Tables=List.Transform(Batches,(Batch)=>let
        Manifest=Read("commit-"&Batch&".json"),
        Sources=List.Select(Manifest[Sources],each [Source]=SourceName),
        S=if Manifest[Status]="committed" and Manifest[BatchID]=Batch and List.Count(Sources)=1 then Sources{0} else error "Invalid retained summary manifest",
        Count=S[PublicationPageCount],
        Valid=S[PublicationTable]=Definition[Table] and Count>0 and Number.RoundDown(Count)=Count,
        Pages=if Valid then List.Transform(List.Numbers(0,Count),(i)=>let
            Rows=Read("uncommitted-"&Batch&"-"&Definition[Table]&"-"&Text.From(i,"en-US")&".json")
            in if Value.Is(Rows,type list) and not List.IsEmpty(Rows) then Table.FromRecords(Rows) else error "Invalid retained summary page") else error "Invalid retained summary inventory",
        Raw=Table.Combine(Pages),
        Normal=Table.TransformColumnNames(Raw,each if Text.StartsWith(_,"[") and Text.EndsWith(_, "]") then Text.Middle(_,1,Text.Length(_)-2) else _),
        Keys=Table.Column(Normal,Definition[Key]),
        Complete=List.Count(Keys)=S[ExpectedRecords] and List.Count(List.Distinct(Keys))=List.Count(Keys) and List.Sort(Keys)=List.Sort(S[ExpectedKeys]),
        Wanted=Table.SelectRows(Selected,each [LastBatchID]=Batch)[SourceID],
        Latest=if Complete then Table.SelectRows(Normal,each List.Contains(Wanted,Record.Field(_,Definition[Key]))) else error "Retained summary keys do not reconcile"
        in Latest),
    Combined=if List.IsEmpty(Tables) then #table({Definition[Key]}, {}) else Table.Combine(Tables),
    Actual=Table.Column(Combined,Definition[Key]),
    Verified=if List.Sort(Actual)=List.Sort(Selected[SourceID]) and List.Count(List.Distinct(Actual))=List.Count(Actual) then Combined else error "Latest retained summary keys do not reconcile"
in Verified
