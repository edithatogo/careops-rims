let
    // Stable output schema also applies when either source has no records.
    PublicationType = type table [
        CanonicalKey = nullable text,
        PMID = nullable text,
        Title = nullable text,
        Journal = nullable text,
        Authors = nullable text,
        DOI = nullable text,
        PubMedURL = nullable text,
        DORAURL = nullable text,
        CHHHSAffiliatedAuthors = nullable text,
        Abstract = nullable text,
        SourceSet = nullable text,
        DedupMethod = nullable text,
        PublicationDateRaw = nullable text,
        PublicationDatePrecision = nullable text,
        PublicationMonth = nullable text,
        OnlineDateRaw = nullable text,
        MatchedFacilities = nullable text,
        AttributionStatus = nullable text,
        AttributionEvidence = nullable text,
        PublicationNotice = nullable text,
        PMCID = nullable text,
        AuthorORCIDs = nullable text,
        FundingType = nullable text,
        IsInternalFunding = nullable text,
        FunderNames = nullable text,
        GrantIDs = nullable text,
        ClinicalTrialID = nullable text,
        IndigenousHealthFocus = nullable text,
        FieldOfResearch = nullable text,
        StudyDesign = nullable text,
        EuropePMC_OpenAccess = nullable text,
        EuropePMC_FullTextURL = nullable text,
        OpenAccessStatus = nullable text,
        OAUrl = nullable text,
        PDFDownloadStatus = nullable text,
        LocalPDFPath = nullable text,
        PDFDownloadedUTC = nullable text,
        PublicationDate = nullable date,
        OnlineDate = nullable date,
        RefreshedAtUTC = nullable datetime,
        PublicationYear = nullable number,
        AuthorCount = nullable number,
        FacilityMatchCount = nullable number,
        EuropePMC_CitedByCount = nullable number,
        CitationCount_Crossref = nullable number,
        CitationCount_OpenAlex = nullable number,
        PDFFileSize = nullable number
    ],
    PubMed = PubMedPublications,
    Dora = DoraHistoricalMetadata,
    NormalizeTitle = (value as nullable text) as text => if value = null then "" else Text.Select(Text.Lower(value), {"a".."z","0".."9"}),
    NormalizePMID = (value as nullable text) as nullable text =>
        let t = if value = null then "" else Text.Trim(value)
        in if t <> "" and Text.Select(t,{"0".."9"}) = t and not Text.StartsWith(t,"0") then t else null,
    NormalizeDOI = (value as nullable text) as nullable text =>
        let
            raw = if value = null then "" else Text.Lower(Text.Trim(value)),
            prefixes = {"https://doi.org/","http://doi.org/","https://dx.doi.org/","http://dx.doi.org/","doi:"},
            prefix = List.First(List.Select(prefixes,each Text.StartsWith(raw,_)),null),
            t = if prefix = null then raw else Text.Trim(Text.Range(raw,Text.Length(prefix))),
            registration = try Text.BetweenDelimiters(t,"10.","/") otherwise "",
            suffix = try Text.AfterDelimiter(t,"/") otherwise "",
            valid = Text.StartsWith(t,"10.") and Text.Length(registration)>=4 and Text.Length(registration)<=9 and Text.Select(registration,{"0".."9"})=registration and suffix<>"" and Text.Remove(t,{" ","#(tab)","#(cr)","#(lf)"})=t
        in if valid then t else null,
    HasInvalidIdentifier = (r as record) as logical =>
        let p = Record.FieldOrDefault(r,"PMID",null), d = Record.FieldOrDefault(r,"DOI",null)
        in (p <> null and p <> "" and NormalizePMID(p) = null) or (d <> null and d <> "" and NormalizeDOI(d) = null),
    PubMedNorm = Table.AddColumn(PubMed,"NormalizedTitle",each NormalizeTitle([Title]),type text),
    MatchDora = Table.AddColumn(Dora,"Match",(d as record) =>
        let
            doi = NormalizeDOI(Record.FieldOrDefault(d,"DOI",null)),
            suppliedPMID = NormalizePMID(Record.FieldOrDefault(d,"PMID",null)),
            exact = Table.SelectRows(PubMedNorm,(p as record) => (doi <> null and NormalizeDOI(p[DOI]) = doi) or (suppliedPMID <> null and NormalizePMID(p[PMID]) = suppliedPMID)),
            conflict = List.AnyTrue(List.Transform(Table.ToRecords(exact),(p as record) => (doi <> null and NormalizeDOI(p[DOI]) <> null and NormalizeDOI(p[DOI]) <> doi) or (suppliedPMID <> null and NormalizePMID(p[PMID]) <> null and NormalizePMID(p[PMID]) <> suppliedPMID))),
            invalid = HasInvalidIdentifier(d) or List.AnyTrue(List.Transform(Table.ToRecords(exact),each HasInvalidIdentifier(_))),
            title = NormalizeTitle(d[Title]),
            candidates = Table.SelectRows(PubMedNorm,(p as record) => title <> "" and d[PublicationYear] <> null and p[PublicationYear] = d[PublicationYear] and p[NormalizedTitle] = title),
            n = Table.RowCount(exact),
            titleCount = Table.RowCount(candidates),
            matched = n = 1 and not conflict and not invalid,
            pmid = if matched then exact{0}[PMID] else null,
            method = if invalid then "invalid-identifiers-needs-review" else if conflict then "conflicting-identifiers-needs-review" else if n > 1 then "ambiguous-identifiers-needs-review" else if matched then (if suppliedPMID = NormalizePMID(exact{0}[PMID]) then "PMID" else "DOI") else if titleCount > 1 then "ambiguous-title+year" else if titleCount = 1 then "possible-title+year-needs-review" else "DORA-only"
        in [PMID=pmid,Method=method,CandidateCount=if n > 0 then n else titleCount,CandidateKeys=Text.Combine(List.Transform(if n > 0 then exact[PMID] else candidates[PMID],each "PMID:" & _),"; ")],type record),
    ExpandMatch = Table.ExpandRecordColumn(MatchDora,"Match",{"PMID","Method","CandidateCount","CandidateKeys"},{"MatchedPMID","DedupMethod","CandidateCount","CandidateKeys"}),
    PubMedCanonical = Table.AddColumn(PubMedNorm,"CanonicalKey",each "PMID:" & [PMID],type text),
    EnrichPubMed = Table.AddColumn(PubMedCanonical,"DoraEvidence",(p as record) => Table.SelectRows(ExpandMatch,each [MatchedPMID]=p[PMID]),type table),
    PubMedRows = Table.AddColumn(EnrichPubMed,"Canonical",(p as record) =>
        let
            d = p[DoraEvidence], has = Table.RowCount(d)>0,
            urls = if has then Text.Combine(List.Distinct(List.RemoveNulls(d[DORAURL])),"; ") else null,
            chhhs = if has then Text.Combine(List.Distinct(List.RemoveNulls(d[CHHHSAffiliatedAuthors])),"; ") else null,
            evidence = Text.Combine(List.RemoveNulls({p[AttributionEvidence]} & (if has then d[AttributionEvidence] else {})), "; "),
            abstracts = List.Select(List.RemoveNulls({Record.FieldOrDefault(p,"Abstract",null)} & (if has then d[Abstract] else {})),each _<>""),
            abstract = if List.Count(abstracts)>0 then abstracts{0} else null
        in [
            CanonicalKey=p[CanonicalKey],PMID=p[PMID],Title=p[Title],Journal=p[Journal],Authors=p[Authors],DOI=p[DOI],PubMedURL=p[PubMedURL],DORAURL=urls,
            PublicationDate=p[PublicationDate],PublicationDateRaw=p[PublicationDateRaw],PublicationDatePrecision=p[PublicationDatePrecision],PublicationMonth=p[PublicationMonth],PublicationYear=p[PublicationYear],
            OnlineDate=p[OnlineDate],OnlineDateRaw=p[OnlineDateRaw],AuthorCount=p[AuthorCount],
            MatchedFacilities=p[MatchedFacilities],CHHHSAffiliatedAuthors=chhhs,Abstract=abstract,SourceSet=if has then "PubMed; DORA" else "PubMed",DedupMethod=if has then Text.Combine(List.Distinct(d[DedupMethod]),"; ") else "PMID",
            AttributionEvidence=evidence,
            AttributionStatus=if has then p[AttributionStatus] & "; DORA identifier match" else p[AttributionStatus],PublicationNotice=p[PublicationNotice],FacilityMatchCount=p[FacilityMatchCount],RefreshedAtUTC=p[RefreshedAtUTC]
        ],type record),
    PubMedCanonicalOnly = Table.SelectColumns(PubMedRows,{"Canonical"}),
    ExpandedPubMed = Table.FromRecords(Table.Column(PubMedCanonicalOnly,"Canonical"), PublicationType, MissingField.UseNull),
    DoraOnly0 = Table.SelectRows(ExpandMatch,each [MatchedPMID]=null),
    DoraOnly = Table.AddColumn(DoraOnly0,"Canonical",(d as record) => [
        CanonicalKey=d[DORAKey],PMID=Record.FieldOrDefault(d,"PMID",null),Title=d[Title],Journal=Record.FieldOrDefault(d,"Journal",null),Authors=d[Authors],DOI=Record.FieldOrDefault(d,"DOI",null),PubMedURL=null,DORAURL=d[DORAURL],
        PublicationDate=d[PublicationDate],PublicationDateRaw=d[PublicationDateRaw],PublicationDatePrecision=d[PublicationDatePrecision],PublicationMonth=if d[PublicationDate]<>null and List.Contains({"day","month"},d[PublicationDatePrecision]) then Date.ToText(d[PublicationDate],"yyyy-MM","en-AU") else null,PublicationYear=d[PublicationYear],
        OnlineDate=null,OnlineDateRaw="",AuthorCount=if d[Authors]=null or d[Authors]="" then null else List.Count(Text.Split(d[Authors],";")),
        MatchedFacilities=if d[CHHHSAffiliatedAuthors] <> null and Text.Trim(d[CHHHSAffiliatedAuthors]) <> "" then "Cairns and Hinterland HHS" else "",CHHHSAffiliatedAuthors=d[CHHHSAffiliatedAuthors],Abstract=d[Abstract],SourceSet="DORA",DedupMethod=d[DedupMethod],
        AttributionEvidence=d[AttributionEvidence],
        AttributionStatus=(if d[CHHHSAffiliatedAuthors] <> null and Text.Trim(d[CHHHSAffiliatedAuthors]) <> "" then "DORA author affiliation statement" else "DORA attribution needs review") & (if d[DedupMethod] <> "DORA-only" then "; identity needs review" else ""),PublicationNotice="DORA full metadata; observed public collection snapshot; institutional scope remains reviewable",FacilityMatchCount=if d[CHHHSAffiliatedAuthors] <> null and Text.Trim(d[CHHHSAffiliatedAuthors]) <> "" then 1 else 0,RefreshedAtUTC=DateTimeZone.RemoveZone(DateTimeZone.FixedUtcNow())
    ],type record),
    DoraCanonicalOnly = Table.SelectColumns(DoraOnly,{"Canonical"}),
    ExpandedDora = Table.FromRecords(Table.Column(DoraCanonicalOnly,"Canonical"), PublicationType, MissingField.UseNull),
    PubMedSelected = Table.SelectColumns(ExpandedPubMed,Table.ColumnNames(ExpandedDora),MissingField.UseNull),
    Combined = Table.Combine({PubMedSelected,ExpandedDora}, PublicationType),
    Verified = if Table.RowCount(Combined) <> List.Count(List.Distinct(Combined[CanonicalKey])) then error "Canonical publication key is not unique" else Combined,
    PubMedMatches0 = PubMedHarvest[Matches],
    PubMedMatches = Table.AddColumn(PubMedMatches0,"CanonicalKey",each "PMID:" & [PMID],type text),
    PubMedBridge = Table.SelectColumns(PubMedMatches,{"CanonicalKey","FacilityKey"}),
    DoraBridge = Table.FromRecords(List.Transform(Table.ToRecords(Table.SelectRows(DoraOnly,each [CHHHSAffiliatedAuthors] <> null and Text.Trim([CHHHSAffiliatedAuthors]) <> "")), each [CanonicalKey=[DORAKey],FacilityKey="hhs"]),type table [CanonicalKey=text,FacilityKey=text]),
    Matches = Table.Distinct(Table.Combine({PubMedBridge,DoraBridge})),
    // One row per observed source identity, including unresolved DORA candidates.
    SourceMapType = type table [Source=text,SourceKey=text,CanonicalKey=text],
    SourceMap = Table.Combine({
        Table.FromRecords(List.Transform(Table.ToRecords(PubMed),each [Source="PubMed",SourceKey="PMID:" & [PMID],CanonicalKey="PMID:" & [PMID]]),SourceMapType),
        Table.FromRecords(List.Transform(Table.ToRecords(ExpandMatch),each [Source="DORA",SourceKey=[DORAKey],CanonicalKey=if [MatchedPMID]=null then [DORAKey] else "PMID:" & [MatchedPMID]]),SourceMapType)
    },SourceMapType),
    CanonicalKeys = Verified[CanonicalKey],
    Audit = #table(type table [Check=text,Observed=number,Passed=logical],{
        {"Source identities mapped exactly once",Table.RowCount(SourceMap),Table.RowCount(SourceMap)=Table.RowCount(PubMed)+Table.RowCount(Dora) and Table.RowCount(SourceMap)=List.Count(List.Distinct(SourceMap[SourceKey]))},
        {"Source mappings without canonical record",List.Count(List.Difference(SourceMap[CanonicalKey],CanonicalKeys)),List.IsEmpty(List.Difference(SourceMap[CanonicalKey],CanonicalKeys))},
        {"Canonical records without source",List.Count(List.Difference(CanonicalKeys,SourceMap[CanonicalKey])),List.IsEmpty(List.Difference(CanonicalKeys,SourceMap[CanonicalKey]))},
        {"Facility mappings without canonical record",List.Count(List.Difference(Matches[CanonicalKey],CanonicalKeys)),List.IsEmpty(List.Difference(Matches[CanonicalKey],CanonicalKeys))},
        {"Canonical count balances source matches",Table.RowCount(Verified),Table.RowCount(Verified)=Table.RowCount(PubMed)+Table.RowCount(DoraOnly0)},
        {"Source sets balance canonical count",Table.RowCount(Verified),Table.RowCount(Verified)=Table.RowCount(Table.SelectRows(Verified,each List.Contains({"PubMed","DORA","PubMed; DORA"},[SourceSet]))) }
    })
in
    [Publications=Verified,Matches=Matches,SourceMap=SourceMap,Audit=Audit,DoraReconciliation=Table.SelectColumns(ExpandMatch,{"DORAKey","Title","DORAURL","MatchedPMID","DedupMethod","CandidateCount","CandidateKeys","CHHHSAffiliatedAuthors"})]
