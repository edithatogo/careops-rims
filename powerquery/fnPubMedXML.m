// Full PubMed XML metadata; no author-level institutional conclusion is inferred.
(ids as list) as table =>
let
    EmptyNodes = #table(type table [Name=nullable text,Namespace=nullable text,Value=any,Attributes=any],{}),
    Nodes = (v as any) as table => if Value.Is(v,type table) then v else EmptyNodes,
    Children = (v as any, name as text) as list => Table.SelectRows(Nodes(v),each [Name]=name)[Value],
    Child = (v as any, name as text) as any => List.First(Children(v,name),null),
    // Iterative depth-first traversal preserves mixed-content text order.
    TextValue = (v as any) as text => Text.Combine(List.RemoveNulls(List.Generate(
        ()=>[Todo={v},Out=null], each not List.IsEmpty([Todo]) or [Out]<>null,
        each if List.IsEmpty([Todo]) then [Todo={},Out=null] else
            let Head=List.First([Todo]),Tail=List.Skip([Todo])
            in if Value.Is(Head,type table) then [Todo=Head[Value]&Tail,Out=null] else [Todo=Tail,Out=if Head=null then null else Text.From(Head)],
        each [Out])),""),
    DateText = (v as any) as text => let Medline=Child(v,"MedlineDate") in if Medline<>null then TextValue(Medline) else Text.Combine(List.Select(List.Transform({"Year","Month","Day"},each TextValue(Child(v,_))),each _<>"")," "),
    RetryCodes={408,429,500,502,503,504},
    Contact=if pNCBIEmail=null then "" else Text.Trim(pNCBIEmail),
    Common=[db="pubmed",retmode="xml",tool="CHHHSResearchPublications",id=Text.Combine(ids,",")],
    Parameters=if Contact="" then Common else Record.AddField(Common,"email",Contact),
    Fetch=(n as number) as record => let
        Body=Function.InvokeAfter(()=>Web.Contents("https://eutils.ncbi.nlm.nih.gov",[RelativePath="entrez/eutils/efetch.fcgi",Query=Parameters,Timeout=#duration(0,0,2,0),ManualStatusHandling=RetryCodes,IsRetry=n>0]),#duration(0,0,0,if n=0 then 1.1 else Number.Power(2,n))),
        Status=Record.FieldOrDefault(Value.Metadata(Body),"Response.Status",200)
        in [Status=Status,Body=Binary.Buffer(Body)],
    Attempts=List.Generate(()=>[N=0,R=Fetch(0)],each [N]<=4,each if List.Contains(RetryCodes,[R][Status]) and [N]<4 then [N=[N]+1,R=Fetch([N]+1)] else [N=5,R=null],each [R]),
    Final=List.Last(Attempts),
    XML=if Final[Status]<>200 then error "PubMed EFetch failed after bounded retries" else Xml.Document(Final[Body]),
    Root=Child(XML,"PubmedArticleSet"),
    Articles=Children(Root,"PubmedArticle"),
    Books=Children(Root,"PubmedBookArticle"),
    Checked=if Root=null or List.Count(Books)>0 then error "Unexpected PubMed XML structure; preserve and review unsupported records" else Articles,
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
    Reconciled=if List.Count(Returned)<>List.Count(ids) or List.Count(List.Distinct(Returned))<>List.Count(ids) or not List.IsEmpty(List.Difference(ids,Returned)) or not List.IsEmpty(List.Difference(Returned,ids)) then error "EFetch requested and returned PMID sets do not reconcile" else Result
in
    Reconciled
