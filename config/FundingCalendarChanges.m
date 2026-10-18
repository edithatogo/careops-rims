// Power Query M: read source-preserving current-user calendar changes.
let
    SiteUrl = try pSharePointSiteUrl otherwise error "pSharePointSiteUrl is required; no tenant default is embedded.",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ApiVersion = 15]),
    Changes = Source{[Title = "Funding Calendar Changes"]}[Items],
    Selected = Table.SelectColumns(Changes, {
        "ChangeKey", "DeadlineKey", "OpportunityKey", "ChangeType", "PreviousRevision",
        "Revision", "PreviousDate", "CalculatedDate", "PreviousCancelled", "Cancelled",
        "SourceURL", "ObservedUTC", "ReviewStatus"
    }, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"ChangeKey", type text}, {"DeadlineKey", type text}, {"OpportunityKey", type text},
        {"ChangeType", type text}, {"PreviousRevision", type text}, {"Revision", type text},
        {"PreviousDate", type date}, {"CalculatedDate", type date},
        {"PreviousCancelled", type logical}, {"Cancelled", type logical},
        {"SourceURL", type text}, {"ObservedUTC", type datetimezone}, {"ReviewStatus", type text}
    }),
    ValidRows = Table.SelectRows(Typed, each
        [ChangeKey] <> null and [ChangeKey] <> "" and
        [DeadlineKey] <> null and [DeadlineKey] <> "" and
        [OpportunityKey] <> null and [OpportunityKey] <> "" and
        [ChangeType] <> null and [ChangeType] <> "" and
        [Revision] <> null and [Revision] <> "" and
        [ObservedUTC] <> null and [ReviewStatus] <> null and [ReviewStatus] <> ""
    )
in
    ValidRows
