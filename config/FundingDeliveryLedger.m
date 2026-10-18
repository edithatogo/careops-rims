// Power Query M: read the current user's personal funding delivery ledger.
let
    SiteUrl = "https://<tenant>.sharepoint.com/sites/<site>",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ViewMode = "All"]),
    Ledger = Source{[Title = "Funding Delivery Ledger"]}[Items],
    Selected = Table.SelectColumns(Ledger, {
        "DeliveryEventKey", "UserKey", "OpportunityKey", "EventType", "Revision", "OffsetDays",
        "Channel", "Status", "ScheduledFor", "SentAt", "ErrorMessage"
    }, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"DeliveryEventKey", type text}, {"UserKey", type text}, {"OpportunityKey", type text},
        {"EventType", type text}, {"Revision", type text}, {"OffsetDays", Int64.Type},
        {"Channel", type text}, {"Status", type text}, {"ScheduledFor", type datetime},
        {"SentAt", type datetime}, {"ErrorMessage", type text}
    })
in
    Typed
