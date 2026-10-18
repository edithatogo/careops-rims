// Parse complete DORA fields from accepted retained observations only.
(History as table) as table =>
let
    Selected=Table.SelectRows(History,each [Source]="DORA"),
    Expected=Table.RowCount(Selected),
    RecordFor=(observation as record) as record => let
        Fields=Table.Buffer(Table.FromRecords(Json.Document(observation[MetadataJSON]))),
        Values=(key as text) as list=>List.Distinct(List.RemoveNulls(Table.SelectRows(Fields,each [Field]=key)[Value])),
        One=(key as text) as nullable text=>let V=Values(key) in if List.Count(V)>1 then error "Conflicting DORA single-value metadata" else List.First(V,null),
        URL=Text.AfterDelimiter(observation[SourceID],"DORA:"), URI=One("dc.identifier.uri"), Title=One("dc.title"),
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
            FullMetadataJSON=Text.FromBinary(Json.FromValue(Table.ToRecords(Fields)),TextEncoding.Utf8),CoverageStatus="Accepted retained source observation",CollectionExpectedCount=null],
    Records=List.Transform(Table.ToRecords(Selected),each RecordFor(_)),
    Result=Table.FromRecords(Records,type table [DORAKey=text,DORAURL=text,Title=text,Authors=text,Abstract=text,CHHHSAffiliatedAuthors=nullable text,AttributionEvidence=text,PublicationDate=nullable date,PublicationDateRaw=text,PublicationDatePrecision=text,PublicationYear=nullable number,NormalizedTitle=text,PMID=nullable text,DOI=nullable text,Journal=nullable text,FullMetadataJSON=text,CoverageStatus=text,CollectionExpectedCount=nullable number]),
    Verified=if Table.RowCount(Result)<>Expected or List.Count(List.Distinct(Result[DORAKey]))<>Expected or List.Sort(Result[DORAKey])<>List.Sort(Selected[SourceID]) then error "Retained DORA metadata keys do not reconcile" else Result
in
    Verified
