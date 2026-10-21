// Derive aliases from retained raw records, never from search/title similarity.
(ReadFile as function, ArchiveBase as text, ExpectedBatch as text, Works as list, SourceRows as list) as list =>
let
    Manifest=Json.Document(ReadFile(ArchiveBase&"/manifest.json")),
    Valid=Manifest[kind]="award_identifier_crosswalk_retention_v1" and Manifest[batch]=ExpectedBatch and Manifest[complete]=true,
    Queries=if Valid then Manifest[source_manifest] else error "Award alias manifest identity drift",
    Read=(Name as text) as record => let F=List.Select(Manifest[files],each [name]=Name),B=Binary.Buffer(ReadFile(ArchiveBase&"/"&Name)) in if List.Count(F)=1 and Binary.Length(B)=F{0}[bytes] then Json.Document(B) else error "Award alias file identity or length drift",
    ProviderID=(S as text,Kind as text) as text => let Prefix="https://openalex.org/"&Kind,N=if Text.StartsWith(S,Prefix) then Text.Range(S,Text.Length(Prefix)) else "" in if N<>"" and Text.Select(N,{"0".."9"})=N then S else "",
    RORRecord=Read("nhmrc-ror-raw.json"),
    AuthorityROR=if List.AnyTrue(List.Transform(RORRecord[links],each [type]="website" and [value]="https://www.nhmrc.gov.au/")) then RORRecord[id] else error "Award funder authority drift",
    QualifiedQueries=List.Transform(Queries,(Q)=>let D=Read(Q[identifier]&".json"),F=List.Select(Manifest[files],each [name]=Q[identifier]&".json"),Complete=Q[http_status]=200 and Q[complete]=true and D[status]="OK" and D[code]="200" and D[data][offset]=0 and D[data][numFound]=List.Count(D[data][records]) and List.Count(F)=1 in if Complete then [Number=Q[identifier],Records=D[data][records],SHA256=F{0}[sha256],ObservedUTC=Q[observed_utc],URL=Q[url]] else error "Award alias raw response incomplete"),
    Aliases=List.Combine(List.Transform(Works,(WR)=>let W=WR[Work],Awards=Record.FieldOrDefault(W,"awards",{}),Funders=Record.FieldOrDefault(W,"funders",{}) in List.RemoveNulls(List.Transform(Awards,(A)=>let
        N=Record.FieldOrDefault(A,"funder_award_id",""),FID=ProviderID(Record.FieldOrDefault(A,"funder_id",""),"F"),GID=ProviderID(Record.FieldOrDefault(A,"id",""),"G"),AwardKey=if GID<>"" then GID else if FID<>"" and N<>"" then FID&"/award/"&N else "",Fs=List.Select(Funders,each Record.FieldOrDefault(_,"id","")=FID and Record.FieldOrDefault(_,"ror","")=AuthorityROR),Qs=List.Select(QualifiedQueries,each [Number]=N),Qualified=List.Count(Fs)=1 and List.Count(Qs)=1,
        Q=if Qualified then Qs{0} else null,ExpectedURI="https://purl.org/au-research/grants/nhmrc/"&N,
        Matches=if Qualified then List.Select(Q[Records],each Record.FieldOrDefault(_,"type","")="grant" and Record.FieldOrDefault(_,"purl","")=ExpectedURI and List.Contains(Record.FieldOrDefault(_,"identifiers",{}),N)) else {},
        Source=if AwardKey="" then {} else List.Select(SourceRows,each [SourceWorkID]=W[id] and [RelationshipKind]="publication_award" and [ToKey]=AwardKey),
        Row=if List.Count(Matches)=1 and List.Count(Source)=1 then Record.TransformFields(Source{0},{{"EvidenceKey",each Text.Combine({W[id],"award_identifier_alias",AwardKey,ExpectedURI},"|")},{"RelationshipKind",each "award_identifier_alias"},{"FromKey",each AwardKey},{"ToKey",each ExpectedURI},{"FromLabel",each Source{0}[ToLabel]},{"ToLabel",each Matches{0}[title]},{"ReferenceType",each "Exact source funder ROR and original grant identifier; ARDC grant PURL"},{"ROR",each AuthorityROR},{"SourceURL",each Q[URL]},{"ObservedUTC",each Q[ObservedUTC]},{"RawSHA256",each Q[SHA256]},{"SourceVersion",each ExpectedBatch}}) else null
        in Row))))
in List.Buffer(Aliases)
