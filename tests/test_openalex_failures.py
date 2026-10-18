import json
import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import enrich_openalex as oa

class Response(BytesIO):
    status=200
    def __init__(self,data): super().__init__(json.dumps(data).encode())

class FailureHandling(unittest.TestCase):
    def test_exact_doi_full_fields_and_private_header(self):
        payload={'doi':'https://doi.org/10.1000/test','unknown_future_field':{'x':[1,None]},'cited_by_count':0}
        with patch.object(oa,'_api_key',return_value='test-secret'),patch.object(oa,'_open_request',return_value=Response(payload)) as request:
            result=oa.fetch_openalex_observation('10.1000/test')
        self.assertEqual(result.payload,payload)
        self.assertEqual(request.call_args.args[0].get_header('Authorization'),'Bearer test-secret')
        self.assertNotIn('test-secret',request.call_args.args[0].full_url)

    def test_auth_denial_no_retry_and_old_values_preserved(self):
        err=urllib.error.HTTPError('private-url',401,'secret error',{},None)
        record={'DOI':'10.1000/test','CitationCount_OpenAlex':12,'CitationMetricsObservedUTC':'old'}
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',side_effect=err) as request,patch.object(oa.time,'sleep') as sleep:
            oa.enrich_record_with_openalex(record)
        self.assertEqual(record['CitationCount_OpenAlex'],12)
        self.assertEqual(record['CitationMetricsObservedUTC'],'old')
        self.assertEqual(record['OpenAlexAttemptStatus'],'access_denied')
        self.assertEqual(request.call_count,1);sleep.assert_not_called()

    def test_transient_recovers_with_finite_backoff(self):
        err=urllib.error.HTTPError('x',503,'x',{'Retry-After':'1'},None)
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',side_effect=[err,Response({'doi':'10.1000/test'})]),patch.object(oa.time,'sleep') as sleep:
            result=oa.fetch_openalex_observation('10.1000/test')
        self.assertEqual(result.status,'success');self.assertEqual(result.attempts,2);sleep.assert_called_once_with(1)

    def test_long_rate_limit_stops_without_early_retry(self):
        err=urllib.error.HTTPError('x',429,'x',{'Retry-After':'3600'},None)
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',side_effect=err) as request,patch.object(oa.time,'sleep') as sleep:
            result=oa.fetch_openalex_observation('10.1000/test')
        self.assertEqual(result.status,'rate_limited');self.assertEqual(request.call_count,1);sleep.assert_not_called()

    def test_outage_stops_at_three_attempts(self):
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',side_effect=TimeoutError) as request,patch.object(oa.time,'sleep') as sleep:
            result=oa.fetch_openalex_observation('10.1000/test')
        self.assertEqual(result.status,'unavailable');self.assertEqual(request.call_count,3);self.assertEqual(sleep.call_count,2)

    def test_not_found_is_distinct_from_outage(self):
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',side_effect=urllib.error.HTTPError('x',404,'x',{},None)):
            self.assertEqual(oa.fetch_openalex_observation('10.1000/test').status,'not_found')

    def test_wrong_doi_rejects_metadata(self):
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',return_value=Response({'doi':'10.1000/foreign'})):
            result=oa.fetch_openalex_observation('10.1000/test')
        self.assertEqual(result.status,'identity_mismatch');self.assertIsNone(result.payload)

    def test_partial_batch_discards_all_rows(self):
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',return_value=Response({'meta':{'count':2},'results':[{'doi':'10.1000/test'}]})):
            self.assertEqual(oa.fetch_openalex_batch(['10.1000/test','10.1000/other']),{})

    def test_malformed_response_no_success(self):
        response=BytesIO(b'<html>maintenance</html>');response.status=200
        with patch.object(oa,'_api_key',return_value=None),patch.object(oa,'_open_request',return_value=response):
            self.assertEqual(oa.fetch_openalex_observation('10.1000/test').status,'invalid_response')

    def test_redirect_cannot_forward_bearer(self):
        self.assertIsNone(oa._NoRedirect().redirect_request(None,None,302,'',{},'https://other.example/'))

class CandidatePreservation(unittest.TestCase):
    def test_failed_fetch_retains_values_and_input_bytes(self):
        import tempfile
        import prepare_openalex_enrichment as prep
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); private=root/'private/ops';private.mkdir(parents=True)
            source=private/'source.json';output=private/'candidate.json'
            source.write_text(json.dumps([{'DOI':'10.1000/test','CanonicalKey':'existing','CitationCount_OpenAlex':12,'CitationMetricsObservedUTC':'old'}]))
            frozen=source.read_bytes()
            with patch.object(prep,'ROOT',root),patch.object(prep,'fetch_openalex_observation',return_value=oa.OpenAlexObservation('unavailable',attempts=3)):
                summary=prep.prepare(source,output)
                with self.assertRaises(ValueError):prep.prepare(source,output)
            data=json.loads(output.read_text())
            self.assertEqual(summary['failures'],1)
            self.assertEqual(data['candidate_records'][0]['CitationCount_OpenAlex'],12)
            self.assertEqual(data['candidate_records'][0]['CitationMetricsObservedUTC'],'old')
            self.assertEqual(source.read_bytes(),frozen)
            self.assertEqual(output.stat().st_mode & 0o777,0o600)

    def test_access_denial_stops_remaining_requests(self):
        import tempfile
        import prepare_openalex_enrichment as prep
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);private=root/'private/ops';private.mkdir(parents=True)
            source=private/'source.json';source.write_text(json.dumps([{'DOI':'10.1000/a'},{'DOI':'10.1000/b'}]))
            with patch.object(prep,'ROOT',root),patch.object(prep,'fetch_openalex_observation',return_value=oa.OpenAlexObservation('access_denied')) as fetch:
                summary=prep.prepare(source,private/'candidate.json')
            self.assertEqual(fetch.call_count,1);self.assertEqual(summary['records_preserved'],2)
