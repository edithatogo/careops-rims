// Durable storage owns Previous; Incoming is one validated source batch.
// Review decisions remain in a separate versioned ledger and are never overwritten here.
(Previous as table, Incoming as table, Source as text, BatchID as text,
 ObservedAtUTC as datetimezone, BatchComplete as logical) as table =>
let
    StoredType = type table [Source=text, SourceID=text, FirstObservedAtUTC=datetimezone,
        LastObservedAtUTC=datetimezone, LastBatchID=text, MetadataJSON=text],
    StoredColumns = {"Source","SourceID","FirstObservedAtUTC","LastObservedAtUTC","LastBatchID","MetadataJSON"},
    IncomingColumns = {"SourceID","MetadataJSON"},
    Require = (condition as logical, message as text, value as any) as any =>
        if condition then value else error Error.Record("RetentionValidation",message,null),
    Old = Require(List.Sort(Table.ColumnNames(Previous))=List.Sort(StoredColumns),
        "Stored observation schema mismatch", Previous),
    New = Require(List.Sort(Table.ColumnNames(Incoming))=List.Sort(IncomingColumns),
        "Incoming observation schema mismatch", Incoming),
    TextValid = (v as any) as logical => if not Value.Is(v,type text) then false else Text.Trim(v)<>"",
    JSONValid = (v as any) as logical => if not TextValid(v) then false else not (try Json.Document(v))[HasError],
    OldValid = List.AllTrue(List.Transform(Table.ToRecords(Old), each
        TextValid([Source]) and TextValid([SourceID]) and TextValid([LastBatchID]) and JSONValid([MetadataJSON]) and
        Value.Is([FirstObservedAtUTC],type datetimezone) and Value.Is([LastObservedAtUTC],type datetimezone) and
        [FirstObservedAtUTC]<=[LastObservedAtUTC])),
    NewValid = List.AllTrue(List.Transform(Table.ToRecords(New), each TextValid([SourceID]) and JSONValid([MetadataJSON]))),
    UniqueOld = Table.RowCount(Table.Distinct(Old,{"Source","SourceID"}))=Table.RowCount(Old),
    UniqueNew = Table.RowCount(Table.Distinct(New,{"SourceID"}))=Table.RowCount(New),
    Current = Table.SelectRows(Old,each [Source]=Source),
    TimeValid = List.AllTrue(List.Transform(Current[LastObservedAtUTC],each _<=ObservedAtUTC)),
    BatchValid = BatchComplete and TextValid(Source) and TextValid(BatchID) and OldValid and NewValid and
        UniqueOld and UniqueNew and TimeValid,
    Checked = Require(BatchValid,
        "Incomplete batch, invalid metadata, duplicate source IDs or out-of-order observation",New),
    Joined = Table.NestedJoin(Checked,{"SourceID"},Current,{"SourceID"},"Prior",JoinKind.LeftOuter),
    Updated = List.Transform(Table.ToRecords(Joined),(r)=>[
        Source=Source,SourceID=r[SourceID],
        FirstObservedAtUTC=if Table.IsEmpty(r[Prior]) then ObservedAtUTC else r[Prior]{0}[FirstObservedAtUTC],
        LastObservedAtUTC=ObservedAtUTC,LastBatchID=BatchID,MetadataJSON=r[MetadataJSON]]),
    // Anti-join retains every missing record, including records absent from a smaller feed.
    Missing = Table.RemoveColumns(Table.NestedJoin(Current,{"SourceID"},Checked,{"SourceID"},"Incoming",JoinKind.LeftAnti),{"Incoming"}),
    OtherSources = Table.SelectRows(Old,each [Source]<>Source),
    Result = Table.Combine({OtherSources,Missing,Table.FromRecords(Updated,StoredType)},StoredColumns),
    Typed = Value.ReplaceType(Result,StoredType)
in
    Require(BatchValid,"Retention batch rejected; preserve the previous committed store",Typed)
