import unittest
import json
import tempfile
from pathlib import Path

from scripts.grants_universities import load_universities


class GrantsUniversityTests(unittest.TestCase):
    def test_required_university_sources_are_explicitly_manual_until_access_proven(self):
        rows = load_universities(Path(__file__).parents[1] / "config/grants-universities.json")
        self.assertEqual({row["institution_id"] for row in rows}, {"jcu", "uq", "qut", "griffith"})
        self.assertTrue(all(row["intake"] == "manual_review" for row in rows))

    def test_unknown_university_lead_times_are_not_invented(self):
        rows = load_universities(Path(__file__).parents[1] / "config/grants-universities.json")
        by_id = {row["institution_id"]: row for row in rows}
        self.assertIsNone(by_id["qut"]["internal_lead_time"])
        self.assertIsNone(by_id["griffith"]["internal_lead_time"])
        self.assertEqual(by_id["jcu"]["internal_lead_time"]["major_schemes"], 20)

    def test_invalid_known_lead_time_is_rejected(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["internal_lead_time"]["major_schemes"] = -1
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "invalid lead-time value"):
                load_universities(handle.name)

    def test_boolean_lead_time_is_rejected(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["internal_lead_time"]["major_schemes"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "invalid lead-time value"):
                load_universities(handle.name)

    def test_fractional_lead_time_is_rejected(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["internal_lead_time"]["major_schemes"] = 2.5
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "non-integral lead-time"):
                load_universities(handle.name)

    def test_authority_url_and_verification_date_are_validated(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["authority_url"] = "not-a-url"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "valid authority URL"):
                load_universities(handle.name)

        rows[0]["authority_url"] = "https://example.org"
        rows[0]["last_verified"] = "not-a-date"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "invalid last_verified date"):
                load_universities(handle.name)

    def test_identity_rows_and_future_dates_fail_closed(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["institution_id"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "institution_id must be"):
                load_universities(handle.name)

        rows[0]["institution_id"] = "jcu"
        rows[0]["last_verified"] = "2999-01-01"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "future last_verified date"):
                load_universities(handle.name)

    def test_identity_rows_reject_surrounding_whitespace(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["institution_id"] = " jcu"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                load_universities(handle.name)

    def test_authority_url_rejects_surrounding_whitespace(self):
        rows = json.loads((Path(__file__).parents[1] / "config/grants-universities.json").read_text())
        rows[0]["authority_url"] = " https://example.org/authority"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(rows, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "valid authority URL"):
                load_universities(handle.name)


if __name__ == "__main__":
    unittest.main()
