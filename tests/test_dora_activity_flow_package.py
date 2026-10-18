import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

from scripts.build_dora_activity_flow_package import build_package


class DoraActivityFlowPackageTests(unittest.TestCase):
    def test_private_package_injects_target_without_placeholders(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            output = Path(folder) / "dora.zip"
            build_package(output, site_url="https://example.sharepoint.com/personal/example_operator", list_id=str(uuid.uuid4()), flow_id=str(uuid.uuid4()), connection_display_name="DEV SharePoint")
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                definition = json.loads(archive.read(next(n for n in names if n.endswith("/definition.json"))))
                text = json.dumps(definition)
                self.assertNotIn("{{", text)
                self.assertIn("shared_sharepointonline", text)
                self.assertNotIn("shared_onedriveforbusiness", text)
                self.assertIn("item/DORAActivityKey", text)
                self.assertIn("item/PI_x0020_Email", text)

    def test_rejects_invalid_target_or_connection(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            with self.assertRaises(ValueError):
                build_package(Path(folder) / "bad.zip", site_url="http://example.org", list_id=str(uuid.uuid4()), flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaises(ValueError):
                build_package(Path(folder) / "bad.zip", site_url="https://example.org", list_id="bad", flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaises(ValueError):
                build_package(Path(folder) / "bad.zip", site_url="https://example.org", list_id=str(uuid.uuid4()), flow_id=str(uuid.uuid4()), connection_display_name=False)

    def test_rejects_non_string_target_parameters(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            output = Path(folder) / "bad.zip"
            with self.assertRaisesRegex(ValueError, "must be strings"):
                build_package(output, site_url=None, list_id=str(uuid.uuid4()),
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaisesRegex(ValueError, "must be strings"):
                build_package(output, site_url="https://example.org", list_id=None,
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaisesRegex(ValueError, "must be a string"):
                build_package(output, site_url="https://example.org", list_id=str(uuid.uuid4()),
                              flow_id=str(uuid.uuid4()), connection_display_name=None)

    def test_rejects_definition_drift_before_writing_package(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            definition_path = Path(folder) / "drift.json"
            definition = json.loads((Path(__file__).parents[1] / "config/flows/dora-activity-registry-upsert.definition.json").read_text())
            del definition["properties"]["definition"]["actions"]["Apply_to_each_DORA_Activity"]["actions"]["SharePoint_Get_items"]
            definition_path.write_text(json.dumps(definition))
            with self.assertRaisesRegex(ValueError, "contract failed"):
                build_package(Path(folder) / "bad.zip", site_url="https://example.org", list_id=str(uuid.uuid4()), flow_id=str(uuid.uuid4()), connection_display_name="DEV", definition_path=definition_path)


if __name__ == "__main__":
    unittest.main()
