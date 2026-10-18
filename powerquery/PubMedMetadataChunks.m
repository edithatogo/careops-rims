// UTF-8 hex chunks avoid text normalization and per-cell truncation in the model.
let
    Rows=List.Combine(List.Transform(Table.ToRecords(PubMedFullMetadata),(r)=>
        let S=Binary.ToText(Text.ToBinary(r[FullMetadataJSON],TextEncoding.Utf8),BinaryEncoding.Hex),N=Number.RoundUp(Text.Length(S)/20000)
        in List.Transform(List.Numbers(0,N),(i)=>[PMID=r[PMID],ChunkIndex=i,ChunkCount=N,MetadataChunk=Text.Middle(S,i*20000,20000),MetadataCharacters=Text.Length(S),Encoding="UTF8-HEX"]))),
    Result=Table.FromRecords(Rows,type table [PMID=text,ChunkIndex=number,ChunkCount=number,MetadataChunk=text,MetadataCharacters=number,Encoding=text])
in Result
