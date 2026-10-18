// Isolated fixture query only. Never append these rows to publication tables.
let
    Node=(Name as text, Value as any) as record=>[Name=Name,Namespace=null,Value=Value,Attributes={}],
    Payload={Node("MedlineCitation",{Node("PMID","101"),Node("Article",{
        Node("ArticleTitle",{Node("text","Unicode "),Node("i","β"),Node("text"," title")}),
        Node("Journal",{Node("Title","Journal"),Node("JournalIssue",{Node("PubDate",{Node("Year","2024")})})}),
        Node("AuthorList",{Node("Author",{Node("ForeName","Ana"),Node("LastName","Test"),Node("AffiliationInfo",{Node("Affiliation","Source evidence")})})}),
        Node("Abstract",{Node("AbstractText","Full abstract")})})})},
    Fields={[Field="dc.identifier.uri",Value="https://dora.health.qld.gov.au/qldresearchjspui/handle/1/test"],
        [Field="dc.title",Value="Retained title"],[Field="dc.date.issued",Value="2024"],
        [Field="dc.contributor.author",Value="Ana Test"],[Field="dc.description.abstract",Value="Full DORA abstract"]},
    HistoryType=type table [Source=text,SourceID=text,MetadataJSON=text],
    History=#table(HistoryType,{{"PubMed","101",Text.FromBinary(Json.FromValue(Payload))},
        {"DORA","DORA:https://dora.health.qld.gov.au/qldresearchjspui/handle/1/test",Text.FromBinary(Json.FromValue(Fields))}}),
    PM=fnParseRetainedPubMedMetadata(History){0},
    Dora=fnParseRetainedDoraMetadata(History){0},
    BadPM=Table.TransformColumns(History,{{"SourceID",each if _="101" then "102" else _,type text}}),
    BadAttempt=try Table.RowCount(fnParseRetainedPubMedMetadata(BadPM)),
    Empty=#table(HistoryType,{}),
    Result=#table(type table [Check=text,Passed=logical],{
        {"Retained PubMed mixed Unicode text",PM[FullTitle]="Unicode β title"},
        {"Retained PubMed complete author and abstract",PM[FullAuthors]="Ana Test" and PM[FullAbstract]="Full abstract"},
        {"Retained PubMed year precision",PM[IssueDateRaw]="2024" and PM[IssueDatePrecision]="year"},
        {"Retained PubMed identifier mismatch rejected",BadAttempt[HasError]},
        {"Retained DORA bibliography",Dora[Authors]="Ana Test" and Dora[Abstract]="Full DORA abstract"},
        {"Retained DORA year precision",Dora[PublicationDateRaw]="2024" and Dora[PublicationDatePrecision]="year"},
        {"Retained DORA attribution uncertainty",Dora[CHHHSAffiliatedAuthors]=null and Text.Contains(Dora[AttributionEvidence],"review required")},
        {"Empty retained source schemas",Table.HasColumns(fnParseRetainedPubMedMetadata(Empty),{"PMID","FullAuthors"}) and Table.HasColumns(fnParseRetainedDoraMetadata(Empty),{"DORAKey","Authors"})}
    })
in Result
