"""Build and verify a reproducible source-only release archive.

Tenant snapshots, private configuration, Git history and native recovery
packages are intentionally excluded. They require a separate private backup
route and are never implied by this source release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

try:
    from project_utils import ROOT, save_json
except ModuleNotFoundError:  # import through the repository package during tests
    from scripts.project_utils import ROOT, save_json

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
EXCLUDED_PREFIXES = ("private/", "downloads/canonical_live_artifacts/")
EXCLUDED_SUFFIXES = (".zip", ".bundle")
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def run(args: list[str], cwd: Path = ROOT) -> str:
    process = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if process.returncode:
        raise RuntimeError(f"Command failed ({process.returncode}): {args}\n{process.stdout}\n{process.stderr}")
    return (process.stdout + process.stderr).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_stable_entry(target: zipfile.ZipFile, name: str, content: bytes) -> None:
    """Write a deterministic ZIP member independent of the current clock."""
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    target.writestr(info, content)


def validate_version(version: str) -> str:
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("version must use MAJOR.MINOR.PATCH with an optional preview suffix")
    return version


def validate_identity(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def source_paths(root: Path = ROOT) -> list[Path]:
    """Return tracked source files eligible for a source archive."""
    try:
        names = run(["git", "ls-files", "-z"], root).split("\0")
    except RuntimeError:
        # A source archive intentionally has no .git directory.  Walk the
        # extracted tree so its local validation can still be self-contained.
        names = [path.relative_to(root).as_posix() for path in root.rglob("*")
                 if path.is_file() and not (set(path.relative_to(root).parts) & EXCLUDED_DIRS)
                 and ".git" not in path.parts]
    paths = []
    for name in names:
        if not name:
            continue
        normalised = name.replace("\\", "/")
        if normalised == "RELEASE-MANIFEST.json" or normalised.startswith(EXCLUDED_PREFIXES):
            continue
        if normalised.endswith(EXCLUDED_SUFFIXES):
            continue
        path = root / name
        if path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_manifest(paths: list[Path], version: str, schema_version: str, batch_id: str,
                   root: Path = ROOT) -> dict:
    validate_version(version)
    schema_version = validate_identity(schema_version, "schema_version")
    batch_id = validate_identity(batch_id, "batch_id")
    try:
        head = run(["git", "rev-parse", "HEAD"], root)
        dirty = bool(run(["git", "status", "--porcelain"], root))
    except RuntimeError:
        head = "source-archive"
        dirty = False
    return {
        "SoftwareVersion": version,
        "SchemaVersion": schema_version,
        "AcceptedBatchID": batch_id,
        "SourceCommit": head,
        "DirtyBuild": dirty,
        "NativeAcceptance": False,
        "Files": [
            {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}
            for path in paths
        ],
    }


def package(output: Path, version: str = "0.3.0-rc1", schema_version: str = "publication-platform-v1",
            accepted_batch_id: str = "local-source", root: Path = ROOT) -> dict:
    """Create a clean-tree source archive and verify a fresh extraction."""
    output.mkdir(parents=True, exist_ok=True)
    version = validate_version(version)
    if run(["git", "status", "--porcelain"], root):
        raise RuntimeError("Commit or isolate changes before making a reproducible release")
    paths = source_paths(root)
    manifest = build_manifest(paths, version, schema_version, accepted_batch_id, root)
    archive = output / f"CHHHS-Research-Publications-v{version}-Source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for path in paths:
            write_stable_entry(
                target,
                "chhhs-research-publications/" + path.relative_to(root).as_posix(),
                path.read_bytes(),
            )
        write_stable_entry(
            target,
            "chhhs-research-publications/RELEASE-MANIFEST.json",
            (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        )

    with tempfile.TemporaryDirectory(prefix="chhhs-release-") as temporary:
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(temporary)
            names = {name.replace("\\", "/") for name in zipped.namelist()}
        extracted = Path(temporary) / "chhhs-research-publications"
        if any(name.endswith("/.git") or "/.git/" in name for name in names):
            raise RuntimeError("source archive must not contain .git")
        if any(name.startswith("chhhs-research-publications/private/") or
               name.startswith("chhhs-research-publications/downloads/canonical_live_artifacts/")
               for name in names):
            raise RuntimeError("source archive contains private/runtime artefacts")
        extracted_manifest = json.loads((extracted / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
        if extracted_manifest != manifest:
            raise RuntimeError("fresh extraction manifest differs")
        run([sys.executable, "scripts/validate_project.py"], extracted)
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], extracted)

    receipt = {
        **manifest,
        "Archive": {"path": archive.name, "sha256": digest(archive), "bytes": archive.stat().st_size},
        "FreshExtractionVerified": True,
        "ContainsGitHistory": False,
        "ContainsPrivateRuntime": False,
    }
    save_json(output / f"CHHHS-Research-Publications-v{version}-Source-receipt.json", receipt)
    print(json.dumps(receipt, indent=2))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent)
    parser.add_argument("--version", default="0.3.0-rc1")
    parser.add_argument("--schema-version", default="publication-platform-v1")
    parser.add_argument("--accepted-batch-id", default="local-source")
    args = parser.parse_args()
    package(args.output_dir, args.version, args.schema_version, args.accepted_batch_id)
