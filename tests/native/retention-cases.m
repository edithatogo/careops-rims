// Execute only in the isolated native test surface; never load fixtures into the live register.
let
    T=type table [Source=text,SourceID=text,FirstObservedAtUTC=datetimezone,LastObservedAtUTC=datetimezone,LastBatchID=text,MetadataJSON=text],
    N=type table [SourceID=text,MetadataJSON=text],
    Empty=#table(T,{}),
    A=#datetimezone(2026,1,1,0,0,0,0,0), B=#datetimezone(2026,1,2,0,0,0,0,0),
    Initial=fnRetainSourceObservations(Empty,#table(N,{{"fixture:1","{}"},{"fixture:2","{}"}}),"DORA","fixture:a",A,true),
    Rollover=fnRetainSourceObservations(Initial,#table(N,{{"fixture:2","{ ""updated"": true }"}}),"DORA","fixture:b",B,true),
    Replay=fnRetainSourceObservations(Rollover,#table(N,{{"fixture:2","{ ""updated"": true }"}}),"DORA","fixture:b",B,true),
    Zero=fnRetainSourceObservations(Rollover,#table(N,{}),"DORA","fixture:c",B,true),
    Failed=try Table.RowCount(fnRetainSourceObservations(Initial,#table(N,{}),"DORA","fixture:bad",B,false)),
    Duplicate=try Table.RowCount(fnRetainSourceObservations(Initial,#table(N,{{"fixture:2","{}"},{"fixture:2","{}"}}),"DORA","fixture:dup",B,true)),
    BadJSON=try Table.RowCount(fnRetainSourceObservations(Initial,#table(N,{{"fixture:2","broken"}}),"DORA","fixture:json",B,true)),
    OldTime=try Table.RowCount(fnRetainSourceObservations(Rollover,#table(N,{{"fixture:2","{}"}}),"DORA","fixture:old",A,true)),
    Results=#table(type table [Check=text,Passed=logical],{
        {"Rollover retains history",Table.RowCount(Rollover)=2},
        {"First observation immutable",List.AllTrue(List.Transform(Rollover[FirstObservedAtUTC],each _=A))},
        {"Absent record observation unchanged",Table.SelectRows(Rollover,each [SourceID]="fixture:1"){0}[LastObservedAtUTC]=A},
        {"Replay idempotent",Table.ToRecords(Replay)=Table.ToRecords(Rollover)},
        {"Successful empty feed retains history",Table.RowCount(Zero)=2},
        {"Failed batch rejected",Failed[HasError]},
        {"Duplicate IDs rejected",Duplicate[HasError]},
        {"Invalid JSON rejected",BadJSON[HasError]},
        {"Older observations rejected",OldTime[HasError]}})
in Results
