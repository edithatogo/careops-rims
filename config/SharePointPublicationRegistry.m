// Power Query M: Ingest clean publication records from the SharePoint Publication Registry list.
// Connects to SharePoint Online Implementation 2.0 and retrieves verified research publications.
// Fully aligns schema and derived fields with the CHHHS Research Publications semantic model.
let
    // Configure your site URL in parameter pSharePointSiteUrl or replace below:
    SiteUrl = try pSharePointSiteUrl otherwise error "pSharePointSiteUrl is required; no tenant default is embedded.",
    
    // Connect to SharePoint using modern Implementation 2.0 (fast, typed, column-filtered)
    Source = SharePoint.Tables(SiteUrl, [Implementation = "2.0", ApiVersion = 15]),
    
    // Select the Publication Registry list
    RegistryTable = Source{[Title = "Publication Registry"]}[Data],
    
    // Exclude records that have been explicitly marked as Excluded during human review
    FilteredIncluded = Table.SelectRows(RegistryTable, each ([ReviewStatus] <> "Excluded")),
    
    // Select the base schema fields from SharePoint
    SelectedColumns = Table.SelectColumns(FilteredIncluded, {
        "Title",
        "SourceKey",
        "CanonicalKey",
        "Authors",
        "Journal",
        "PublicationYear",
        "PublicationMonth",
        "PublicationDateRaw",
        "PublicationDatePrecision",
        "SourceSet",
        "PMID",
        "DOI",
        "PubMedURL",
        "DORAURL",
        "MatchedFacilities",
        "CHHHSAffiliatedAuthors",
        "AttributionEvidence",
        "ReviewStatus",
        "ReviewNotes",
        "FirstObservedUTC",
        "LastObservedUTC",
        "PMCID",
        "AuthorORCIDs",
        "FundingType",
        "IsInternalFunding",
        "ClinicalTrialID",
        "IndigenousHealthFocus",
        "StudyDesign",
        "FieldOfResearch",
        "EuropePMC_OpenAccess",
        "EuropePMC_FullTextURL",
        "EuropePMC_CitedByCount",
        "FunderNames",
        "GrantIDs",
        "OpenAccessStatus",
        "OAUrl",
        "CitationCount_Crossref",
        "CitationCount_OpenAlex"
    }, MissingField.Error),
    
    // Set appropriate data types for base columns
    TypedBase = Table.TransformColumnTypes(SelectedColumns, {
        {"Title", type text},
        {"SourceKey", type text},
        {"CanonicalKey", type text},
        {"Authors", type text},
        {"Journal", type text},
        {"PublicationYear", Int64.Type},
        {"PublicationMonth", type text},
        {"PublicationDateRaw", type text},
        {"PublicationDatePrecision", type text},
        {"SourceSet", type text},
        {"PMID", type text},
        {"DOI", type text},
        {"PubMedURL", type text},
        {"DORAURL", type text},
        {"MatchedFacilities", type text},
        {"CHHHSAffiliatedAuthors", type text},
        {"AttributionEvidence", type text},
        {"ReviewStatus", type text},
        {"ReviewNotes", type text},
        {"FirstObservedUTC", type datetimezone},
        {"LastObservedUTC", type datetimezone},
        {"PMCID", type text},
        {"AuthorORCIDs", type text},
        {"FundingType", type text},
        {"IsInternalFunding", type text},
        {"ClinicalTrialID", type text},
        {"IndigenousHealthFocus", type text},
        {"StudyDesign", type text},
        {"FieldOfResearch", type text},
        {"EuropePMC_OpenAccess", type text},
        {"EuropePMC_FullTextURL", type text},
        {"EuropePMC_CitedByCount", Int64.Type},
        {"FunderNames", type text},
        {"GrantIDs", type text},
        {"OpenAccessStatus", type text},
        {"OAUrl", type text},
        {"CitationCount_Crossref", Int64.Type},
        {"CitationCount_OpenAlex", Int64.Type}
    }),

    // Derive date and semantic model compatibility fields
    AddPublicationDate = Table.AddColumn(TypedBase, "PublicationDate", each 
        if [PublicationMonth] <> null and Text.Length([PublicationMonth]) >= 7 then
            try #date(Int64.From(Text.Start([PublicationMonth], 4)), Int64.From(Text.End([PublicationMonth], 2)), 1) otherwise null
        else if [PublicationYear] <> null then
            #date([PublicationYear], 1, 1)
        else null,
        type date
    ),
    AddOnlineDate = Table.AddColumn(AddPublicationDate, "OnlineDate", each null, type date),
    AddOnlineDateRaw = Table.AddColumn(AddOnlineDate, "OnlineDateRaw", each "", type text),
    AddAbstract = Table.AddColumn(AddOnlineDateRaw, "Abstract", each null, type text),
    AddDedupMethod = Table.AddColumn(AddAbstract, "DedupMethod", each 
        if [SourceSet] = "PubMed; DORA" then "PMID" 
        else if [SourceSet] = "PubMed" then "PMID" 
        else "DORA-only", 
        type text
    ),
    AddAttributionStatus = Table.AddColumn(AddDedupMethod, "AttributionStatus", each 
        if [ReviewStatus] = "Included" then "Verified included" 
        else "Needs review", 
        type text
    ),
    AddPublicationNotice = Table.AddColumn(AddAttributionStatus, "PublicationNotice", each 
        "SharePoint Publication Registry curated record", 
        type text
    ),
    AddAuthorCount = Table.AddColumn(AddPublicationNotice, "AuthorCount", each 
        if [Authors] = null or [Authors] = "" then 0 
        else List.Count(Text.Split([Authors], ";")), 
        Int64.Type
    ),
    AddFacilityMatchCount = Table.AddColumn(AddAuthorCount, "FacilityMatchCount", each 
        if [MatchedFacilities] = null or [MatchedFacilities] = "" then 0 
        else List.Count(Text.Split([MatchedFacilities], ";")), 
        Int64.Type
    ),
    AddRefreshedAtUTC = Table.AddColumn(AddFacilityMatchCount, "RefreshedAtUTC", each 
        DateTimeZone.RemoveZone(DateTimeZone.FixedUtcNow()), 
        type datetime
    )
in
    AddRefreshedAtUTC
