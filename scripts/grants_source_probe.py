"""Run bounded, read-only checks against the reviewed grants source catalogue.

This is source discovery evidence only. A reachable HTML authority page is not
promoted to an RSS/Atom/API feed, and an HTTP error is retained as an explicit
observation rather than hidden or retried indefinitely.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.grants_sources import load_catalogue
    from scripts.grants_universities import load_universities
except ImportError:  # direct script execution with scripts/ on sys.path
    from grants_sources import load_catalogue
    from grants_universities import load_universities

MAX_BYTES = 128 * 1024
USER_AGENT = "CHHHS-RIMS-grants-source-probe/0.1 (bounded read-only discovery)"
TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)


def _title(body: bytes) -> str | None:
    match = TITLE_RE.search(body)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1).decode("utf-8", "ignore")).strip()
    return value or None


def _probe_row(row: dict[str, Any], opener: Callable[..., Any]) -> dict[str, Any]:
    url = row["authority_url"]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    result: dict[str, Any] = {
        "source_id": row.get("source_id", row.get("institution_id")),
        "authority_url": url,
        "observed_at": observed_at,
        "probe_kind": "authority_url_bounded_get",
        "promoted_to_feed": False,
    }
    try:
        with opener(request, timeout=15) as response:
            body = response.read(MAX_BYTES + 1)
            result.update({
                "status": int(response.getcode() or 0),
                "content_type": response.headers.get("Content-Type", ""),
                "final_url": response.geturl(),
                "bytes_read": min(len(body), MAX_BYTES),
                "truncated": len(body) > MAX_BYTES,
                "body_sha256": hashlib.sha256(body[:MAX_BYTES]).hexdigest(),
                "title": _title(body[:MAX_BYTES]),
            })
    except urllib.error.HTTPError as exc:
        result.update({
            "status": int(exc.code),
            "error": "http_error",
            "reason": str(exc.reason),
            "final_url": getattr(exc, "url", url),
        })
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result.update({"status": None, "error": "transport_error", "reason": str(exc)})
    return result


def _load_university_rows(path: str | Path) -> list[dict[str, Any]]:
    # Use the same fail-closed contract as registry admission. A bounded probe
    # must never make malformed catalogue rows look like source evidence.
    return load_universities(path)


def probe_rows(rows: list[dict[str, Any]], catalogue: str | Path, opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    results = [_probe_row(row, opener) for row in rows]
    return {
        "status": "observed",
        "observed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "catalogue": str(catalogue),
        "max_bytes": MAX_BYTES,
        "results": results,
        "feed_acceptance": "not_proven_by_authority_probe",
    }


def probe_catalogue(path: str | Path, opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    return probe_rows(load_catalogue(path), path, opener)


def probe_universities(path: str | Path, opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    return probe_rows(_load_university_rows(path), path, opener)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalogue", type=Path)
    parser.add_argument("--universities", action="store_true", help="interpret the catalogue as config/grants-universities.json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = probe_universities(args.catalogue) if args.universities else probe_catalogue(args.catalogue)
    payload = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
