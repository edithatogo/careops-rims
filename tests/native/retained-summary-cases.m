// Native isolated fixtures for latest committed summary selection.
// History rows stand in for the separately tested committed metadata reader.
let
    At=#datetimezone(2026,1,1,0,0,0,0,0),
    HistoryType=type table [Source=text,SourceID=text,LastBatchID=text],
    History=#table(HistoryType,{{"PubMed","101","a"},{"PubMed","102","b"}}),
    Manifest=(Batch as text,Keys as list) as binary=>Json.FromValue([
        SchemaVersion=1,Status="committed",BatchID=Batch,ObservedAtUTC=DateTimeZone.ToText(At),
        Validation=[Keysets=true,Metadata=true,RefreshGeneration=true],
        Sources={[Source="PubMed",PublicationTable="PubMedPublications",PublicationPageCount=1,
            ExpectedRecords=List.Count(Keys),ExpectedKeys=Keys]}]),
    Files=#table(type table [Name=text,Content=binary],{
        {"commit-a.json",Manifest("a",{"101","102"})},
        {"uncommitted-a-PubMedPublications-0.json",Json.FromValue({[PMID="101",Title="Retained older row"],[PMID="102",Title="Old title"]})},
        {"commit-b.json",Manifest("b",{"102"})},
        {"uncommitted-b-PubMedPublications-0.json",Json.FromValue({[PMID="102",Title="Updated title"]})},
        {"uncommitted-c-PubMedPublications-0.json",Json.FromValue({[PMID="103",Title="Interrupted row"]})}
    }),
    Result=fnReadRetainedPublicationRows(Files,History,"PubMed"),
    Replay=fnReadRetainedPublicationRows(Files,History,"PubMed"),
    Missing=try Table.RowCount(fnReadRetainedPublicationRows(Table.SelectRows(Files,each [Name]<>"uncommitted-b-PubMedPublications-0.json"),History,"PubMed")),
    WrongKeys=Table.TransformRows(Files,each if [Name]="uncommitted-b-PubMedPublications-0.json" then [Name=[Name],Content=Json.FromValue({[PMID="999",Title="Wrong identity"]})] else _),
    Wrong=try Table.RowCount(fnReadRetainedPublicationRows(Table.FromRecords(WrongKeys),History,"PubMed")),
    Duplicate=try Table.RowCount(fnReadRetainedPublicationRows(Table.Combine({Files,Table.SelectRows(Files,each [Name]="commit-b.json")}),History,"PubMed")),
    Tests=#table(type table [Check=text,Passed=logical],{
        {"Smaller committed batch retains absent summary",List.Sort(Result[PMID])={"101","102"}},
        {"Latest accepted summary replaces prior version",Table.SelectRows(Result,each [PMID]="102"){0}[Title]="Updated title"},
        {"Interrupted summary batch stays invisible",not List.Contains(Result[PMID],"103")},
        {"Summary replay is stable",Table.ToRecords(Result)=Table.ToRecords(Replay)},
        {"Missing committed summary page rejected",Missing[HasError]},
        {"Wrong summary key set rejected",Wrong[HasError]},
        {"Duplicate committed file rejected",Duplicate[HasError]}
    })
in Tests
