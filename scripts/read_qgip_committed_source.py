"""Project review candidates from a downloaded Microsoft QGIP source commit.

Offline verification only: no network, service writes or canonical admission.
Reuse the existing adapter for source/schema/page/repeated-read qualification.
Native JSON values are retained; original HTTP transport bytes are not claimed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    from scripts import grants_qld_qgip_api as qgip
except ImportError:
    import grants_qld_qgip_api as qgip


def _load(path: Path, root: Path) -> tuple[dict, bytes]:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive file must stay within the downloaded commit")
    if not path.is_file() or path.stat().st_size > 4_000_000:
        raise ValueError("Archive file is missing or exceeds the bounded size")
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Archive file must contain a JSON object")
    return data, raw


def _key(uri: str, queries: dict) -> tuple:
    if (not isinstance(uri, str) or not uri.startswith(qgip.API_BASE)
            or urlsplit(uri).query or urlsplit(uri).fragment
            or not isinstance(queries, dict)
            or any(not isinstance(k, str) or type(v) not in (str, int)
                   for k, v in queries.items())):
        raise ValueError("Unexpected retained API request")
    return uri, tuple(sorted((k, str(v)) for k, v in queries.items()))


class _Response:
    """Adapter-compatible response of reserialized native JSON values."""

    def __init__(self, response):
        if (response.get("statusCode") != 200
                or not isinstance(response.get("body"), dict)):
            raise ValueError("Retained request did not produce a successful JSON body")
        self.body = json.dumps(response["body"], ensure_ascii=False).encode()
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return 200

    def read(self, size):
        return self.body[:size]


def read_commit(folder: Path, *, catalogue_path=qgip.DEFAULT_CATALOGUE) -> dict:
    """Read one complete native commit and preserve all original envelope values."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Downloaded commit directory required")
    manifest, manifest_bytes = _load(folder / "manifest.json", folder)
    expected = {"format": "rims-qgip-source-commit-v1", "source_id": qgip.SOURCE_ID,
                "resource_id": qgip.RESOURCE_ID, "package_id": qgip.PACKAGE_ID,
                "complete_reads": 2, "candidate_filter_applied": False,
                "canonical_admission": False, "schedule": "manual_only"}
    if any(type(manifest.get(k)) is not type(v) or manifest[k] != v
           for k, v in expected.items()):
        raise ValueError("Manifest source or candidate-only boundary changed")
    if not isinstance(manifest.get("run"), str) or not manifest["run"].strip():
        raise ValueError("Manifest lacks its native run identity")
    total = manifest.get("source_total")
    if type(total) is not int or not 0 <= total <= qgip.MAX_PAGES * qgip.PAGE_SIZE:
        raise ValueError("Manifest lacks a bounded exact source total")
    qgip._aware(manifest.get("committed_utc"))
    pages = max(1, (total + qgip.PAGE_SIZE - 1) // qgip.PAGE_SIZE)
    names = {f"{kind}_{phase}.json" for kind in ("Index", "Package", "Resource", "Schema")
             for phase in ("before", "after")}
    names |= {f"pass-{read}-offset-{offset}.json" for read in (1, 2)
              for offset in range(0, pages * qgip.PAGE_SIZE, qgip.PAGE_SIZE)}
    files = manifest.get("files")
    if (not isinstance(files, list) or len(files) != len(names)
            or any(not isinstance(f, dict) or f.get("name") not in names
                   or f.get("verification") != "exact_base64_stored_content_readback"
                   for f in files)
            or {f["name"] for f in files} != names):
        raise ValueError("Manifest file coverage is incomplete or duplicated")
    if {p.name for p in folder.iterdir()} != names | {"manifest.json"}:
        raise ValueError("Downloaded commit has missing or unmanifested entries")
    envelopes, hashes, pending = {}, {}, {}
    for name in sorted(names):
        envelope, raw = _load(folder / name, folder)
        request, response = envelope.get("request"), envelope.get("response")
        if (not isinstance(request, dict) or request.get("method") != "GET"
                or not isinstance(response, dict)):
            raise ValueError("Retained request/response envelope is malformed")
        _Response(response)
        captured = qgip._aware(envelope.get("captured_utc"))
        if captured > qgip._aware(manifest["committed_utc"]):
            raise ValueError("Envelope was captured after the declared commit")
        key = _key(request.get("uri"), request.get("queries"))
        # Bind each declared file to its purpose, not merely a matching URL.
        if name.startswith("pass-"):
            offset = int(name.removesuffix(".json").split("-offset-")[1])
            expected_key = _key(qgip.API_BASE + "datastore_search",
                                {"resource_id": qgip.RESOURCE_ID, "limit": 100, "offset": offset})
        else:
            kind = name.split("_")[0]
            action, queries = {
                "Index": ("datastore_search", {"resource_id": qgip.INDEX_RESOURCE_ID, "limit": 100, "offset": 0}),
                "Package": ("package_show", {"id": qgip.PACKAGE_NAME}),
                "Resource": ("resource_show", {"id": qgip.RESOURCE_ID}),
                "Schema": ("datastore_info", {"id": qgip.RESOURCE_ID}),
            }[kind]
            expected_key = _key(qgip.API_BASE + action, queries)
        if key != expected_key:
            raise ValueError("Retained request differs from its declared file purpose")
        envelopes[name] = envelope
        hashes[name] = hashlib.sha256(raw).hexdigest()
        pending.setdefault(key, []).append((name, response))

    for kind, fields in {
        "Index": ("records", "total", "total_was_estimated"),
        "Package": ("id", "license_id", "resources"),
        "Resource": ("id", "package_id", "last_modified", "hash"),
        "Schema": ("fields",),
    }.items():
        before = envelopes[kind + "_before.json"]["response"].get("body", {}).get("result", {})
        after = envelopes[kind + "_after.json"]["response"].get("body", {}).get("result", {})
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or any(before.get(field) != after.get(field) for field in fields)):
            raise ValueError("Native source metadata changed across the committed reads")

    def opener(request, **_kwargs):
        url = urlsplit(request.full_url)
        queries = parse_qs(url.query, keep_blank_values=True)
        if any(len(v) != 1 for v in queries.values()):
            raise ValueError("Repeated request parameter")
        key = _key(url._replace(query="").geturl(), {k: v[0] for k, v in queries.items()})
        queue = pending.get(key)
        if not queue:
            raise ValueError("Request has no retained response; network fallback is forbidden")
        # Explicit before/after and pass ordering, independent of directory order.
        queue.sort(key=lambda pair: ("_after." in pair[0], pair[0]))
        return _Response(queue.pop(0)[1])

    result = qgip.fetch_review_queue(retrieved_at=manifest["committed_utc"],
                                    opener=opener, catalogue_path=catalogue_path)
    if any(pending.values()) or result["source_total"] != total:
        raise ValueError("Retained response coverage differs from the native manifest")
    # Generated adapter byte receipts describe reserialization, never source bytes.
    for receipt in result["raw_source"]["http_responses"]:
        receipt["fidelity"] = "reserialized_native_JSON_values_not_original_transport_bytes"
    result["raw_source"]["native_envelopes"] = copy.deepcopy(envelopes)
    result["native_commit"] = {
        "run": manifest["run"], "manifest": manifest,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "stored_file_sha256": hashes,
        "qualification": "offline_downloaded_commit_validation_not_fresh_native_readback",
        "original_transport_bytes_certified": False,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, default=qgip.DEFAULT_CATALOGUE)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output.resolve().is_relative_to(root / "private/ops"):
        raise ValueError("Full retained source output must remain in private/ops")
    result = read_commit(args.folder, catalogue_path=args.catalogue)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    args.output.chmod(0o600)
    print(f"Retained {result['source_total']} source rows; {len(result['records'])} review candidates; no canonical admission")


if __name__ == "__main__":
    main()
