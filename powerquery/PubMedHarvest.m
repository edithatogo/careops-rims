let
    RefreshedUTC = DateTimeZone.RemoveZone(DateTimeZone.FixedUtcNow()),
    ActiveQueries = Table.ToRecords(Table.SelectRows(FacilityDefinitions, each [Active] = true)),
    SearchOne = (definition as record) as record =>
        let
            Payload = fnNCBIJson("esearch.fcgi", [term=definition[PubMedQuery], retmax="10000", sort="pub_date"]),
            Search = if Record.HasFields(Payload, "esearchresult") then Payload[esearchresult] else error "Missing esearchresult",
            // Unknown field names are fatal. An unmatched phrase can be a valid zero-hit affiliation search.
            SearchErrors = Record.FieldOrDefault(Search, "errorlist", []),
            FatalErrors = if Value.Is(SearchErrors,type record) then Record.RemoveFields(SearchErrors,{"phrasesnotfound", "quotedphrasesnotfound", "phrasesignored"},MissingField.Ignore) else error "Unexpected ESearch errorlist structure",
            HasFatalErrors = List.AnyTrue(List.Transform(Record.FieldValues(FatalErrors), each if Value.Is(_,type list) then List.Count(_) > 0 else if _ = null then false else Text.From(_) <> "")),
            Checked = if Record.HasFields(Search, "ERROR") then error Error.Record("PubMedSearch", Text.From(Search[ERROR]), null)
                      else if HasFatalErrors then error Error.Record("PubMedSearch", "Search contains errors; check the affiliation query", FatalErrors)
                      else Search,
            Count = Number.FromText(Text.From(Checked[count]), "en-US"),
            IDs = List.Buffer(List.Transform(Checked[idlist], each Text.From(_))),
            Complete = if Count > 10000 then error Error.Record("PubMedLimit", "Segment this affiliation search into date ranges before retrieving more than 10000 records", [Facility=definition[FacilityName], Count=Count])
                       else if Count < 0 or Count <> List.Count(List.Distinct(IDs)) or List.Count(IDs) <> List.Count(List.Distinct(IDs)) then error Error.Record("PubMedIncomplete", "ESearch count does not match retrieved distinct PMIDs", [Facility=definition[FacilityName], Count=Count, Retrieved=List.Count(IDs)])
                       else IDs,
            WarningParts = List.RemoveNulls({
                if Record.HasFields(Checked, "warninglist") then Checked[warninglist] else null,
                if Record.HasFields(SearchErrors,"phrasesnotfound") and List.Count(SearchErrors[phrasesnotfound]) > 0 then [phrasesnotfound=SearchErrors[phrasesnotfound]] else null,
                if Record.HasFields(SearchErrors,"quotedphrasesnotfound") and List.Count(SearchErrors[quotedphrasesnotfound]) > 0 then [quotedphrasesnotfound=SearchErrors[quotedphrasesnotfound]] else null,
                if Record.HasFields(SearchErrors,"phrasesignored") and List.Count(SearchErrors[phrasesignored]) > 0 then [phrasesignored=SearchErrors[phrasesignored]] else null
            }),
            Warnings = if List.Count(WarningParts) > 0 then Text.FromBinary(Json.FromValue(WarningParts), TextEncoding.Utf8) else "",
            Translation = Text.From(Record.FieldOrDefault(Checked, "querytranslation", ""))
        in [FacilityKey=definition[FacilityKey], IDs=Complete, SearchCount=Count, QueryTranslation=Translation, Warnings=Warnings],
    // Accumulate and buffer each request result to avoid unconstrained parallel fan-out.
    SearchResults = List.Buffer(List.Accumulate(ActiveQueries, {}, (state, definition) =>
        let Result = SearchOne(definition), Force = List.Count(Result[IDs])
        in if Force >= 0 then state & {Result} else error "Invalid count")),
    // Preserve the earlier collector's scope-review search without asserting a facility link.
    ScopeSearch = SearchOne([FacilityKey="scope-review:cphu",FacilityName="Cairns Public Health Unit - scope review",PubMedQuery="""Cairns Public Health Unit""[Affiliation]"]),
    MatchRecords = List.Combine(List.Transform(SearchResults, (s) => List.Transform(s[IDs], (id) => [PMID=id, FacilityKey=s[FacilityKey]]))),
    Matches = Table.Buffer(Table.Distinct(Table.FromRecords(MatchRecords, type table [PMID=text,FacilityKey=text]))),
    AllIDs = List.Buffer(List.Sort(List.Distinct(Matches[PMID] & ScopeSearch[IDs]))),
    Batches = List.Split(AllIDs,100),
    FetchBatch = (ids as list) as list =>
        let
            Payload = fnNCBIJson("esummary.fcgi", [id=Text.Combine(ids,",")]),
            Result = if Record.HasFields(Payload, "result") then Payload[result] else error "Missing ESummary result",
            ReturnedIDs = List.Transform(Result[uids], each Text.From(_)),
            CheckedIDs = if List.Count(List.Difference(ids,ReturnedIDs)) > 0 or List.Count(List.Difference(ReturnedIDs,ids)) > 0 or List.Count(ReturnedIDs) <> List.Count(ids) then error "ESummary PMID reconciliation failed" else ReturnedIDs,
            Rows = List.Transform(CheckedIDs, (id) =>
                let Row = Record.Field(Result,id)
                in if Record.HasFields(Row,"error") then error Error.Record("PubMedSummary",Text.From(Row[error]),[PMID=id])
                   else if Text.From(Row[uid]) <> id then error "ESummary UID mismatch" else Row)
        in List.Buffer(Rows),
    RawRows = List.Buffer(List.Accumulate(Batches, {}, (state,batch) => state & FetchBatch(batch))),
    ToPublication = (row as record) as record =>
        let
            PMID = Text.From(row[uid]),
            ParsedDate = fnParsePubDate(Text.From(Record.FieldOrDefault(row,"pubdate",""))),
            OnlineRaw = Text.From(Record.FieldOrDefault(row,"epubdate","")),
            OnlineParsed = fnParsePubDate(OnlineRaw),
            Types = List.Transform(Record.FieldOrDefault(row,"pubtype",{}),each Text.From(_)),
            TypeText = Text.Lower(Text.Combine(Types,"|")),
            Trial = Text.Contains(TypeText,"clinical trial") or Text.Contains(TypeText,"randomized controlled trial") or Text.Contains(TypeText,"controlled clinical trial"),
            Synthesis = Text.Contains(TypeText,"systematic review") or Text.Contains(TypeText,"meta-analysis"),
            Class = if Trial then "Clinical trial" else if Text.Contains(TypeText,"meta-analysis") then "Meta-analysis" else if Text.Contains(TypeText,"systematic review") then "Systematic review" else if Text.Contains(TypeText,"review") then "Review" else if Text.Contains(TypeText,"journal article") then "Journal article" else "Other",
            AuthorRows = Record.FieldOrDefault(row,"authors",{}),
            Identifiers = Record.FieldOrDefault(row,"articleids",{}),
            DOIValues = List.Select(Identifiers, each Record.FieldOrDefault(_,"idtype","") = "doi"),
            DOI = if List.Count(DOIValues) = 0 then null else Text.From(DOIValues{0}[value]),
            FacilityKeys = Table.SelectRows(Matches, each [PMID] = PMID)[FacilityKey],
            MatchedQueries = Table.SelectRows(FacilityDefinitions, each List.Contains(FacilityKeys,[FacilityKey]))[PubMedQuery],
            FacilityNames = Table.SelectRows(FacilityDefinitions, each List.Contains(FacilityKeys,[FacilityKey]))[FacilityName],
            ModelDate = if ParsedDate[Date] = null then null else if Date.Year(ParsedDate[Date]) < 1900 then null else ParsedDate[Date],
            ModelOnlineDate = if OnlineParsed[Date] = null then null else if Date.Year(OnlineParsed[Date]) < 1900 then null else OnlineParsed[Date],
            ModelDatePrecision = if ParsedDate[Date] <> null and ModelDate = null then "outside-model-range" else ParsedDate[Precision],
            PublicationMonth = if List.Contains({"day","month"},ModelDatePrecision) then Date.ToText(ModelDate, "yyyy-MM", "en-AU") else null,
            Notice = if Text.Contains(TypeText,"retracted publication") then "Retracted publication" else if Text.Contains(TypeText,"retraction of publication") then "Retraction notice" else if Text.Contains(TypeText,"expression of concern") then "Expression of concern" else "No notice in retrieved publication types"
        in [
            PMID=PMID, Title=Text.From(Record.FieldOrDefault(row,"title","")),
            Journal=Text.From(Record.FieldOrDefault(row,"fulljournalname","")),
            Authors=Text.Combine(List.Transform(AuthorRows,each Text.From(Record.FieldOrDefault(_,"name",""))),"; "),
            DOI=DOI, PubMedURL="https://pubmed.ncbi.nlm.nih.gov/" & PMID & "/",
            PublicationDate=ModelDate, PublicationDateRaw=ParsedDate[Raw], PublicationDatePrecision=ModelDatePrecision,
            PublicationMonth=PublicationMonth, PublicationYear=ParsedDate[Year],
            OnlineDate=ModelOnlineDate, OnlineDateRaw=OnlineRaw,
            AuthorCount=List.Count(AuthorRows), PublicationTypes=Text.Combine(Types,"; "),
            PublicationClass=Class, IsClinicalTrial=Trial, IsEvidenceSynthesis=Synthesis,
            MatchedFacilities=Text.Combine(List.Sort(FacilityNames),"; "),
            AttributionStatus=if List.IsEmpty(FacilityKeys) then "Historical scope query match - institutional scope needs review" else "Affiliation search match - not manually verified",
            AttributionEvidence="Retrieved by PubMed affiliation search; not author-level verification. Queries: " & Text.Combine(List.Sort(List.Distinct(MatchedQueries & (if List.Contains(ScopeSearch[IDs],PMID) then {"""Cairns Public Health Unit""[Affiliation] - historical institutional scope requires review"} else {}))), " | "),
            PublicationNotice=Notice, FacilityMatchCount=List.Count(FacilityKeys), RefreshedAtUTC=RefreshedUTC
        ],
    PublicationRecords = List.Transform(RawRows, each ToPublication(_)),
    Publications = Table.Buffer(Table.FromRecords(PublicationRecords, type table [
        PMID=text,Title=text,Journal=text,Authors=text,DOI=nullable text,PubMedURL=text,
        PublicationDate=nullable date,PublicationDateRaw=text,PublicationDatePrecision=text,
        PublicationMonth=nullable text,PublicationYear=nullable number,OnlineDate=nullable date,OnlineDateRaw=text,
        AuthorCount=number,PublicationTypes=text,PublicationClass=text,IsClinicalTrial=logical,IsEvidenceSynthesis=logical,
        MatchedFacilities=text,AttributionStatus=text,AttributionEvidence=text,PublicationNotice=text,FacilityMatchCount=number,RefreshedAtUTC=datetime
    ])),
    VerifiedPublications = if Table.RowCount(Publications) <> List.Count(AllIDs) or List.Count(List.Distinct(Publications[PMID])) <> List.Count(AllIDs) then error "Final publication row count mismatch" else Publications,
    AuditRows = List.Transform(SearchResults & {ScopeSearch}, (s) => [FacilityKey=s[FacilityKey], SearchCount=s[SearchCount], QueryTranslation=s[QueryTranslation], Warnings=s[Warnings], QueryVersion="2026-09-11-v2", RefreshedAtUTC=RefreshedUTC]),
    SearchAudit = Table.FromRecords(AuditRows, type table [FacilityKey=text,SearchCount=number,QueryTranslation=text,Warnings=text,QueryVersion=text,RefreshedAtUTC=datetime])
in
    [Publications=VerifiedPublications, Matches=Matches, SearchAudit=SearchAudit, IDs=AllIDs]
