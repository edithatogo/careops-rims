// Source-only helper: retain exact returned bytes and observed schema, not a
// reconstruction of selected publication fields. No additional HTTP request.
(endpoint as text, request as record, body as binary, acquired as text, decoded as any) as record =>
let
    IsXML = endpoint = "efetch.fcgi",
    Describe = (v as any) as record =>
        if v = null then [Kind="null"]
        else if Value.Is(v,type record) then
            if IsXML and Record.FieldCount(v)=4 and Record.HasFields(v,{"Name","Namespace","Value","Attributes"}) then
                [Kind="xml-node",Name=v[Name],Namespace=v[Namespace],ValueSchema=@Describe(v[Value]),AttributeSchema=@Describe(v[Attributes])]
            else [Kind="record",Fields=List.Transform(Record.FieldNames(v),(n)=>[Name=n,Schema=@Describe(Record.Field(v,n))])]
        else if Value.Is(v,type table) then [Kind="table",Columns=Table.ColumnNames(v),Rows=List.Distinct(List.Transform(Table.ToRecords(v),each @Describe(_)))]
        else if Value.Is(v,type list) then [Kind="list",Items=List.Distinct(List.Transform(v,each @Describe(_)))]
        else if Value.Is(v,type text) then [Kind="text"]
        else if Value.Is(v,type logical) then [Kind="logical"]
        else if Value.Is(v,type number) then [Kind="number"]
        else [Kind="other"],
    SafeRequest = Record.SelectFields(request,{"db","retmode","tool","term","retmax","retstart","sort","id","usehistory"},MissingField.Ignore),
    Buffered = Binary.Buffer(body)
in
    [RawEndpoint=endpoint,
     RawRequestJSON=Text.FromBinary(Json.FromValue(SafeRequest),TextEncoding.Utf8),
     RawAcquiredUTC=acquired,
     RawSchemaJSON=Text.FromBinary(Json.FromValue(Describe(decoded)),TextEncoding.Utf8),
     RawByteCount=Binary.Length(Buffered),
     RawBinary=Buffered]
