import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from scripts.build_native_retention_package import SOURCES, build_package


class NativeRetentionPackageTests(unittest.TestCase):
    def test_generated_package_is_keyset_verified_and_staging_only(self):
        definition = {
            "properties": {
                "definition": {
                    "triggers": {"manual": {"inputs": {"schema": {}}}},
                    "actions": {
                        "Run_a_query_against_a_dataset": {
                            "type": "OpenApiConnection",
                            "inputs": {"parameters": {"specification/query": "EVALUATE ROW(\"x\",1)"}},
                        },
                        "Create_file": {
                            "type": "OpenApiConnection",
                            "inputs": {"parameters": {}},
                        },
                        "Get_file_content_using_path": {
                            "type": "OpenApiConnection",
                            "inputs": {
                                "host": {"operationId": "GetFileContentByPath"},
                                "parameters": {},
                            },
                        },
                    },
                }
            }
        }
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            folder_path = Path(folder)
            baseline = folder_path / "baseline.zip"
            output = folder_path / "retention.zip"
            with zipfile.ZipFile(baseline, "w") as archive:
                archive.writestr("Microsoft.Flow/flows/example/definition.json", json.dumps(definition))
            action_count = build_package(baseline, output)
            self.assertGreater(action_count, len(SOURCES))
            with zipfile.ZipFile(output) as archive:
                name = next(item for item in archive.namelist() if item.endswith("/definition.json"))
                result = json.loads(archive.read(name))
            actions = result["properties"]["definition"]["actions"]
            self.assertIn("Staging_only", actions)
            text = json.dumps(actions)
            self.assertIn("UNCOMMITTED", text)
            self.assertNotIn("PROMOTED", text)
            self.assertNotIn("Commit", text)
            for table in SOURCES:
                self.assertIn(f"{table}_Expected_keys", actions)
                self.assertIn(f"{table}_Final_keys", actions)
                self.assertIn(f"{table}_Require_complete_keyset", actions)
                self.assertIn(f"{table}_Require_exact_readback", text)
                acceptance = actions[f"{table}_Require_complete_keyset"]["inputs"]
                self.assertIn("KEYSET_VERIFIED", acceptance)
                self.assertIn("SOURCE_KEYSET_MISMATCH", acceptance)
                self.assertIn("intersection", acceptance)


if __name__ == "__main__":
    unittest.main()
