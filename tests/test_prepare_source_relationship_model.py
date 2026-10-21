import base64,copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_source_relationship_model import prepare,TABLE
class ModelPreservationTests(unittest.TestCase):
 def test_preserves_source_review_and_unknown_parts_and_rejects_reapplication(self):
  def part(path,text):return {'path':path,'payload':base64.b64encode(text.encode()).decode(),'payloadType':'InlineBase64'}
  x={'definition':{'parts':[part('definition/model.tmdl','model Model\nref table Publication\n'),part('definition/relationships.tmdl',''),part('definition/tables/Study register.tmdl',"table 'Study register'\n\tpartition 'Study register' = m\n\t\tmode: import\n\t\tsource = let X = SharePoint.Tables(\"https://example.invalid/site\",[ApiVersion=15]) in X\n"),part('definition/tables/Publication.tmdl','table Publication\n\tcolumn DOI\n\t\tdataType: string\n\tpartition Publication = m\n\t\tmode: import\n\t\tsource = ExistingAcceptedSource'),part('definition/tables/ExistingReview.tmdl','Reviewed and rejected records preserved'),part('unknown.txt','preserve')]}}
  original=copy.deepcopy(x);y=prepare(x,'let StudyRows=__STUDY_REGISTER_SOURCE__ in StudyRows');self.assertEqual(x,original)
  before={p['path']:p['payload'] for p in x['definition']['parts']};after={p['path']:p['payload'] for p in y['definition']['parts']}
  for k in before:
   if k not in {'definition/model.tmdl','definition/relationships.tmdl','definition/tables/Publication.tmdl'}:self.assertEqual(before[k],after[k])
  new=base64.b64decode(after[f'definition/tables/{TABLE}.tmdl']).decode();self.assertIn('ALLNOBLANKROW(Publication[CanonicalKey]',new);self.assertNotIn('__STUDY_REGISTER_SOURCE__',new);self.assertIn('Publication[RelationshipDOIKey]',new)
  with self.assertRaises(ValueError):prepare(y,'let X=1 in X')
