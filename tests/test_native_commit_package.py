import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_native_commit_package import build


class NativeCommitPackageTests(unittest.TestCase):
    def test_batch_identity_must_be_a_uuid_string(self):
        with self.assertRaisesRegex(ValueError, 'UUID string'):
            build(Path('baseline.zip'), Path('result.zip'), None)
        with self.assertRaisesRegex(ValueError, 'UUID string'):
            build(Path('baseline.zip'), Path('result.zip'), 'not-a-uuid')

    def test_failure_markers_are_text_expressions(self):
        definition = {
            "properties": {
                "definition": {
                    "triggers": {"manual": {"inputs": {"schema": {}}}},
                    "actions": {
                        "Run_a_query_against_a_dataset": {
                            "type": "OpenApiConnection",
                            "inputs": {"parameters": {"specification/query": "EVALUATE ROW(\"x\",1)"}},
                        },
                        "Create_file": {"type": "OpenApiConnection", "inputs": {"parameters": {}}},
                        "Get_file_content_using_path": {"type": "OpenApiConnection", "inputs": {"parameters": {}}},
                    },
                },
            }
        }
        private_dir = ROOT / "private"
        private_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_dir) as temp_dir:
            temp = Path(temp_dir)
            baseline = temp / "baseline.zip"
            output = temp / "result.zip"
            with zipfile.ZipFile(baseline, "w") as archive:
                archive.writestr("Microsoft.Flow/flows/example/definition.json", json.dumps(definition))
                archive.writestr("manifest.json", json.dumps({"details": {}, "resources": {}}))
            build(baseline, output, "00000000-0000-4000-8000-7ac1b8d7010b")
            with zipfile.ZipFile(output) as archive:
                name = next(name for name in archive.namelist() if name.endswith("/definition.json"))
                result = json.loads(archive.read(name))
            actions = result["properties"]["definition"]["actions"]
            self.assertIn("'COMMIT_VALIDATION_FAILED'", actions["Require_validation"]["inputs"])
            self.assertIn("'COMMIT_READBACK_FAILED'", actions["Verify_commit_readback"]["inputs"])
            self.assertNotIn("int('COMMIT_VALIDATION_FAILED')", actions["Require_validation"]["inputs"])
            self.assertNotIn("int('COMMIT_READBACK_FAILED')", actions["Verify_commit_readback"]["inputs"])


if __name__ == "__main__":
    unittest.main()
