// Power Query M: read the personal Funding Calendar SharePoint list.
let
    SiteUrl = "https://<tenant>.sharepoint.com/sites/<site>",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ViewMode = "All"]),
    Calendar = Source{[Title = "Funding Calendar"]}[Items],
    Selected = Table.SelectColumns(Calendar, {
        "DeadlineKey", "OpportunityKey", "CalculatedDate", "SourceURL", "Cancelled", "PolicyKey", "ReviewStatus"
    }, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"DeadlineKey", type text}, {"OpportunityKey", type text}, {"CalculatedDate", type datetime},
        {"SourceURL", type text}, {"Cancelled", type logical}, {"PolicyKey", type text}, {"ReviewStatus", type text}
    })
in
    Typed
