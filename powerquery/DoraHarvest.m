let
    DoraURL = "https://dora.health.qld.gov.au/qldresearchjspui/feed/rss_2.0/1/849",
    // Retain raw observations separately; this reference is not durable storage.
    AsText = DoraSourceObservations,
    NormalizeTitle = (value as nullable text) as text => if value = null then "" else Text.Select(Text.Lower(value), {"a".."z","0".."9"}),
    ExtractBetween = (value as nullable text, start as text, finish as text) as nullable text =>
        if value = null or not Text.Contains(value,start) then null else try Text.Trim(Text.BeforeDelimiter(Text.AfterDelimiter(value,start),finish)) otherwise null,
    ExtractAffiliatedAuthors = (value as nullable text) as nullable text =>
        let
            singular = "Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated author: ",
            plural = "Cairns & Hinterland Hospital and Health Service (CHHHS) affiliated authors: ",
            marker = if value <> null and Text.Contains(value,plural) then plural else if value <> null and Text.Contains(value,singular) then singular else null,
            result = if marker = null then null else Text.Trim(Text.AfterDelimiter(value,marker))
        in result,
    AddAuthors = Table.AddColumn(AsText,"Authors",each ExtractBetween([description],"Authors: ","#(lf)Abstract:"),type nullable text),
    AddAbstract = Table.AddColumn(AddAuthors,"Abstract",each ExtractBetween([description],"Abstract: ","#(lf)Description:"),type nullable text),
    AddCHHHSAuthors = Table.AddColumn(AddAbstract,"CHHHSAffiliatedAuthors",each ExtractAffiliatedAuthors([description]),type nullable text),
    // RSS pubDate is a feed timestamp, not corroborated publication-date evidence.
    AddEvidence = Table.AddColumn(AddCHHHSAuthors,"AttributionEvidence",each if [CHHHSAffiliatedAuthors]=null or Text.Trim([CHHHSAffiliatedAuthors])="" then "No CHHHS affiliation statement found in RSS description; review required." else "DORA RSS CHHHS affiliated author statement: " & [CHHHSAffiliatedAuthors],type text),
    AddRawDate = Table.AddColumn(AddEvidence,"PublicationDateRaw",each [pubDate],type nullable text),
    AddPrecision = Table.AddColumn(AddRawDate,"PublicationDatePrecision",each "unknown",type text),
    AddDate = Table.AddColumn(AddPrecision,"PublicationDate",each null,type nullable date),
    AddYear = Table.AddColumn(AddDate,"PublicationYear",each if [PublicationDate]=null then null else Date.Year([PublicationDate]),Int64.Type),
    AddNorm = Table.AddColumn(AddYear,"NormalizedTitle",each NormalizeTitle([title]),type text),
    AddKey = Table.AddColumn(AddNorm,"DORAKey",each "DORA:" & Text.From([link]),type text),
    Selected = Table.SelectColumns(AddKey,{"DORAKey","title","Authors","Abstract","CHHHSAffiliatedAuthors","AttributionEvidence","PublicationDate","PublicationDateRaw","PublicationDatePrecision","PublicationYear","NormalizedTitle","link"}),
    Renamed = Table.RenameColumns(Selected,{{"title","Title"},{"link","DORAURL"}}),
    Checked = if Table.HasColumns(Renamed,{"DORAKey","Title","PublicationYear","DORAURL"}) then Renamed else error "DORA RSS schema changed"
in
    Checked
