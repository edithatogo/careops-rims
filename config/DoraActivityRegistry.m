// Power Query M: read the source-preserving DORA Activity Registry list.
// This is an additive query for the existing RIMS report; it is not a
// publication table and must not be joined on Project ID without review.
let
    SiteUrl = try pSharePointSiteUrl otherwise error "pSharePointSiteUrl is required; no tenant default is embedded.",
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ApiVersion = 15]),
    Registry = Source{[Title = "DORA Activity Registry"]}[Data],
    Selected = Table.SelectColumns(Registry, {
        "DORAActivityKey", "DORARecordID", "DORAResourceID", "DORAResourceName",
        "DORAResourceLastModified", "DORAObservedUTC", "DORASourceURL",
        "Project ID", "Review Reference", "HREC (Ethics) Reference Number",
        "Full Project Title", "Short Project Title", "Project Description",
        "Clinical Trial (Yes/No)", "PI Name", "PI Email", "Contact Person Name",
        "Contact Person Email", "Site Name", "Sponsor Name", "Start Date",
        "Finish Date", "Disease Category", "Multi/Single site",
        "DORA Authority (Yes/No)", "DORA Consent (Yes/No)"
    }, MissingField.Error),
    Typed = Table.TransformColumnTypes(Selected, {
        {"DORAActivityKey", type text}, {"DORARecordID", Int64.Type},
        {"DORAResourceID", type text}, {"DORAResourceName", type text},
        {"DORAResourceLastModified", type text}, {"DORAObservedUTC", type datetimezone},
        {"DORASourceURL", type text}, {"Project ID", type text},
        {"Review Reference", type text}, {"HREC (Ethics) Reference Number", type text},
        {"Full Project Title", type text}, {"Short Project Title", type text},
        {"Project Description", type text}, {"Clinical Trial (Yes/No)", type text},
        {"PI Name", type text}, {"PI Email", type text},
        {"Contact Person Name", type text}, {"Contact Person Email", type text},
        {"Site Name", type text}, {"Sponsor Name", type text},
        {"Start Date", type text}, {"Finish Date", type text},
        {"Disease Category", type text}, {"Multi/Single site", type text},
        {"DORA Authority (Yes/No)", type text}, {"DORA Consent (Yes/No)", type text}
    }),
    ValidKeys = Table.SelectRows(Typed, each [DORAActivityKey] <> null and [DORAActivityKey] <> ""),
    Keys = Table.Column(ValidKeys, "DORAActivityKey"),
    Unique = if List.Count(Keys) <> List.Count(List.Distinct(Keys)) then error "DORAActivityKey values are not unique" else ValidKeys
in
    Unique
