// Power Query M: read the typed grant/publication relationship bridge.
let
    SiteUrl = try pSharePointSiteUrl otherwise error "pSharePointSiteUrl is required; no tenant default is embedded.",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ApiVersion = 15]),
    RelationshipTable = Source{[Title = "Grant Relationships"]}[Data],
    Selected = Table.SelectColumns(RelationshipTable, {
        "RelationshipKey", "RelationshipType", "FromKey", "ToKey", "AwardID",
        "EvidenceURL", "Confidence", "ReviewStatus"
    }, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Selected, {
        {"RelationshipKey", type text}, {"RelationshipType", type text},
        {"FromKey", type text}, {"ToKey", type text}, {"AwardID", type text},
        {"EvidenceURL", type text}, {"Confidence", type text}, {"ReviewStatus", type text}
    }),
    ValidRows = Table.SelectRows(Typed, each
        [RelationshipKey] <> null and [RelationshipKey] <> "" and
        [RelationshipType] <> null and [FromKey] <> null and [FromKey] <> "" and
        [ToKey] <> null and [ToKey] <> "" and [EvidenceURL] <> null and [EvidenceURL] <> ""
    )
in
    ValidRows
