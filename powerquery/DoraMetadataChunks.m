let
    Rows=List.Combine(List.Transform(Table.ToRecords(DoraHistoricalMetadata),(r)=>let S=Binary.ToText(Text.ToBinary(r[FullMetadataJSON],TextEncoding.Utf8),BinaryEncoding.Hex),N=Number.RoundUp(Text.Length(S)/20000)
        in List.Transform(List.Numbers(0,N),(i)=>[DORAKey=r[DORAKey],ChunkIndex=i,ChunkCount=N,MetadataChunk=Text.Middle(S,i*20000,20000),MetadataCharacters=Text.Length(S),Encoding="UTF8-HEX"]))),
    Result=Table.FromRecords(Rows,type table [DORAKey=text,ChunkIndex=number,ChunkCount=number,MetadataChunk=text,MetadataCharacters=number,Encoding=text])
in Result
