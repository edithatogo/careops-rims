// Public collection snapshot, not a durable first-observed registry.
let
    Origin="https://dora.health.qld.gov.au",
    CollectionPath="qldresearchjspui/handle/1/849",
    Fetch=(path as text, query as record) as binary =>
        let
            RetryCodes={408,429,500,502,503,504},
            Get=(n as number) as record => let
                Body=Function.InvokeAfter(()=>Web.Contents("https://dora.health.qld.gov.au",[RelativePath=path,Query=query,Timeout=#duration(0,0,2,0),ManualStatusHandling=RetryCodes,IsRetry=n>0]),#duration(0,0,0,if n=0 then 0.5 else Number.Power(2,n))),
                Status=Record.FieldOrDefault(Value.Metadata(Body),"Response.Status",200)
                in [Status=Status,Body=Binary.Buffer(Body)],
            Attempts=List.Generate(()=>[N=0,R=Get(0)],each [N]<=4,each if List.Contains(RetryCodes,[R][Status]) and [N]<4 then [N=[N]+1,R=Get([N]+1)] else [N=5,R=null],each [R]),
            Final=List.Last(Attempts)
        in if Final[Status]<>200 then error "DORA HTTP retrieval failed; incomplete history must not replace prior data" else Final[Body],
    Page=(offset as number) as record => let
        Body=Fetch(CollectionPath,[offset=Text.From(offset)]),
        Ranges=Html.Table(Body,{{"Range","div.browse_range"}})[Range],
        Counts=List.Distinct(List.Transform(Ranges,each Number.FromText(Text.Trim(Text.AfterDelimiter(_," of ")),"en-US"))),
        Count=if List.Count(Counts)<>1 then error "DORA collection count is unavailable or ambiguous" else Counts{0},
        Links=Html.Table(Body,{{"Path","table[summary='This table browses all dspace content'] a[title='Visit this item']",each [Attributes][href]}})[Path],
        Checked=if List.AnyTrue(List.Transform(Links,each not Text.StartsWith(_,"/qldresearchjspui/handle/1/"))) then error "Unexpected DORA item URL" else Links
        in [Count=Count,Paths=List.Buffer(Checked)],
    First=Page(0),
    Expected=First[Count],
    Offsets=if Expected<=20 then {} else List.Numbers(1,Number.RoundUp(Expected/20)-1),
    Pages=List.Buffer(List.Accumulate(Offsets,{First},(state,n)=>let P=Page(n*20), Forced=List.Count(P[Paths]) in if P[Count]<>Expected then error "DORA collection changed during traversal" else if Forced>=0 then state&{P} else error "Invalid page")),
    Paths=List.Combine(List.Transform(Pages,each [Paths])),
    Keys=if List.Count(Paths)<>Expected or List.Count(List.Distinct(Paths))<>Expected then error "DORA collection keys do not reconcile" else List.Buffer(Paths),
    RecordFor=(path as text) as record => let
        Fields=Table.Buffer(Html.Table(Fetch(Text.TrimStart(path,"/"),[mode="full"]),{{"Field","td[headers='s1']"},{"Value","td[headers='s2']"}},[RowSelector="table.itemDisplayTable tr"])),
        Values=(key as text) as list=>List.Distinct(List.RemoveNulls(Table.SelectRows(Fields,each [Field]=key)[Value])),
        One=(key as text) as nullable text=>let V=Values(key) in if List.Count(V)>1 then error "Conflicting DORA single-value metadata" else List.First(V,null),
        URL=Origin&path, URI=One("dc.identifier.uri"), Title=One("dc.title"),
        Identity=if Title=null or not List.Contains({URL,Text.Replace(URL,"https://","http://")},URI) then error "DORA canonical identity/title mismatch" else URL,
        Raw=One("dc.date.issued"), Parsed=fnParsePubDate(Raw),
        Evidence=Text.Combine(Values("dc.description"),"#(lf)"),
        Markers={"Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated authors:","Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated author:"},
        Marker=List.First(List.Select(Markers,each Text.Contains(Evidence,_)),null),
        Affiliated=if Marker=null then null else Text.Trim(Text.AfterDelimiter(Evidence,Marker)),
        Journal=One("dc.identifier.journaltitle")
        in [DORAKey="DORA:"&Identity,DORAURL=Identity,Title=Title,Authors=Text.Combine(Values("dc.contributor.author"),"; "),
            Abstract=Text.Combine(Values("dc.description.abstract"),"#(lf)"),CHHHSAffiliatedAuthors=Affiliated,
            AttributionEvidence=if Evidence="" then "No explicit DORA affiliation evidence; review required." else Evidence,
            PublicationDate=Parsed[Date],PublicationDateRaw=if Raw=null then "" else Raw,PublicationDatePrecision=Parsed[Precision],PublicationYear=Parsed[Year],
            NormalizedTitle=Text.Select(Text.Lower(Title),{"a".."z","0".."9"}),PMID=One("dc.identifier.pmid"),DOI=One("dc.identifier.doi"),Journal=if Journal=null then One("dc.relation.ispartof") else Journal,
            FullMetadataJSON=Text.FromBinary(Json.FromValue(Table.ToRecords(Fields)),TextEncoding.Utf8),CoverageStatus="Observed public collection snapshot",CollectionExpectedCount=Expected],
    Records=List.Accumulate(Keys,{},(state,path)=>let R=RecordFor(path),Force=Text.Length(R[FullMetadataJSON]) in if Force>0 then state&{R} else error "Empty DORA metadata"),
    Result=Table.FromRecords(Records,type table [DORAKey=text,DORAURL=text,Title=text,Authors=text,Abstract=text,CHHHSAffiliatedAuthors=nullable text,AttributionEvidence=text,PublicationDate=nullable date,PublicationDateRaw=text,PublicationDatePrecision=text,PublicationYear=nullable number,NormalizedTitle=text,PMID=nullable text,DOI=nullable text,Journal=nullable text,FullMetadataJSON=text,CoverageStatus=text,CollectionExpectedCount=number]),
    Verified=if Table.RowCount(Result)<>Expected or List.Count(List.Distinct(Result[DORAKey]))<>Expected then error "DORA metadata keys do not reconcile" else Result
in
    Verified
