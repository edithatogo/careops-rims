import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_pubmed import parse_records

ARTICLE = '<PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>A <i>test</i> title</ArticleTitle><Journal><Title>Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal><AuthorList><Author><LastName>Smith</LastName><ForeName>A</ForeName><AffiliationInfo><Affiliation>Example Hospital</Affiliation></AffiliationInfo></Author></AuthorList></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/TEST</ArticleId></ArticleIdList></PubmedData></PubmedArticle>'
class Tests(unittest.TestCase):
 def test_dates_are_not_invented(self):
  r=parse_records(('<PubmedArticleSet>'+ARTICLE+'</PubmedArticleSet>').encode())[0]
  self.assertEqual(r['publication_date_parts'], {'Year':'2024'})
  self.assertEqual(r['title'], 'A test title')
  self.assertEqual(r['doi'], '10.1234/test')
  self.assertEqual(r['authors'][0]['affiliations'], ['Example Hospital'])
  self.assertEqual(r['review_status'],'needs_review')
 def test_error_is_not_empty_success(self):
  with self.assertRaises(ValueError): parse_records(b'<ERROR>failed</ERROR>')
 def test_duplicate_is_not_counted_twice(self):
  with self.assertRaises(ValueError): parse_records(('<PubmedArticleSet>'+ARTICLE*2+'</PubmedArticleSet>').encode())
 def test_conflicting_doi_is_rejected(self):
  a=ARTICLE.replace('</ArticleIdList>','<ArticleId IdType="doi">10.1234/OTHER</ArticleId></ArticleIdList>')
  with self.assertRaises(ValueError): parse_records(('<PubmedArticleSet>'+a+'</PubmedArticleSet>').encode())
 def test_unsupported_records_are_not_silently_dropped(self):
  with self.assertRaises(ValueError): parse_records(b'<PubmedArticleSet><PubmedBookArticle/></PubmedArticleSet>')
if __name__ == '__main__': unittest.main()
