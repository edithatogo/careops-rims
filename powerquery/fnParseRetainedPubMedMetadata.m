// Parse retained XML-shaped JSON without re-fetching PubMed.
// Source identity is checked against the durable observation key.
(History as table) as table =>
let
    EmptyNodes = #table(type table [Name=nullable text,Namespace=nullable text,Value=any,Attributes=any],{}),
    Nodes = (v as any) as table => if Value.Is(v,type table) then v else if Value.Is(v,type list) then Table.FromRecords(v) else EmptyNodes,
    Children = (v as any, name as text) as list => Table.SelectRows(Nodes(v),each [Name]=name)[Value],
    Child = (v as any, name as text) as any => List.First(Children(v,name),null),
    // Iterative depth-first traversal preserves mixed-content text order.
    TextValue = (v as any) as text => Text.Combine(List.RemoveNulls(List.Generate(
        ()=>[Todo={v},Out=null], each not List.IsEmpty([Todo]) or [Out]<>null,
        each if List.IsEmpty([Todo]) then [Todo={},Out=null] else
            let Head=List.First([Todo]),Tail=List.Skip([Todo])
            in if Value.Is(Head,type table) or Value.Is(Head,type list) then [Todo=Nodes(Head)[Value]&Tail,Out=null] else [Todo=Tail,Out=if Head=null then null else Text.From(Head)],
        each [Out])),""),
    DateText = (v as any) as text => let Medline=Child(v,"MedlineDate") in if Medline<>null then TextValue(Medline) else Text.Combine(List.Select(List.Transform({"Year","Month","Day"},each TextValue(Child(v,_))),each _<>"")," "),
    Selected=Table.SelectRows(History,each [Source]="PubMed"),
    IDs=Selected[SourceID],
    Checked=List.Transform(Table.ToRecords(Selected),(r)=>let
        Payload=Json.Document(r[MetadataJSON]),
        PMID=TextValue(Child(Child(Payload,"MedlineCitation"),"PMID"))
        in if PMID=r[SourceID] then Payload else error "Retained PubMed payload identity mismatch"),
    Records=List.Transform(Checked,(v)=>let
        Citation=Child(v,"MedlineCitation"), Article=Child(Citation,"Article"), Journal=Child(Article,"Journal"),
        Authors=List.Transform(Children(Child(Article,"AuthorList"),"Author"),(a)=>[
            Name=if Child(a,"CollectiveName")<>null then TextValue(Child(a,"CollectiveName")) else Text.Combine(List.Select({if Child(a,"ForeName")=null then TextValue(Child(a,"Initials")) else TextValue(Child(a,"ForeName")),TextValue(Child(a,"LastName")),TextValue(Child(a,"Suffix"))},each _<>"")," "),
            Affiliations=List.Transform(Children(a,"AffiliationInfo"),each TextValue(Child(_,"Affiliation"))) ]),
        RawDate=DateText(Child(Child(Journal,"JournalIssue"),"PubDate")),
        ArticleDates=Children(Article,"ArticleDate"),
        ParsedDate=fnParsePubDate(RawDate),
        AbstractNodes=Children(Child(Article,"Abstract"),"AbstractText"),
        Types=Children(Child(Article,"PublicationTypeList"),"PublicationType")
        in [PMID=TextValue(Child(Citation,"PMID")),FullTitle=TextValue(Child(Article,"ArticleTitle")),FullJournal=TextValue(Child(Journal,"Title")),
            FullAuthors=Text.Combine(List.Transform(Authors,each [Name]),"; "),FullAuthorCount=List.Count(Authors),
            AuthorAffiliationsJSON=Text.FromBinary(Json.FromValue(Authors),TextEncoding.Utf8),
            FullAbstract=Text.Combine(List.Transform(AbstractNodes,each TextValue(_)),"#(lf)"),
            IssueDateRaw=RawDate,IssueDatePrecision=ParsedDate[Precision],IssueDate=ParsedDate[Date],
            ArticleDatesJSON=Text.FromBinary(Json.FromValue(ArticleDates),TextEncoding.Utf8),
            FullPublicationTypes=Text.Combine(List.Transform(Types,each TextValue(_)),"; "),
            FullMetadataJSON=Text.FromBinary(Json.FromValue(v),TextEncoding.Utf8)]),
    Result=Table.FromRecords(Records,type table [PMID=text,FullTitle=text,FullJournal=text,FullAuthors=text,FullAuthorCount=number,AuthorAffiliationsJSON=text,FullAbstract=text,IssueDateRaw=text,IssueDatePrecision=text,IssueDate=nullable date,ArticleDatesJSON=text,FullPublicationTypes=text,FullMetadataJSON=text]),
    Returned=Result[PMID],
    Reconciled=if List.Count(Returned)<>List.Count(IDs) or List.Count(List.Distinct(Returned))<>List.Count(IDs) or not List.IsEmpty(List.Difference(IDs,Returned)) or not List.IsEmpty(List.Difference(Returned,IDs)) then error "Retained PubMed parsed keys do not reconcile" else Result
in
    Reconciled
