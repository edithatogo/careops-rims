let
    // Raw source staging only; not canonical publications or historical completeness.
    Source = Xml.Tables(Web.Contents("https://dora.health.qld.gov.au", [RelativePath="qldresearchjspui/feed/rss_2.0/1/849", Timeout=#duration(0,0,2,0)])),
    Channel = if Table.RowCount(Source) = 1 and Table.HasColumns(Source,"channel") then Source{0}[channel] else error "DORA RSS channel schema changed",
    Items = if Table.RowCount(Channel) <> 1 then error "DORA RSS channel count changed" else if Table.HasColumns(Channel,"item") then Channel{0}[item] else #table(type table [title=nullable text,link=nullable text,description=nullable text,pubDate=nullable text],{}),
    Checked = if Table.HasColumns(Items,{"title","link"}) then Items else error "DORA RSS item schema changed",
    Selected = Table.SelectColumns(Checked,{"title","link","description","pubDate"},MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected,{{"title",type text},{"link",type text},{"description",type text},{"pubDate",type text}},"en-AU")
in Typed
