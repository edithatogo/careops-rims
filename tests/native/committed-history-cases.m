// Isolated synthetic tests: only Check/Passed results may be loaded into a model.
let
    At="2026-01-01T00:00:00Z",
    A="fixture-a", B="fixture-b",
    Payload="{""title"":""Café β"",""authors"":[""A"",""B""]}",
    Chunk=(ID as text,TextValue as text) as record =>
        let Hex=Binary.ToText(Text.ToBinary(TextValue,TextEncoding.Utf8),BinaryEncoding.Hex)
        in [#"[DORAKey]"=ID,#"[ChunkIndex]"=0,#"[ChunkCount]"=1,#"[MetadataChunk]"=Hex,#"[MetadataCharacters]"=Text.Length(Hex),#"[Encoding]"="UTF8-HEX"],
    Manifest=(Batch as text,Time as text,Keys as list) as binary => Json.FromValue([
        SchemaVersion=1,Status="committed",BatchID=Batch,ObservedAtUTC=Time,
        Validation=[Keysets=true,Metadata=true,RefreshGeneration=true],
        Sources={[Source="DORA",ChunkTable="DoraMetadataChunks",KeyColumn="DORAKey",PageCount=1,ExpectedRecords=List.Count(Keys),ExpectedKeys=Keys]}]),
    Base={{"commit-" & A & ".json",Manifest(A,At,{"fixture:1","fixture:2"})},
        {"uncommitted-" & A & "-DoraMetadataChunks-0.json",Json.FromValue({Chunk("fixture:1",Payload),Chunk("fixture:2","{}")})}},
    Rollover={{"commit-" & B & ".json",Manifest(B,"2026-01-02T00:00:00Z",{"fixture:2"})},
        {"uncommitted-" & B & "-DoraMetadataChunks-0.json",Json.FromValue({Chunk("fixture:2","{""updated"":true}")})}},
    Read=(Rows as list)=>fnReadCommittedHistory(#table(type table [Name=text,Content=binary],Rows)),
    Original=Read(Base),
    Rolled=Read(Base & Rollover),
    Interrupted=Read(Base & {Rollover{1}}),
    Missing=try Table.RowCount(Read({Base{0}})),
    BadKeys=try Table.RowCount(Read({{"commit-" & A & ".json",Manifest(A,At,{"fixture:other"})},Base{1}})),
    NoCommit=try Table.RowCount(Read({Base{1}})),
    BadJSON=try List.Sum(List.Transform(Read({Base{0},{Base{1}{0},Json.FromValue({Chunk("fixture:1","not-json"),Chunk("fixture:2","{}")})}})[MetadataJSON],each Text.Length(_))),
    ArrayPayload="[{""Field"":""dc.title"",""Value"":""Café β""}]",
    ArrayResult=Read({{"commit-" & A & ".json",Manifest(A,At,{"fixture:1"})},{Base{1}{0},Json.FromValue({Chunk("fixture:1",ArrayPayload)})}}),
    ScalarJSON=try Table.RowCount(Read({Base{0},{Base{1}{0},Json.FromValue({Chunk("fixture:1","42"),Chunk("fixture:2","{}")})}})),
    Results=#table(type table [Check=text,Passed=logical],{
        {"Unicode and full JSON roundtrip",Original{0}[MetadataJSON]=Payload},
        {"Source metadata array roundtrip",ArrayResult{0}[MetadataJSON]=ArrayPayload},
        {"Scalar metadata rejected",ScalarJSON[HasError]},
        {"Rollover retains absent publication",Table.RowCount(Rolled)=2},
        {"Rollover preserves first observation",List.AllTrue(List.Transform(Rolled[FirstObservedAtUTC],each _=DateTimeZone.FromText(At)))},
        {"Interrupted uncommitted batch ignored",Table.ToRecords(Original)=Table.ToRecords(Interrupted)},
        {"Missing committed page rejected",Missing[HasError]},
        {"Mismatched committed keys rejected",BadKeys[HasError]},
        {"No commit does not return empty history",NoCommit[HasError]},
        {"Invalid reconstructed JSON rejected",BadJSON[HasError]}})
in Results
