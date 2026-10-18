let
    Rows=List.Combine(List.Transform(Table.ToRecords(PubMedFullMetadata),(r)=>let
        Authors=Json.Document(r[AuthorAffiliationsJSON])
        in List.Combine(List.Transform(List.Positions(Authors),(i)=>let A=Authors{i},Affiliations=if List.IsEmpty(A[Affiliations]) then {null} else A[Affiliations]
            in List.Transform(List.Positions(Affiliations),(j)=>[PMID=r[PMID],AuthorIndex=i+1,AuthorName=A[Name],AffiliationIndex=j+1,AffiliationText=Affiliations{j},EvidenceKind="PubMed XML author affiliation; institutional scope not automatically approved"]))))),
    Result=Table.FromRecords(Rows,type table [PMID=text,AuthorIndex=number,AuthorName=text,AffiliationIndex=number,AffiliationText=nullable text,EvidenceKind=text])
in Result
