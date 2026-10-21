import base64,copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_relationship_evidence import project,orcid_status

def packet(authors=None,awards=None):
 w={'id':'https://openalex.org/W1','doi':'https://doi.org/10.1234/test','authorships':authors or [],'awards':awards or []};b=json.dumps(w).encode();return {'work_id':w['id'],'requested_doi':'10.1234/test','raw_response_base64':base64.b64encode(b).decode(),'raw_response_sha256':hashlib.sha256(b).hexdigest(),'observed_utc':'2026-10-20T00:00:00Z'}
def author(i,name='Same Name',institutions=None,orcid=None):return {'author':{'id':f'https://openalex.org/A{i}' if i else None,'display_name':name,'orcid':orcid},'institutions':institutions or []}
PUB=[{'DOI':'10.1234/test','CanonicalKey':'pub:1'}]
class SourceEvidenceTests(unittest.TestCase):
 def test_same_name_distinct_ids_and_unresolved_excluded_from_pairs(self):
  r=project([packet([author(1),author(2),author(None)])],PUB)
  self.assertEqual(sum(x['RelationshipKind']=='coauthorship' for x in r),1)
  self.assertEqual(sum(x['IdentityStatus']=='Unresolved identity' for x in r),1)
 def test_duplicate_identical_authorships_do_not_multiply_pairs(self):
  r=project([packet([author(1),author(1),author(2)])],PUB)
  self.assertEqual(sum(x['RelationshipKind']=='authorship' for x in r),2)
  self.assertEqual(sum(x['RelationshipKind']=='coauthorship' for x in r),1)
 def test_ambiguous_doi_retains_evidence_without_canonical_admission(self):
  r=project([packet([author(1)])],PUB+[{'DOI':'https://doi.org/10.1234/test','CanonicalKey':'pub:2'}])
  self.assertTrue(all(x['CanonicalKey']=='' and x['CanonicalMatchCount']==2 for x in r))
 def test_concurrent_affiliations_are_publication_specific(self):
  inst=[{'id':'https://openalex.org/I1','display_name':'One','ror':'https://ror.org/abc'},{'id':'https://openalex.org/I2','display_name':'Two'}]
  r=project([packet([author(1,institutions=inst)])],PUB)
  self.assertEqual(sum(x['RelationshipKind']=='publication_affiliation' for x in r),2)
  self.assertEqual(sum(x['RelationshipKind']=='institution_cooccurrence' for x in r),1)
  self.assertTrue(all(x['AuthenticationState']=='Not authenticated' and x['ReviewState']=='Not reviewed' for x in r))
 def test_multiple_awards_and_equal_numbers_different_funders_remain_distinct(self):
  awards=[{'funder_id':f'https://openalex.org/F{i}','funder_award_id':'123'} for i in [1,2]]
  r=project([packet(awards=awards)],PUB);self.assertEqual(sum(x['RelationshipKind']=='publication_award' for x in r),2)
 def test_hash_mismatch_rejected_and_source_immutable(self):
  e=packet();before=copy.deepcopy(e);project([e],PUB);self.assertEqual(e,before)
  e['raw_response_sha256']='0'*64
  with self.assertRaises(ValueError):project([e],PUB)
 def test_missing_projects_never_inferred_from_award_or_name(self):
  r=project([packet([author(1)],awards=[{'id':'https://openalex.org/G1'}])],PUB)
  self.assertFalse(any('project' in x['RelationshipKind'] for x in r))
 def test_orcid_checksum_is_not_authentication(self):
  self.assertEqual(orcid_status('0000-0002-1825-0097'),'Valid syntax; unauthenticated')
  self.assertEqual(orcid_status('0000-0002-1825-0098'),'Invalid')

class StudyReferenceTests(unittest.TestCase):
 def test_reference_types_and_missing_identity_are_preserved(self):
  from source_relationship_evidence import study_references
  s={'protocolSection':{'identificationModule':{'nctId':'NCT00000001'},'referencesModule':{'references':[{'pmid':'12','type':'BACKGROUND'},{'pmid':'13','type':'DERIVED'},{'pmid':'14','type':'RESULT'}]}}}
  r=study_references([{'record':s,'raw':json.dumps(s).encode(),'observed_utc':'2026-10-20T00:00:00Z'}],[{'PMID':'13','CanonicalKey':'pub:13'}])
  self.assertEqual(len(r),2);self.assertEqual({x['ReferenceType'] for x in r},{'DERIVED','RESULT'})
  self.assertEqual(sum(bool(x['CanonicalKey']) for x in r),1)
  self.assertTrue(all(x['ToKey']=='clinicaltrials.gov:NCT00000001' for x in r))
 def test_repeated_project_reference_deduplicates_without_project_award_inference(self):
  from source_relationship_evidence import study_references
  ref={'pmid':'13','type':'RESULT'};s={'protocolSection':{'identificationModule':{'nctId':'NCT00000001','orgStudyIdInfo':{'id':'NHMRC123'}},'referencesModule':{'references':[ref,ref]}}}
  r=study_references([{'record':s,'raw':json.dumps(s).encode(),'observed_utc':'2026-10-20T00:00:00Z'}],[{'PMID':'13','CanonicalKey':'pub:13'}])
  self.assertEqual(len(r),1);self.assertEqual(r[0]['RelationshipKind'],'publication_study_reference')

class ConflictingIdentityTests(unittest.TestCase):
 def test_conflicting_valid_orcids_exclude_author_from_pairs(self):
  a=packet([author(1,orcid='0000-0002-1825-0097'),author(2)])
  b=packet([author(1,orcid='0000-0001-5109-3700'),author(3)])
  w=json.loads(base64.b64decode(b['raw_response_base64']));w['id']='https://openalex.org/W2';w['doi']='https://doi.org/10.1234/other';raw=json.dumps(w).encode();b.update(work_id=w['id'],requested_doi='10.1234/other',raw_response_base64=base64.b64encode(raw).decode(),raw_response_sha256=hashlib.sha256(raw).hexdigest())
  self.assertTrue(orcid_status('0000-0001-5109-3700').startswith('Valid'))
  r=project([a,b],PUB+[{'DOI':'10.1234/other','CanonicalKey':'pub:2'}]);self.assertFalse(any(x['RelationshipKind']=='coauthorship' for x in r));self.assertEqual(sum(x['IdentityStatus']=='Conflicting identifiers' for x in r),2)

def node(name,value,attrs=None):return {'Name':name,'Value':value,'Attributes':attrs or []}
def pm_record(authors,grants=None,dbs=None):
 tree=[node('MedlineCitation',[node('PMID','13'),node('Article',[node('AuthorList',authors),node('GrantList',grants or []),node('DataBankList',dbs or [])])])]
 return {'pmid':'13','metadata':tree,'source_version':'batch-accepted','observed_utc':'2026-10-20T00:00:00Z'}
def pm_author(orcid=None,affs=None,name='Same Label'):
 return node('Author',[node('LastName',name)]+([node('Identifier',orcid,[{'Name':'Source','Value':'ORCID'}])] if orcid else [])+(affs or []))
class PubMedExplicitEvidenceTests(unittest.TestCase):
 def test_only_author_bound_valid_orcids_create_people_pairs(self):
  from source_relationship_evidence import pubmed_projection
  rec=pm_record([pm_author('0000-0002-1825-0097'),pm_author('https://orcid.org/0000-0001-5109-3700'),pm_author('0000-0002-1825-0098'),pm_author()]);before=copy.deepcopy(rec)
  r=pubmed_projection([rec],[{'PMID':'13','CanonicalKey':'pub:13'}]);self.assertEqual(rec,before)
  self.assertEqual(sum(x['RelationshipKind']=='coauthorship' for x in r),1)
  self.assertEqual(sum(x['RelationshipKind']=='authorship' and x['IdentityStatus']=='Source-supported' for x in r),2)
  self.assertTrue(all(x['AuthenticationState']=='Not authenticated' and x['SourceVersion']=='batch-accepted' for x in r))
 def test_affiliation_variants_same_explicit_ringgold_id_remain_evidence(self):
  from source_relationship_evidence import pubmed_projection
  def af(label):return node('AffiliationInfo',[node('Affiliation',label),node('Identifier','123',[{'Name':'Source','Value':'RINGGOLD'}])])
  r=pubmed_projection([pm_record([pm_author('0000-0002-1825-0097',[af('Department One'),af('Department Two')])])],[{'PMID':'13','CanonicalKey':'pub:13'}])
  self.assertEqual(sum(x['RelationshipKind']=='publication_affiliation' for x in r),2)
  self.assertFalse(any(x['RelationshipKind']=='institution_cooccurrence' for x in r))
 def test_grants_are_explicit_source_scoped_and_unqualified_agency_is_unresolved(self):
  from source_relationship_evidence import pubmed_projection
  grants=[node('Grant',[node('GrantID','123'),node('Agency',agency),node('Country','AU')]) for agency in ['Funder A','Funder B','']]
  r=pubmed_projection([pm_record([],grants)],[{'PMID':'13','CanonicalKey':'pub:13'}]);g=[x for x in r if x['RelationshipKind']=='publication_grant_reference'];self.assertEqual(len(g),3);self.assertEqual(len({x['ToKey'] for x in g}),3);self.assertEqual(sum(x['IdentityStatus']=='Unresolved award namespace' for x in g),1)
 def test_trial_registry_ids_only_and_no_background_or_sequence_database_join(self):
  from source_relationship_evidence import pubmed_projection
  dbs=[node('DataBank',[node('DataBankName',name),node('AccessionNumberList',[node('AccessionNumber',value)])]) for name,value in [('ClinicalTrials.gov','NCT00000001'),('ANZCTR','ACTRN12605000411673'),('GENBANK','NCT00000002')]]
  r=pubmed_projection([pm_record([],dbs=dbs)],[{'PMID':'13','CanonicalKey':'pub:13'}]);links=[x for x in r if x['RelationshipKind']=='publication_study_reference'];self.assertEqual(len(links),2);self.assertEqual({x['ToKey'] for x in links},{'clinicaltrials.gov:NCT00000001','anzctr:ACTRN12605000411673'})
 def test_explicit_orcid_crosswalk_deduplicates_same_pair_across_providers(self):
  from source_relationship_evidence import pubmed_projection
  pubs=[{'PMID':'13','DOI':'10.1234/test','CanonicalKey':'pub:13'}]
  oa=project([packet([author(1,orcid='0000-0002-1825-0097'),author(2,orcid='0000-0001-5109-3700')])],pubs)
  pm=pubmed_projection([pm_record([pm_author('0000-0002-1825-0097',name='Other Display Label'),pm_author('0000-0001-5109-3700')])],pubs)
  pairs=[x for x in oa+pm if x['RelationshipKind']=='coauthorship'];self.assertEqual(len(pairs),2);self.assertEqual(len({(x['FromKey'],x['ToKey']) for x in pairs}),1)
