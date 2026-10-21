// Contract payloads are independently qualified bytes compiled into the saved
// definition, never an expected hash or body read from the mutable source packet.
// Equality covers every actual byte before callers parse JSON, HTML, PDF or XLSX.
(ReadFile as function, Contract as record) as function =>
    (URL as text) as binary =>
    let
        Entry=Record.FieldOrDefault(Contract,URL,null),
        Expected=if Entry=null then error "Unpinned source URL" else Binary.Buffer(Binary.Decompress(Binary.FromText(Entry[Payload],BinaryEncoding.Base64),Compression.Deflate)),
        Actual=if Entry=null then error "Unpinned source URL" else Binary.Buffer(ReadFile(URL)),
        Valid=Binary.Length(Expected)=Entry[Bytes] and Binary.Length(Actual)=Entry[Bytes] and Binary.ToText(Actual,BinaryEncoding.Base64)=Binary.ToText(Expected,BinaryEncoding.Base64)
    in
        if Valid then Actual else error "Actual source bytes differ from independently pinned contract"
