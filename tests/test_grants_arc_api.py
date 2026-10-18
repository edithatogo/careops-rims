import unittest

from scripts.grants_arc_api import parse_award_page, fetch_award_page


class GrantsArcApiTests(unittest.TestCase):
    def test_awards_are_typed_and_not_opportunities(self):
        records = parse_award_page({"data": [{
            "id": "FT260100001",
            "attributes": {
                "code": "FT260100001",
                "scheme-name": "ARC Future Fellowships",
                "grant-summary": "Award summary",
                "current-funding-amount": 100,
                "grant-status": "Active",
            },
            "links": {"self": "https://dataportal.arc.gov.au/NCGP/API/grants/FT260100001"},
        }]}, retrieved_at="2026-09-20T03:36:00+00:00")
        self.assertEqual(records[0]["RecordKind"], "Award")
        self.assertEqual(records[0]["SourceID"], "FT260100001")
        self.assertNotIn("OpportunityKey", records[0])

    def test_fetch_uses_bounded_page_and_preserves_meta(self):
        class Response:
            headers = {"Content-Type": "application/json"}
            def getcode(self): return 200
            def read(self, limit):
                self.limit = limit
                return b'{"meta":{"total-size":1},"data":[]}'
            def __enter__(self): return self
            def __exit__(self, *args): return False

        calls = []
        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return Response()

        result = fetch_award_page(page_size=1, retrieved_at="2026-09-20T03:36:00+00:00", opener=opener)
        self.assertEqual(result["record_kind"], "awards_only")
        self.assertEqual(result["meta"]["total-size"], 1)
        self.assertIn("page%5Bsize%5D=1", result["api_url"])
        self.assertEqual(calls[0][1], 20)

    def test_invalid_page_size_fails_closed(self):
        with self.assertRaises(ValueError):
            fetch_award_page(page_size=1001, opener=lambda *_args, **_kwargs: None)

    def test_malformed_award_fields_are_not_coerced(self):
        payload = {"data": [{
            "id": "FT260100002",
            "attributes": {"code": ["bad"], "grant-summary": "Summary"},
            "links": {"self": "https://dataportal.arc.gov.au/award/2"},
        }]}
        with self.assertRaisesRegex(ValueError, "award code/id"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")

        payload["data"][0]["attributes"]["code"] = "FT260100002"
        payload["data"][0]["links"] = {"self": 7}
        with self.assertRaisesRegex(ValueError, "evidence URL"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")

        payload["data"][0]["links"] = {"self": "https://"}
        with self.assertRaisesRegex(ValueError, "evidence URL"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")

        payload["data"][0]["links"] = {"self": "https://dataportal.arc.gov.au/award/2"}
        payload["data"][0]["attributes"]["current-funding-amount"] = [100]
        with self.assertRaisesRegex(ValueError, "current-funding-amount"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")

    def test_award_identity_and_evidence_url_reject_surrounding_whitespace(self):
        payload = {"data": [{
            "id": "FT260100003",
            "attributes": {"code": " FT260100003", "grant-summary": "Summary"},
            "links": {"self": "https://dataportal.arc.gov.au/award/3"},
        }]}
        with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")
        payload["data"][0]["attributes"]["code"] = "FT260100003"
        payload["data"][0]["links"]["self"] = "https://dataportal.arc.gov.au/award/3 "
        with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
            parse_award_page(payload, retrieved_at="2026-09-20T03:36:00+00:00")


if __name__ == "__main__":
    unittest.main()
