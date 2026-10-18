let
    Full=Table.Buffer(PubMedFullMetadata),
    Chunks=Table.Buffer(PubMedMetadataChunks),
    Expected=List.Distinct(PubMedHarvest[IDs]),
    Joined=Table.NestedJoin(Full,{"PMID"},Chunks,{"PMID"},"Chunks",JoinKind.LeftOuter),
    BadChunks=Table.SelectRows(Joined,(r)=>let C=Table.Sort(r[Chunks],{{"ChunkIndex",Order.Ascending}}),N=Table.RowCount(C) in N=0 or Text.FromBinary(Binary.FromText(Text.Combine(C[MetadataChunk],""),BinaryEncoding.Hex),TextEncoding.Utf8)<>r[FullMetadataJSON] or List.Count(List.Distinct(C[ChunkIndex]))<>N or List.AnyTrue(List.Transform(C[ChunkCount],each _<>N))),
    BadDates=Table.SelectRows(Full,each (List.Contains({"year","unknown","range"},[IssueDatePrecision]) and [IssueDate]<>null) or (List.Contains({"day","month"},[IssueDatePrecision]) and [IssueDate]=null)),
    AuthorFailures=Table.SelectRows(Full,each List.Count(Json.Document([AuthorAffiliationsJSON]))<>[FullAuthorCount]),
    Result=#table(type table [Check=text,Observed=number,Passed=logical],{
        {"Full metadata publications",Table.RowCount(Full),Table.RowCount(Full)=List.Count(Expected)},
        {"Distinct full-metadata PMIDs",List.Count(List.Distinct(Full[PMID])),List.Count(List.Distinct(Full[PMID]))=List.Count(Expected)},
        {"Missing metadata PMIDs",List.Count(List.Difference(Expected,Full[PMID])),List.IsEmpty(List.Difference(Expected,Full[PMID]))},
        {"Unexpected metadata PMIDs",List.Count(List.Difference(Full[PMID],Expected)),List.IsEmpty(List.Difference(Full[PMID],Expected))},
        {"Metadata reconstruction failures",Table.RowCount(BadChunks),Table.IsEmpty(BadChunks)},
        {"Metadata chunk rows",Table.RowCount(Chunks),List.AllTrue(List.Transform(Chunks[MetadataChunk],each Text.Length(_)<=20000))},
        {"Author evidence count failures",Table.RowCount(AuthorFailures),Table.IsEmpty(AuthorFailures)},
        {"Date precision failures",Table.RowCount(BadDates),Table.IsEmpty(BadDates)},
        {"Blank full titles",Table.RowCount(Table.SelectRows(Full,each Text.Trim([FullTitle])="")),Table.IsEmpty(Table.SelectRows(Full,each Text.Trim([FullTitle])=""))}
    })
in Result
