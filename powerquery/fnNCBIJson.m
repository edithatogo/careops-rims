(endpoint as text, parameters as record, optional attempt as nullable number) as record =>
let
    Start = if attempt = null then 0 else attempt,
    Common = [db="pubmed", retmode="json", tool="CHHHSResearchPublications"],
    Contact = if pNCBIEmail = null then "" else Text.Trim(pNCBIEmail),
    WithEmail = if Contact = "" then Common else if not Text.Contains(Contact,"@") then error "pNCBIEmail must be blank or a valid operational contact" else Record.AddField(Common,"email",Contact),
    QueryParameters = Record.Combine({WithEmail,parameters}),
    RetryCodes = {408,429,500,502,503,504},
    Fetch = (n as number) as record =>
        let
            Body = Function.InvokeAfter(() => Web.Contents("https://eutils.ncbi.nlm.nih.gov", [RelativePath="entrez/eutils/" & endpoint, Query=QueryParameters, Timeout=#duration(0,0,2,0), ManualStatusHandling=RetryCodes, IsRetry=n>0]),#duration(0,0,0,if n=0 then 1.1 else Number.Power(2,n))),
            Status = Record.FieldOrDefault(Value.Metadata(Body),"Response.Status",200)
        in [Status=Status,Body=Binary.Buffer(Body)],
    Attempts = List.Generate(() => [N=Start,R=Fetch(Start)], each [N]<=4,
        each if List.Contains(RetryCodes,[R][Status]) and [N]<4 then [N=[N]+1,R=Fetch([N]+1)] else [N=5,R=null], each [R]),
    Final = List.Last(Attempts),
    Parsed = if Final[Status]<>200 then error Error.Record("PubMedHTTP","NCBI request failed after bounded retries; no successful empty result is substituted.",[Status=Final[Status],Endpoint=endpoint]) else Json.Document(Final[Body]),
    Result = if not Value.Is(Parsed,type record) then error "Unexpected NCBI JSON response" else if Record.HasFields(Parsed,"error") then error Error.Record("PubMedAPI",Text.From(Parsed[error]),null) else Parsed
in
    Result
