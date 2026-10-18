// Power Query M: read the single canonical Grants Registry SharePoint list.
let
    SiteUrl = "https://<tenant>.sharepoint.com/sites/<site>",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ViewMode = "All"]),
    Registry = Source{[Title = "Grants Registry"]}[Items],
    Selected = Table.SelectColumns(Registry, {
        "OpportunityKey", "Title", "Funder", "Source", "SourceID", "RoundID", "URL",
        "Description", "Eligibility", "Geography", "Amount", "Deadline", "DeadlineRaw",
        "DeadlinePrecision", "Status", "Contact", "CHHHSRelevance", "ReviewStatus",
        "ReviewNotes", "RetrievedUTC", "RetrievedTimestampStatus", "EvidenceHash"
    }, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"OpportunityKey", type text}, {"Title", type text}, {"Funder", type text},
        {"Source", type text}, {"SourceID", type text}, {"RoundID", type text}, {"URL", type text},
        {"Description", type text}, {"Eligibility", type text}, {"Geography", type text},
        {"Amount", type text}, {"Deadline", type text}, {"DeadlineRaw", type text},
        {"DeadlinePrecision", type text}, {"Status", type text}, {"Contact", type text},
        {"CHHHSRelevance", type text}, {"ReviewStatus", type text}, {"ReviewNotes", type text},
        {"RetrievedUTC", type text}, {"RetrievedTimestampStatus", type text}, {"EvidenceHash", type text}
    })
in
    Typed
