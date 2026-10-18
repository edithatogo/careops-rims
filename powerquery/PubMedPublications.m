let
    Summary=PubMedHarvest[Publications],
    Joined=Table.NestedJoin(Summary,{"PMID"},PubMedFullMetadata,{"PMID"},"Full",JoinKind.LeftOuter),
    Verified=if List.AnyTrue(List.Transform(Joined[Full],each Table.RowCount(_)<>1)) then error "PubMed summary/full metadata join is not one-to-one" else Joined,
    Records=List.Transform(Table.ToRecords(Verified),(r)=>let
        F=r[Full]{0},Parsed=fnParsePubDate(F[IssueDateRaw]),D=if Parsed[Date]=null then null else if Date.Year(Parsed[Date])<1900 then null else Parsed[Date],
        Precision=if Parsed[Date]<>null and D=null then "outside-model-range" else Parsed[Precision],
        Base=Record.RemoveFields(r,{"Full","Title","Journal","Authors","AuthorCount","PublicationDate","PublicationDateRaw","PublicationDatePrecision","PublicationMonth","PublicationYear","AttributionEvidence"}),
        Added=[Title=F[FullTitle],Journal=F[FullJournal],Authors=F[FullAuthors],AuthorCount=F[FullAuthorCount],Abstract=F[FullAbstract],
            PublicationDate=D,PublicationDateRaw=F[IssueDateRaw],PublicationDatePrecision=Precision,PublicationYear=Parsed[Year],
            PublicationMonth=if D<>null and List.Contains({"day","month"},Precision) then Date.ToText(D,"yyyy-MM","en-AU") else null,
            AttributionEvidence=r[AttributionEvidence]&" Full author-level source statements retained separately in PubMedAuthorEvidence; no automatic institutional approval."]
        in Record.Combine({Base,Added})),
    Columns=Table.ColumnNames(Summary)&{"Abstract"},
    Result=Table.FromRecords(Records,Columns,MissingField.Error),
    Typed=Table.TransformColumnTypes(Result,{{"PMID",type text},{"Title",type text},{"Journal",type text},{"Authors",type text},{"DOI",type text},{"PubMedURL",type text},{"PublicationDate",type date},{"PublicationDateRaw",type text},{"PublicationDatePrecision",type text},{"PublicationMonth",type text},{"PublicationYear",Int64.Type},{"OnlineDate",type date},{"OnlineDateRaw",type text},{"AuthorCount",Int64.Type},{"PublicationTypes",type text},{"PublicationClass",type text},{"IsClinicalTrial",type logical},{"IsEvidenceSynthesis",type logical},{"MatchedFacilities",type text},{"AttributionStatus",type text},{"AttributionEvidence",type text},{"PublicationNotice",type text},{"FacilityMatchCount",Int64.Type},{"RefreshedAtUTC",type datetime},{"Abstract",type text}})
in Typed
