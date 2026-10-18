// Power Query M: read the current user's personal funding watchlist.
let
    SiteUrl = "https://<tenant>.sharepoint.com/sites/<site>",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ViewMode = "All"]),
    Watchlist = Source{[Title = "My Funding Watchlist"]}[Items],
    Selected = Table.SelectColumns(Watchlist, {"OpportunityKey", "Scope", "TargetKey", "Active"}, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"OpportunityKey", type text}, {"Scope", type text}, {"TargetKey", type text}, {"Active", type logical}
    })
in
    Typed
