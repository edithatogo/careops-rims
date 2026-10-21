// Typed grant-registry related publications; not an assertion of reviewed funding.
(ReadFile as function, ArchiveBase as text, ExpectedBatch as text) as list =>
let
    M=Json.Document(ReadFile(ArchiveBase&"/manifest.json")),
    Manifest=if M[kind]="ardc_publication_handle_retention_v1" and M[batch]=ExpectedBatch and M[namespace]="nhmrc" and M[complete]=true and List.Count(List.Distinct(List.Transform(M[files],each [name])))=List.Count(M[files]) then M else error "Registry publication manifest identity drift",
    Info=(Name as text) as record => let Fs=List.Select(Manifest[files],each [name]=Name) in if List.Count(Fs)=1 and not Text.Contains(Name,"/") and not Text.Contains(Name,"\") and Name<>".." then Fs{0} else error "Registry publication source filename drift",
    Raw=(Name as text) as binary => let F=Info(Name),B=Binary.Buffer(ReadFile(ArchiveBase&"/"&Name)) in if Binary.Length(B)=F[bytes] then B else error "Registry publication source length drift",
    AuthorityInfo=Info(Manifest[authority][name]),
    Authority=if Manifest[authority][sha256]=AuthorityInfo[sha256] then Json.Document(Raw(AuthorityInfo[name])) else error "Registry authority provenance drift",
    ROR=if List.AnyTrue(List.Transform(Authority[links],each [type]="website" and [value]="https://www.nhmrc.gov.au/")) then Authority[id] else error "Registry NHMRC namespace authority drift",
    Funders=List.Buffer(List.Combine(List.Transform(List.Select(Authority[external_ids],each [type]="fundref"),each List.Transform([all],(N)=>"10.13039/"&N)))),
    DOI=(S as text) as text => let T=Text.Lower(Text.Trim(S)),Ps={"https://doi.org/","http://doi.org/","https://dx.doi.org/","http://dx.doi.org/"},P=List.First(List.Select(Ps,each Text.StartsWith(T,_)),null),D=if P=null then T else Text.Range(T,Text.Length(P)),Issuer=try Text.BeforeDelimiter(D,"/") otherwise "",Digits=if Text.StartsWith(Issuer,"10.") then Text.Range(Issuer,3) else "",Suffix=try Text.AfterDelimiter(D,"/") otherwise "" in if Text.Length(Digits)>=4 and Text.Length(Digits)<=9 and Text.Select(Digits,{"0".."9"})=Digits and Suffix<>"" and Text.Remove(D,{" ","#(tab)","#(cr)","#(lf)"})=D then D else "",
    OAI="http://www.openarchives.org/OAI/2.0/",
    RIF="http://ands.org.au/standards/rif-cs/registryObjects",
    Nodes=(T as any,N as text,NS as text) as table => if Value.Is(T,type table) then Table.SelectRows(T,each [Name]=N and [Namespace]=NS) else #table({"Name","Namespace","Value","Attributes"},{}),
    One=(T as table,N as text,NS as text) as record => let R=Nodes(T,N,NS) in if Table.RowCount(R)=1 then R{0} else error "Registry XML node missing or ambiguous",
    Children=(R as record,N as text,NS as text) as table => Nodes(R[Value],N,NS),
    Child=(R as record,N as text,NS as text) as record => One(R[Value],N,NS),
    TextValue=(R as record) as text => if Value.Is(R[Value],type text) then R[Value] else error "Registry XML identifier is not a text leaf",
    Attribute=(R as record,N as text) as text => let A=if Value.Is(R[Attributes],type table) then Table.SelectRows(R[Attributes],each [Name]=N) else #table({"Name","Value"},{}) in if Table.RowCount(A)=1 then A{0}[Value] else "",
    Grants=List.Buffer(List.Transform(Manifest[grants],(G)=>let
        Number=G[original_identifier],URI="https://purl.org/au-research/grants/nhmrc/"&Number,
        Lookup=Json.Document(Raw(G[ardc_name])),LD=Lookup[data],
        Matches=if Lookup[status]="OK" and Lookup[code]="200" and LD[offset]=0 and LD[numFound]=List.Count(LD[records]) then List.Select(LD[records],each Record.FieldOrDefault(_,"type","")="grant" and Record.FieldOrDefault(_,"purl","")=URI and List.Contains(Record.FieldOrDefault(_,"identifiers",{}),Number)) else error "Registry canonical grant lookup incomplete",
        Root=One(Xml.Document(Raw(G[rifcs_name])),"OAI-PMH",OAI),
        Record=if Table.RowCount(Children(Root,"error",OAI))=0 then Child(Child(Root,"GetRecord",OAI),"record",OAI) else error "Registry OAI error response",
        Header=Child(Record,"header",OAI),
        Object=Child(Child(Child(Record,"metadata",OAI),"registryObjects",RIF),"registryObject",RIF),
        Activity=Child(Object,"activity",RIF),
        Numbers=List.Transform(List.Select(Table.ToRecords(Children(Activity,"identifier",RIF)),each Attribute(_,"type")="nhmrc"),each TextValue(_)),
        Funding=List.Transform(List.Select(Table.ToRecords(Children(Activity,"relatedObject",RIF)),each List.AnyTrue(List.Transform(Table.ToRecords(Children(_,"relation",RIF)),(R)=>Attribute(R,"type")="isFundedBy"))),each DOI(TextValue(Child(_,"key",RIF)))),
        Valid=G[grant_uri]=URI and List.Count(Matches)=1 and Attribute(Header,"status")<>"deleted" and TextValue(Child(Header,"identifier",OAI))="oai:ands.org.au::"&G[record_id] and Attribute(Activity,"type")="grant" and Numbers={Number} and List.AnyTrue(List.Transform(Funding,each List.Contains(Funders,_))),
        Refs=List.Distinct(List.Combine(List.Transform(List.Select(Table.ToRecords(Children(Activity,"relatedInfo",RIF)),each Attribute(_,"type")="publication"),each List.Transform(List.Select(Table.ToRecords(Children(_,"identifier",RIF)),(I)=>Attribute(I,"type")="URI"),each TextValue(_)))))
        in if Valid then [Spec=G,References=Refs,Version=TextValue(Child(Header,"datestamp",OAI))] else error "Registry grant/funder/record identifier drift")),
    JSON=(R as record) as text => Text.FromBinary(Json.FromValue(R),TextEncoding.Utf8),
    Rows=List.Buffer(List.Transform(Manifest[publications],(P)=>let
        Gs=List.Select(Grants,each [Spec][record_id]=P[record_id]),G=if List.Count(Gs)=1 then Gs{0} else error "Registry grant record missing or duplicated",Spec=G[Spec],
        Prefixes={"http://hdl.handle.net/","https://hdl.handle.net/","http://handle.unsw.edu.au/","https://handle.unsw.edu.au/"},URIs=List.Transform(Prefixes,each _&P[handle]),
        Item=Json.Document(Raw(P[name])),Kind=Record.FieldOrDefault(P,"metadata_kind","dspace"),
        Materials=if Kind="figshare" then Record.FieldOrDefault(Item,"related_materials",{}) else {},
        IdentifierValues=if Kind="dspace" then List.Transform(List.Combine(List.Transform({"dc.identifier.doi","unsw.identifier.doiPublisher"},each Record.FieldOrDefault(Item[metadata],_,{}))),each [value]) else if Kind="figshare" then List.Transform(List.Select(Materials,each Record.FieldOrDefault(_,"identifier_type","")="DOI" and Record.FieldOrDefault(_,"relation","")="IsIdenticalTo"),each [identifier]) else error "Unqualified repository metadata contract",
        Ds=List.Distinct(List.RemoveItems(List.Transform(IdentifierValues,each DOI(_)),{""})),
        ItemValid=if Kind="dspace" then Item[type]="item" and Item[id]=P[item_id] else if Kind="figshare" then Value.Is(Item[id],type number) and Number.RoundDown(Item[id])=Item[id] and Number.ToText(Item[id],"0","en-US")=P[item_id] and Item[is_public]=true and Item[is_confidential]=false and Item[defined_type_name]="journal contribution" else false,
        Valid=List.Contains(URIs,P[publication_uri]) and List.Contains(G[References],P[publication_uri]) and ItemValid and Item[handle]=P[handle] and List.Count(Ds)<=1 and (Kind<>"dspace" or List.Count(Ds)=1),
        D=if not Valid then error "Registry repository handle/DOI identity drift" else if List.Count(Ds)=1 then Ds{0} else "",Source="ardc:"&P[record_id],Identity=if D<>"" then "doi:"&D else "handle:"&P[handle],
        Provenance=[relationship="RIF-CS relatedInfo publication",publicationHandleURI=P[publication_uri],resolvedHandle=P[handle],repositoryItemID=P[item_id],repositoryDOI=D,repositoryMetadataKind=Kind,repositoryDOIState=if D<>"" then "Explicit repository DOI identity" else "No explicit identity-equivalent DOI",repositoryRelatedMaterials=Materials,repositoryMetadataSHA256=Info(P[name])[sha256],repositoryMetadataURL=P[final_url],grantIdentifierNamespace="nhmrc",grantOriginalIdentifier=Spec[original_identifier],ardcRawSHA256=Info(Spec[ardc_name])[sha256],authorityRawSHA256=AuthorityInfo[sha256],retentionBatch=ExpectedBatch]
        in [EvidenceKey=Text.Combine({Source,"grant_related_publication",Identity,Spec[grant_uri],P[publication_uri]},"|"),RelationshipKind="grant_related_publication",SourceWorkID=Source,PublicationDOI=D,PublicationPMID="",ReferenceType=JSON(Provenance),FromKey=Identity,ToKey=Spec[grant_uri],FromLabel=if D<>"" then D else P[handle],ToLabel=Spec[original_identifier],ORCID="",ORCIDStatus="Absent",ROR=ROR,IdentityStatus="Source-supported",SourceURL=Spec[rifcs_url],ObservedUTC=Manifest[qualified_utc],RawSHA256=Info(Spec[rifcs_name])[sha256],SourceVersion=G[Version],ReviewState="Not reviewed",AuthenticationState="Not authenticated"])),
    Keys=List.Transform(Rows,each [EvidenceKey])
in if List.Count(Keys)=List.Count(List.Distinct(Keys)) then Rows else error "Duplicate registry publication mapping"
