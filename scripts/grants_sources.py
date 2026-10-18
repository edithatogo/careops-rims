"""Validate official, machine-readable and reconciled grants sources only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts.grants_source_identity import validate_source_id_path
except ImportError:
    from grants_source_identity import validate_source_id_path

REQUIRED_SOURCE_IDS = {"arc-awards-api", "queensland-grants-finder-catalogue-api"}
ALLOWED_INTAKE = {"rss", "atom", "api"}
ALLOWED_HEALTH = {"verified_sample"}
ALLOWED_ADMISSION = {"opportunity", "awarded_grant", "context_only", "metadata_only", "candidate_only"}
DEFAULT_CATALOGUE = Path(__file__).resolve().parents[1] / "config" / "grants-sources.json"


def _https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    raw = value
    if raw != raw.strip() or any(char.isspace() or ord(char) < 32 for char in raw):
        return False
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        # Catalogue endpoints and authority pages are public source locations,
        # so credentials and custom ports are never part of the contract. In
        # particular, checking only netloc would accept URLs such as
        # https://official.example@attacker.test/...
        return (parsed.scheme.casefold() == "https" and bool(host) and "." in host
                and not host.endswith(".") and not parsed.username and not parsed.password
                and parsed.port is None)
    except ValueError:
        return False


def load_catalogue(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("grants source catalogue must be a list")
    seen: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("each source catalogue row must be an object")
        source_id_value = row.get("source_id")
        if not isinstance(source_id_value, str):
            raise ValueError("source_id must be text")
        source_id = source_id_value.strip()
        if source_id != source_id_value or not source_id:
            raise ValueError("source_id must be nonempty unpadded text")
        if source_id in seen:
            raise ValueError(f"duplicate or missing source_id: {source_id!r}")
        seen.add(source_id)
        if not isinstance(row.get("enabled"), bool):
            raise ValueError(f"source {source_id!r} needs boolean enabled state")
        if (not _https_url(row.get("authority_url"))
                or not isinstance(row.get("title"), str)
                or not row["title"].strip()):
            raise ValueError(f"source {source_id!r} needs official HTTPS authority_url and title")
        intake = row.get("intake")
        if intake not in ALLOWED_INTAKE:
            raise ValueError(f"source {source_id!r} has unsupported non-machine intake")
        endpoint_field = "api_url" if intake == "api" else "feed_url"
        if not _https_url(row.get(endpoint_field)):
            raise ValueError(f"source {source_id!r} with {intake} intake needs HTTPS {endpoint_field}")
        if row.get("health_status") not in ALLOWED_HEALTH:
            raise ValueError(f"source {source_id!r} is not verified for machine reconciliation")
        reconciliation = row.get("reconciliation")
        if not isinstance(reconciliation, dict):
            raise ValueError(f"source {source_id!r} needs reconciliation contract")
        if not isinstance(reconciliation.get("source_id_path"), str) or not reconciliation["source_id_path"].strip():
            raise ValueError(f"source {source_id!r} needs reconciliation source_id_path")
        try:
            validate_source_id_path(reconciliation["source_id_path"], intake)
        except ValueError as exc:
            raise ValueError(f"source {source_id!r} has invalid reconciliation source_id_path") from exc
        stable_key_prefix = reconciliation.get("stable_key_prefix")
        if (not isinstance(stable_key_prefix, str) or not stable_key_prefix
                or stable_key_prefix != stable_key_prefix.strip()):
            raise ValueError(
                f"source {source_id!r} needs a nonempty unpadded reconciliation stable_key_prefix"
            )
        if reconciliation.get("admission") not in ALLOWED_ADMISSION:
            raise ValueError(f"source {source_id!r} has unsupported reconciliation admission")
        if reconciliation.get("admission") == "opportunity":
            if reconciliation.get("entity") != "opportunity":
                raise ValueError(f"source {source_id!r} has mismatched opportunity entity")
            hosts = row.get("official_row_hosts")
            if (not isinstance(hosts, list) or not hosts
                    or any(not isinstance(host, str) or not host
                           or host != host.strip().casefold()
                           or not _https_url(f"https://{host}/")
                           or urlsplit(f"https://{host}/").hostname != host
                           for host in hosts)):
                raise ValueError(f"source {source_id!r} needs official_row_hosts")
        for field in ("authority_type", "eligibility_scope", "format", "access", "coverage", "record_kind"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"source {source_id!r} needs {field}")
    missing = REQUIRED_SOURCE_IDS - seen
    if missing:
        raise ValueError(f"required sources missing: {sorted(missing)}")
    return payload


def require_enabled_source(path: str | Path, source_id: str) -> dict[str, Any]:
    """Resolve one exact catalogue row and fail before network access if stopped."""
    rows = load_catalogue(path)
    matches = [row for row in rows if row["source_id"] == source_id]
    if len(matches) != 1:
        raise ValueError("source_missing_or_ambiguous")
    if not matches[0]["enabled"]:
        raise ValueError("source_disabled")
    return matches[0]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("catalogue", type=Path)
    args = parser.parse_args()
    rows = load_catalogue(args.catalogue)
    print(f"validated {len(rows)} official reconciled grant source rows")
