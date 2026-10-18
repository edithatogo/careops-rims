let
    Full=Table.Buffer(DoraHistoricalMetadata),Chunks=Table.Buffer(DoraMetadataChunks),N=Table.RowCount(Full),
    Joined=Table.NestedJoin(Full,{"DORAKey"},Chunks,{"DORAKey"},"Chunks",JoinKind.LeftOuter),
    BadChunks=Table.SelectRows(Joined,(r)=>let C=Table.Sort(r[Chunks],{{"ChunkIndex",Order.Ascending}}) in Text.FromBinary(Binary.FromText(Text.Combine(C[MetadataChunk],""),BinaryEncoding.Hex),TextEncoding.Utf8)<>r[FullMetadataJSON]),
    BadDates=Table.SelectRows(Full,each (List.Contains({"year","unknown","range"},[PublicationDatePrecision]) and [PublicationDate]<>null) or (List.Contains({"day","month"},[PublicationDatePrecision]) and [PublicationDate]=null)),
    Result=#table(type table [Check=text,Observed=number,Passed=logical],{
        {"Historical DORA records",N,List.AllTrue(List.Transform(Full[CollectionExpectedCount],each _=N))},
        {"Distinct DORA keys",List.Count(List.Distinct(Full[DORAKey])),List.Count(List.Distinct(Full[DORAKey]))=N},
        {"Metadata reconstruction failures",Table.RowCount(BadChunks),Table.IsEmpty(BadChunks)},
        {"Date precision failures",Table.RowCount(BadDates),Table.IsEmpty(BadDates)},
        {"Records needing explicit attribution review",Table.RowCount(Table.SelectRows(Full,each [CHHHSAffiliatedAuthors]=null or [CHHHSAffiliatedAuthors]="")),true}
    })
in Result
