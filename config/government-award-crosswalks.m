// Exact original funding identifiers joined to historical government application records.
(ReadFile as function, ArchiveBase as text, ExpectedBatch as text, TrustedUpstreamSHA256 as text) as list =>
let
    M=Json.Document(ReadFile(ArchiveBase&"/manifest.json")),
    Manifest=if M[kind]="historical_nhmrc_crossref_retention_v1" and M[batch]=ExpectedBatch and M[namespace]="nhmrc" and M[complete]=true and List.Count(List.Distinct(List.Transform(M[files],each [name])))=List.Count(M[files]) then M else error "Government crosswalk manifest drift",
    Info=(Name as text) as record => let Fs=List.Select(Manifest[files],each [name]=Name) in if List.Count(Fs)=1 and not Text.Contains(Name,"/") and not Text.Contains(Name,"\") and Name<>".." then Fs{0} else error "Government source filename drift",
    Raw=(Ref as record) as binary => let F=Info(Ref[name]),B=Binary.Buffer(ReadFile(ArchiveBase&"/"&F[name])) in if Ref[sha256]=F[sha256] and Binary.Length(B)=F[bytes] then B else error "Government source provenance or length drift",
    Authority=Json.Document(Raw(Manifest[authority])),
    ROR=if List.AnyTrue(List.Transform(Authority[links],each [type]="website" and [value]="https://www.nhmrc.gov.au/")) then Authority[id] else error "Government NHMRC namespace authority drift",
    Funders=List.Buffer(List.Combine(List.Transform(List.Select(Authority[external_ids],each [type]="fundref"),each List.Transform([all],(N)=>"10.13039/"&N)))),
    Upstream=Json.Document(Raw(Manifest[source_manifest])),Spec=Manifest[workbook],
    UpstreamFiles=List.Select(Upstream[files],each [name]=Spec[name]),
    URL=Uri.Parts(Spec[source_url]),
    Valid=Upstream[format]="rims-funding-native-workbook-commit-v1" and Upstream[source]="nhmrc" and Upstream[complete]=true and Upstream[fidelity]="original_binary_content_exact_saved_readback" and List.Count(UpstreamFiles)=1 and UpstreamFiles{0}[source_url]=Spec[source_url] and URL[Scheme]="https" and URL[Host]="www.nhmrc.gov.au" and Text.StartsWith(Spec[source_url],"https://www.nhmrc.gov.au/sites/default/files/") and not Text.Contains(Spec[source_url],"?") and not Text.Contains(Spec[source_url],"#") and Spec[sheet]="GRANTS DATA" and Spec[id_column]="APP ID",
    UpstreamFile=if Valid then UpstreamFiles{0} else error "Official historical workbook identity drift",
    HasDirect=Record.HasFields(UpstreamFile,{"sha256","bytes"}),
    Anchor=if HasDirect then Manifest[source_manifest] else if Record.HasFields(Manifest,"source_retention") then Manifest[source_retention] else error "Upstream workbook byte binding missing",
    Trusted=Text.Length(TrustedUpstreamSHA256)=64 and Text.Select(TrustedUpstreamSHA256,{"0".."9","a".."f"})=TrustedUpstreamSHA256 and Anchor[sha256]=TrustedUpstreamSHA256,
    Receipt=if not Trusted then error "External upstream authority digest mismatch" else if HasDirect then null else Json.Document(Raw(Anchor)),
    Original=if HasDirect then {} else List.Select(Receipt[files],each [name]="manifest.json"),
    Retained=if HasDirect then {} else List.Select(Receipt[files],each [name]=Spec[name]),
    ReceiptValid=if HasDirect then true else Receipt[status]="PASS_NATIVE_ORIGINAL_WORKBOOK_ARCHIVE" and Record.HasFields(Upstream,"run") and Upstream[run]<>"" and Receipt[run]=Upstream[run] and List.Count(Original)=1 and List.Count(Retained)=1 and Original{0}[sha256]=Manifest[source_manifest][sha256] and Original{0}[bytes]=Info(Manifest[source_manifest][name])[bytes] and Retained{0}[matches_original_CLI_capture]=true,
    Binding=if not Trusted then error "External upstream authority digest mismatch" else if HasDirect then UpstreamFile else if ReceiptValid then Retained{0} else error "Upstream retention identity or binding drift",
    Bound=Record.HasFields(Binding,{"sha256","bytes"}) and Binding[sha256]=Spec[sha256] and Binding[bytes]=Info(Spec[name])[bytes] and Value.Is(Binding[bytes],type number),
    Workbook=if Bound then Excel.Workbook(Raw(Spec),null,true) else error "Upstream workbook digest or length missing or different",
    Sheets=Table.SelectRows(Workbook,each [Kind]="Sheet" and [Item]=Spec[sheet]),
    Data=if Table.RowCount(Sheets)=1 then Table.ToRows(Sheets{0}[Data]) else error "Historical workbook sheet missing or ambiguous",
    Headers=if List.Count(Data)>0 then Data{0} else error "Historical workbook has no header",
    IdentifierColumn=if List.Count(List.Select(Headers,each _=Spec[id_column]))=1 then List.PositionOf(Headers,Spec[id_column]) else error "Unique historical identifier column required",
    ExactID=(V as any) as nullable text => if Value.Is(V,type number) then if V>=0 and Number.RoundDown(V)=V then Number.ToText(V,"0","en-US") else null else if Value.Is(V,type text) then if V<>"" and Text.Trim(V)=V then V else null else null,
    Records=List.Buffer(List.Transform(List.Positions(List.Skip(Data,1)),(I)=>[ID=ExactID(Data{I+1}{IdentifierColumn}),Row=I+2])),
    DOI=(S as text) as text => let T=Text.Lower(Text.Trim(S)),Ps={"https://doi.org/","http://doi.org/","https://dx.doi.org/","http://dx.doi.org/"},P=List.First(List.Select(Ps,each Text.StartsWith(T,_)),null),D=if P=null then T else Text.Range(T,Text.Length(P)),Issuer=try Text.BeforeDelimiter(D,"/") otherwise "",Digits=if Text.StartsWith(Issuer,"10.") then Text.Range(Issuer,3) else "",Suffix=try Text.AfterDelimiter(D,"/") otherwise "" in if Text.Length(Digits)>=4 and Text.Length(Digits)<=9 and Text.Select(Digits,{"0".."9"})=Digits and Suffix<>"" and Text.Remove(D,{" ","#(tab)","#(cr)","#(lf)"})=D then D else "",
    JSON=(R as record) as text => Text.FromBinary(Json.FromValue(R),TextEncoding.Utf8),
    DOIs=List.Transform(Manifest[crossref],each DOI([doi])),
    Queries=if not List.Contains(DOIs,"") and List.Count(DOIs)=List.Count(List.Distinct(DOIs)) then Manifest[crossref] else error "Unique Crossref DOI source required",
    Rows=List.Buffer(List.Combine(List.Transform(Queries,(Q)=>let
        Response=Json.Document(Raw(Q)),D=DOI(Q[doi]),
        Work=if Response[status]="ok" and DOI(Response[message][DOI])=D then Response[message] else error "Crossref publication identity drift",
        Funding=List.Select(Record.FieldOrDefault(Work,"funder",{}),each List.Contains(Funders,DOI(Record.FieldOrDefault(_,"DOI","")))),
        Assertions=List.Combine(List.Transform(Funding,(F)=>List.Transform(Record.FieldOrDefault(F,"award",{}),(N)=>[Number=N,Funder=DOI(F[DOI])]))),
        Edges=List.Combine(List.Transform(Assertions,(A)=>let
            N=A[Number],Matches=if Value.Is(N,type text) and N=ExactID(N) then List.Select(Records,each [ID]=N) else {},
            Source="crossref:"&D,Target=if Value.Is(N,type text) then "nhmrc:"&N else "",
            Provenance=[relationship="explicit_crossref_funding_to_historical_application",recordKind="historical_nhmrc_application",funderDOI=A[Funder],originalAwardNumber=N,authorityROR=ROR,authorityRawSHA256=Manifest[authority][sha256],workbookSourceURL=Spec[source_url],workbookRawSHA256=Spec[sha256],sourceManifestSHA256=Manifest[source_manifest][sha256],workbookSheet=Spec[sheet],identifierColumn=Spec[id_column],workbookRow=if List.Count(Matches)=1 then Matches{0}[Row] else null,retentionBatch=ExpectedBatch]
            in if List.Count(Matches)=0 then {} else if List.Count(Matches)<>1 then error "Ambiguous historical application identifier" else
            {[EvidenceKey=Text.Combine({Source,"publication_government_award_reference","doi:"&D,Target},"|"),RelationshipKind="publication_government_award_reference",SourceWorkID=Source,PublicationDOI=D,PublicationPMID="",ReferenceType=JSON(Provenance),FromKey="doi:"&D,ToKey=Target,FromLabel=A[Funder],ToLabel=N,ORCID="",ORCIDStatus="Absent",ROR=ROR,IdentityStatus="Source-supported",SourceURL=Q[url],ObservedUTC=Q[observed_utc],RawSHA256=Q[sha256],SourceVersion=ExpectedBatch,ReviewState="Not reviewed",AuthenticationState="Not authenticated"]}))
        in Edges))),
    Unique=List.Distinct(Rows),Keys=List.Transform(Unique,each [EvidenceKey])
in if List.Count(Keys)=List.Count(List.Distinct(Keys)) then Unique else error "Conflicting historical government application assertion"
