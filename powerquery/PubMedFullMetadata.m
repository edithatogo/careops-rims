let
    IDs=List.Buffer(List.Sort(List.Distinct(PubMedHarvest[IDs]))),
    Batches=List.Split(IDs,100),
    Tables=List.Accumulate(Batches,{},(state,batch)=>let T=Table.Buffer(fnPubMedXML(batch)),N=Table.RowCount(T) in if N=List.Count(batch) then state&{T} else error "PubMed full metadata batch is incomplete"),
    Empty=type table [PMID=text,FullTitle=text,FullJournal=text,FullAuthors=text,FullAuthorCount=number,AuthorAffiliationsJSON=text,FullAbstract=text,IssueDateRaw=text,IssueDatePrecision=text,IssueDate=nullable date,ArticleDatesJSON=text,FullPublicationTypes=text,FullMetadataJSON=text],
    Result=Table.Combine(Tables,Empty),
    Verified=if Table.RowCount(Result)<>List.Count(IDs) or List.Count(List.Distinct(Result[PMID]))<>List.Count(IDs) then error "PubMed full metadata key reconciliation failed" else Result
in
    Verified
