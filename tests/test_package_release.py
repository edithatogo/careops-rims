import unittest
import io
import tempfile
import zipfile
from pathlib import Path

from scripts.package_release import build_manifest, source_paths, validate_version, write_stable_entry


class PackageReleaseTests(unittest.TestCase):
    def test_version_requires_semver_with_optional_preview(self):
        self.assertEqual(validate_version("0.3.0-rc1"), "0.3.0-rc1")
        with self.assertRaises(ValueError):
            validate_version("v0.3")
        with self.assertRaisesRegex(ValueError, "version must use"):
            validate_version(None)
        with self.assertRaisesRegex(ValueError, "version must use"):
            validate_version(3)

    def test_source_paths_exclude_runtime_archives(self):
        names = {path.as_posix() for path in source_paths()}
        self.assertFalse(any("downloads/canonical_live_artifacts/" in name for name in names))
        self.assertFalse(any(name.endswith((".zip", ".bundle")) for name in names))

    def test_manifest_separates_software_schema_and_batch_identity(self):
        manifest = build_manifest([], "0.3.0-rc1", "publication-platform-v1", "batch-local")
        self.assertEqual(manifest["SoftwareVersion"], "0.3.0-rc1")
        self.assertEqual(manifest["SchemaVersion"], "publication-platform-v1")
        self.assertEqual(manifest["AcceptedBatchID"], "batch-local")
        self.assertIn("DirtyBuild", manifest)
        self.assertFalse(manifest["NativeAcceptance"])

    def test_manifest_rejects_empty_schema_or_batch_identity(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            build_manifest([], "0.3.0-rc1", "", "batch-local")
        with self.assertRaisesRegex(ValueError, "batch_id"):
            build_manifest([], "0.3.0-rc1", "publication-platform-v1", "")

    def test_zip_member_timestamp_is_stable(self):
        first = io.BytesIO()
        second = io.BytesIO()
        for stream in (first, second):
            with zipfile.ZipFile(stream, "w") as archive:
                write_stable_entry(archive, "example.txt", b"content")
        self.assertEqual(first.getvalue(), second.getvalue())

    def test_source_path_fallback_excludes_tool_caches(self):
        from scripts.package_release import source_paths
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "main.py").write_text("pass\n", encoding="utf-8")
            (root / "scripts" / "__pycache__").mkdir()
            (root / "scripts" / "__pycache__" / "main.cpython-314.pyc").write_bytes(b"cache")
            (root / ".pytest_cache").mkdir()
            (root / ".pytest_cache" / "state").write_text("cache\n", encoding="utf-8")
            names = {path.relative_to(root).as_posix() for path in source_paths(root)}
            self.assertEqual(names, {"scripts/main.py"})


if __name__ == "__main__":
    unittest.main()
