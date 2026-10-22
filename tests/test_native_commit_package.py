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

    def test_validation_absence_and_readback_fail_closed_before_dependent_write(self):
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
            self.assertIn("int('COMMIT_VALIDATION_FAILED')", actions["Require_validation"]["inputs"])
            self.assertIn("int('COMMIT_READBACK_FAILED')", actions["Verify_commit_readback"]["inputs"])
            self.assertEqual(actions['Read_existing_commit']['runAfter'], {'Require_validation': ['Succeeded']})
            self.assertEqual(actions['Require_commit_absent']['runAfter'], {'Read_existing_commit': ['Succeeded', 'Failed']})
            self.assertIn("equals(outputs('Read_existing_commit')?['statusCode'],404)", actions['Require_commit_absent']['inputs'])
            self.assertIn("int('COMMIT_ALREADY_EXISTS_OR_READ_FAILED')", actions['Require_commit_absent']['inputs'])
            self.assertEqual(actions['Create_file']['runAfter'], {'Require_commit_absent': ['Succeeded']})
            self.assertEqual(actions['Get_file_content_using_path']['runAfter'], {'Create_file': ['Succeeded']})
            self.assertEqual(actions['Get_file_content_using_path']['inputs']['parameters']['path'],
                             actions['Create_file']['inputs']['parameters']['folderPath'] + '/' + actions['Create_file']['inputs']['parameters']['name'])
            frozen = output.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Preserve the existing package'):
                build(baseline, output, "00000000-0000-4000-8000-7ac1b8d7010b")
            self.assertEqual(output.read_bytes(), frozen)


if __name__ == "__main__":
    unittest.main()
