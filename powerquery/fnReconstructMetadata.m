// Reconstruct complete source JSON from retained UTF8-HEX chunks; fail closed.
(Chunks as table, KeyColumn as text) as table =>
let
    Required={KeyColumn,"ChunkIndex","ChunkCount","MetadataChunk","MetadataCharacters","Encoding"},
    Checked=if List.ContainsAll(Table.ColumnNames(Chunks),Required) then Chunks else error "Metadata chunk schema mismatch",
    Groups=Table.Group(Checked,{KeyColumn},{{"Parts",each _,type table}}),
    Records=List.Transform(Table.ToRecords(Groups),(g)=>
        let
            ID=Record.Field(g,KeyColumn),
            P=Table.Sort(g[Parts],{{"ChunkIndex",Order.Ascending}}),
            N=Table.RowCount(P),
            Indices=P[ChunkIndex],
            Hex=Text.Combine(P[MetadataChunk],""),
            Valid=Value.Is(ID,type text) and Text.Trim(ID)<>"" and N>0 and
                Indices=List.Numbers(0,N) and List.Distinct(P[ChunkCount])={N} and
                List.Distinct(P[MetadataCharacters])={Text.Length(Hex)} and
                List.Distinct(P[Encoding])={"UTF8-HEX"},
            Bytes=if Valid then Binary.FromText(Hex,BinaryEncoding.Hex) else error "Incomplete or inconsistent metadata chunks",
            TextValue=Text.FromBinary(Bytes,TextEncoding.Utf8),
            RoundTrip=Binary.ToText(Text.ToBinary(TextValue,TextEncoding.Utf8),BinaryEncoding.Hex)=Binary.ToText(Bytes,BinaryEncoding.Hex),
            Parsed=Json.Document(TextValue),
            Structured=Value.Is(Parsed,type record) or (Value.Is(Parsed,type list) and List.AllTrue(List.Transform(Parsed,each Value.Is(_,type record)))),
            Result=if RoundTrip and Structured then [SourceID=ID,MetadataJSON=TextValue] else error "Invalid UTF-8 or unstructured source metadata"
        in Result),
    Result=Table.FromRecords(Records,type table [SourceID=text,MetadataJSON=text])
in Result
