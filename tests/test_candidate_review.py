from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publication_registry import Registry
from review_publication_candidates import recommendations, apply_supported_recommendations

class ReviewTests(unittest.TestCase):
 def test_geographic_context_and_preserved_exclusion(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Registry(Path(tmp)/'r.sqlite','synthetic')
   records=[{'source':'pubmed','source_record_id':str(i),'pmid':str(i),'doi':None,'title':'Synthetic study','url':f'https://pubmed.ncbi.nlm.nih.gov/{i}/','authors':[{'name':'A','affiliations':[aff]}],'publication_date_parts':{'Year':'2024'}} for i,aff in enumerate(['Atherton Hospital, California','Atherton Hospital, Queensland, Australia'],1)]
   keys=db.ingest(records,'r','pubmed','2026-01-01T00:00:00Z','baseline')
   db.review(keys[1],'excluded','Existing decision','human','2026-01-01T00:00:00Z')
   r=recommendations(db,{'rows':[{'Active':True,'FacilityName':'Atherton Hospital','PubMedQuery':'"Atherton Hospital"[Affiliation] AND Australia[Affiliation]'}]})
   by={x['CanonicalKey']:x for x in r['attribution']}
   self.assertEqual(by[keys[0]]['recommendation'],'needs_review')
   self.assertEqual(by[keys[1]]['recommendation'],'included')
   self.assertEqual(by[keys[1]]['current_status'],'excluded')
   self.assertEqual(len(r['duplicate_candidates']),1)
   self.assertEqual(apply_supported_recommendations(db,r,'2026-01-02T00:00:00Z'),0)
   self.assertEqual(next(x for x in db.records() if x['CanonicalKey']==keys[1])['ReviewStatus'],'excluded')
   db.close()
 def test_supported_application_is_idempotent(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Registry(Path(tmp)/'r.sqlite','synthetic')
   row={'source':'pubmed','source_record_id':'1','pmid':'1','title':'Synthetic','url':'https://pubmed.ncbi.nlm.nih.gov/1/','authors':[{'name':'A','affiliations':['Cairns Hospital']}],'publication_date_parts':{}}
   key=db.ingest([row],'r','pubmed','2026-01-01T00:00:00Z','baseline')[0]
   report=recommendations(db,{'rows':[{'Active':True,'FacilityName':'Cairns Hospital','PubMedQuery':'"Cairns Hospital"[Affiliation]'}]})
   self.assertEqual(apply_supported_recommendations(db,report,'2026-01-02T00:00:00Z'),1)
   self.assertEqual(apply_supported_recommendations(db,report,'2026-01-03T00:00:00Z'),0)
   self.assertEqual(db.records()[0]['ReviewStatus'],'included')
   self.assertEqual(db.records()[0]['CHHHSAffiliatedAuthors'],'A')
   db.close()
