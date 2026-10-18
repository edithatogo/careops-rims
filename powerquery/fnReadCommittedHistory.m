// Files must be scoped by the caller to the approved source-archive folder.
// A commit is written last, after all page, key, metadata and generation gates.
(Files as table) as table =>
let
    StoredType=type table [Source=text,SourceID=text,FirstObservedAtUTC=datetimezone,LastObservedAtUTC=datetimezone,LastBatchID=text,MetadataJSON=text],
    ReadFile=(Name as text) as binary =>
        let Matches=Table.SelectRows(Files,each [Name]=Name)
        in if Table.RowCount(Matches)=1 then Binary.Buffer(Matches{0}[Content]) else error "Missing or duplicate committed file",
    CommitFiles=Table.SelectRows(Files,each Text.StartsWith([Name],"commit-") and Text.EndsWith([Name],".json")),
    Manifests=List.Transform(Table.ToRecords(CommitFiles),(f)=>
        let M=Json.Document(f[Content]),
            Valid=M[SchemaVersion]=1 and M[Status]="committed" and
                f[Name]="commit-" & M[BatchID] & ".json" and
                M[Validation][Keysets]=true and M[Validation][Metadata]=true and M[Validation][RefreshGeneration]=true,
            At=DateTimeZone.FromText(M[ObservedAtUTC])
        in if Valid then [BatchID=M[BatchID],At=At,Sources=M[Sources]] else error "Invalid commit manifest"),
    Ordered=List.Sort(Manifests,(a,b)=>if a[At]<b[At] then -1 else if a[At]>b[At] then 1 else Value.Compare(a[BatchID],b[BatchID])),
    Unique=List.Count(List.Distinct(List.Transform(Ordered,each [BatchID])))=List.Count(Ordered),
    Result=List.Accumulate(if Unique then Ordered else error "Duplicate batch identity",#table(StoredType,{}),(History,Batch)=>
        List.Accumulate(Batch[Sources],History,(Prior,S)=>
            let
                Count=S[PageCount],
                ValidCount=Value.Is(Count,type number) and Count>0 and Number.RoundDown(Count)=Count,
                Pages=if ValidCount then List.Transform(List.Numbers(0,Count),(i)=>
                    let Name="uncommitted-" & Batch[BatchID] & "-" & S[ChunkTable] & "-" & Text.From(i,"en-US") & ".json",
                        Rows=Json.Document(ReadFile(Name))
                    in if Value.Is(Rows,type list) and List.Count(Rows)>0 then Table.FromRecords(Rows) else error "Invalid committed page") else error "Invalid page count",
                Raw=Table.Combine(Pages),
                Normal=Table.TransformColumnNames(Raw,each if Text.StartsWith(_,"[") and Text.EndsWith(_, "]") then Text.Middle(_,1,Text.Length(_)-2) else _),
                Incoming=fnReconstructMetadata(Normal,S[KeyColumn]),
                Keys=Incoming[SourceID], Expected=S[ExpectedKeys],
                Complete=List.Count(Keys)=S[ExpectedRecords] and List.Count(List.Distinct(Expected))=List.Count(Expected) and
                    List.Sort(Keys)=List.Sort(Expected),
                Retained=fnRetainSourceObservations(Prior,Incoming,S[Source],Batch[BatchID],Batch[At],Complete)
            in Retained))
in
    if List.IsEmpty(Ordered) then error "No accepted history commit; preserve previous model state" else Result
