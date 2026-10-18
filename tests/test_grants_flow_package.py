import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

from scripts.build_grants_flow_package import build_package


class GrantsFlowPackageTests(unittest.TestCase):
    def test_private_package_injects_target_without_placeholders(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            output = Path(folder) / "grants.zip"
            build_package(
                output,
                site_url="https://example.sharepoint.com/personal/example_operator",
                list_id=str(uuid.uuid4()),
                flow_id=str(uuid.uuid4()),
                connection_display_name="DEV SharePoint",
            )
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("Microsoft.Flow/flows/manifest.json", names)
                definition = json.loads(archive.read(next(n for n in names if n.endswith("/definition.json"))))
                text = json.dumps(definition)
                self.assertNotIn("{{", text)
                self.assertIn("shared_sharepointonline", text)
                self.assertNotIn("shared_onedriveforbusiness", text)
                create = definition["properties"]["definition"]["actions"]["Apply_to_each_Reviewed_Row"]["actions"]["Condition_Is_New_Opportunity"]["actions"]["SharePoint_Create_item"]["inputs"]["parameters"]
                update = definition["properties"]["definition"]["actions"]["Apply_to_each_Reviewed_Row"]["actions"]["Condition_Is_New_Opportunity"]["else"]["actions"]["Condition_Exactly_One_Opportunity"]["actions"]["SharePoint_Update_item"]["inputs"]["parameters"]
                self.assertIsInstance(create["item/DeadlinePrecision"], dict)
                self.assertEqual(create["item/DeadlinePrecision"]["Value"], "@{item()?['DeadlinePrecision']}")
                self.assertIsInstance(create["item/Status"], dict)
                self.assertIsInstance(create["item/CHHHSRelevance"], dict)
                self.assertEqual(create["item/URL"], "@{item()?['URL']}")
                self.assertEqual(create["item/SourceRowURL"], "@{item()?['SourceRowURL']}")
                self.assertEqual(update["item/OpportunityKey"], "@{item()?['OpportunityKey']}")

    def test_rejects_non_guid_list(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            with self.assertRaises(ValueError):
                build_package(Path(folder) / "x.zip", site_url="https://example.org", list_id="bad",
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")

    def test_rejects_malformed_site_url(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            with self.assertRaisesRegex(ValueError, "concrete HTTPS SharePoint site URL"):
                build_package(Path(folder) / "x.zip", site_url="https://", list_id=str(uuid.uuid4()),
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")

    def test_rejects_non_string_target_parameters(self):
        private_root = Path(__file__).parents[1] / "private"
        private_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root) as folder:
            output = Path(folder) / "x.zip"
            with self.assertRaisesRegex(ValueError, "must be strings"):
                build_package(output, site_url=None, list_id=str(uuid.uuid4()),
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaisesRegex(ValueError, "must be strings"):
                build_package(output, site_url="https://example.org", list_id=None,
                              flow_id=str(uuid.uuid4()), connection_display_name="DEV")
            with self.assertRaisesRegex(ValueError, "must be a GUID"):
                build_package(output, site_url="https://example.org", list_id=str(uuid.uuid4()),
                              flow_id="bad", connection_display_name="DEV")
            with self.assertRaisesRegex(ValueError, "must be a string"):
                build_package(output, site_url="https://example.org", list_id=str(uuid.uuid4()),
                              flow_id=str(uuid.uuid4()), connection_display_name=None)


if __name__ == "__main__":
    unittest.main()
