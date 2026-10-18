import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.grants_source_probe import MAX_BYTES, probe_catalogue, probe_universities
from scripts.grants_sources import load_catalogue


ROOT = Path(__file__).resolve().parents[1]


class _Response:
    def __init__(self, body=b"<html><title>Example</title></html>", status=200, url="https://example.test"):
        self.body = body
        self.status = status
        self.url = url
        self.headers = {"Content-Type": "text/html"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url


class GrantsSourceProbeTests(unittest.TestCase):
    def test_probe_is_bounded_and_does_not_promote_page_to_feed(self):
        body = b"<title>Authority</title>" + (b"x" * (MAX_BYTES + 100))
        with patch("scripts.grants_source_probe.urllib.request.urlopen", return_value=_Response(body)) as opener:
            result = probe_catalogue(ROOT / "config/grants-sources.json", opener=opener)
        self.assertEqual(len(result["results"]), len(load_catalogue(ROOT / "config/grants-sources.json")))
        self.assertTrue(all(row["promoted_to_feed"] is False for row in result["results"]))
        self.assertTrue(all(row["truncated"] is True for row in result["results"]))
        self.assertEqual(result["feed_acceptance"], "not_proven_by_authority_probe")

    def test_transport_failure_is_preserved(self):
        def fail(*args, **kwargs):
            raise OSError("offline")

        with patch("scripts.grants_source_probe.urllib.request.urlopen", side_effect=fail) as opener:
            result = probe_catalogue(ROOT / "config/grants-sources.json", opener=opener)
        self.assertTrue(all(row["status"] is None and row["error"] == "transport_error" for row in result["results"]))

    def test_university_catalogue_uses_same_conservative_probe(self):
        with patch("scripts.grants_source_probe.urllib.request.urlopen", return_value=_Response()) as opener:
            result = probe_universities(ROOT / "config/grants-universities.json", opener=opener)
        self.assertEqual(len(result["results"]), 4)
        self.assertTrue(all(row["promoted_to_feed"] is False for row in result["results"]))

    def test_university_probe_reuses_strict_catalogue_validation(self):
        rows = json.loads((ROOT / "config/grants-universities.json").read_text())
        rows[0]["institution_id"] = " jcu"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with patch("scripts.grants_source_probe.urllib.request.urlopen") as opener:
                with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                    probe_universities(handle.name, opener=opener)
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
