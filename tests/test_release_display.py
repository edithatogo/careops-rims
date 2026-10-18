import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ReleaseDisplayTests(unittest.TestCase):
    def test_release_metadata_has_explicit_non_acceptance_state(self):
        metadata = json.loads((ROOT / 'config/release-metadata.json').read_text())
        self.assertEqual(metadata['SchemaVersion'], 'publication-platform-v1')
        self.assertTrue(metadata['SoftwareVersion'])
        self.assertTrue(metadata['AcceptedBatchID'])
        self.assertFalse(metadata['NativeAcceptance'])

    def test_report_builder_exposes_release_metadata_columns(self):
        source = (ROOT / 'scripts/build_report.py').read_text()
        self.assertIn("ReleaseMetadata", source)
        self.assertIn("release-version", source)
        self.assertIn("release-batch", source)


if __name__ == '__main__':
    unittest.main()
