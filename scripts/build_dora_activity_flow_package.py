"""Build a private, target-injected package for the isolated DoRA flow."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from scripts.validate_dora_activity_flow_contract import validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITION = ROOT / "config/flows/dora-activity-registry-upsert.definition.json"


def _replace(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_replace(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace(item, replacements) for key, item in value.items()}
    return value


def build_package(output: Path, *, site_url: str, list_id: str, flow_id: str,
                  connection_display_name: str, definition_path: Path = DEFAULT_DEFINITION) -> Path:
    if not output.resolve().is_relative_to((ROOT / "private").resolve()):
        raise ValueError("tenant-specific package must be written under ignored private/")
    if not isinstance(site_url, str) or not isinstance(list_id, str) or not isinstance(flow_id, str):
        raise ValueError("site_url, list_id and flow_id must be strings")
    if not isinstance(connection_display_name, str):
        raise ValueError("connection display name must be a string")
    parsed_site = urlsplit(site_url.strip())
    if parsed_site.scheme != "https" or not parsed_site.netloc or "{{" in site_url:
        raise ValueError("a concrete HTTPS SharePoint site URL is required")
    for value, label in ((list_id, "list_id"), (flow_id, "flow_id")):
        try:
            UUID(value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"{label} must be a GUID") from exc
    if not isinstance(connection_display_name, str) or not connection_display_name.strip():
        raise ValueError("connection display name is required")
    document = _replace(json.loads(definition_path.read_text(encoding="utf-8")), {
        "{{FLOW_ID}}": flow_id, "{{SHAREPOINT_SITE_URL}}": site_url,
        "{{SHAREPOINT_LIST_ID}}": list_id,
    })
    if "{{" in json.dumps(document):
        raise ValueError("flow definition contains unresolved package placeholders")
    contract_errors = validate(document["properties"]["definition"])
    if contract_errors:
        raise ValueError("DoRA flow contract failed after target injection: " + "; ".join(contract_errors))
    manifest = {"schema": "1.0", "details": {
        "displayName": document["properties"]["displayName"],
        "description": "Isolated DoRA Activity Registry import; disabled until native target/readback approval.",
        "createdTime": "2026-09-21T00:00:00Z", "creator": "N/A", "sourceEnvironment": "",
    }, "resources": {
        flow_id: {"type": "Microsoft.Flow/flows", "suggestedCreationType": "New", "creationType": "New", "details": {"displayName": document["properties"]["displayName"]}, "configurableBy": "User", "hierarchy": "Root", "dependsOn": ["sp_api_id", "sp_conn_id"]},
        "sp_api_id": {"id": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline", "name": "shared_sharepointonline", "type": "Microsoft.PowerApps/apis", "suggestedCreationType": "Existing", "details": {"displayName": "SharePoint"}, "configurableBy": "System", "hierarchy": "Child", "dependsOn": []},
        "sp_conn_id": {"type": "Microsoft.PowerApps/apis/connections", "suggestedCreationType": "Existing", "creationType": "Existing", "details": {"displayName": connection_display_name}, "configurableBy": "User", "hierarchy": "Child", "dependsOn": ["sp_api_id"]},
    }}
    flow_root = f"Microsoft.Flow/flows/{flow_id}"
    files = {
        f"{flow_root}/definition.json": json.dumps(document, indent=2).encode(),
        f"{flow_root}/apisMap.json": json.dumps({"shared_sharepointonline": "sp_api_id"}, indent=2).encode(),
        f"{flow_root}/connectionsMap.json": json.dumps({"shared_sharepointonline": "sp_conn_id"}, indent=2).encode(),
        "manifest.json": json.dumps(manifest, indent=2).encode(),
        "Microsoft.Flow/flows/manifest.json": json.dumps({"packageSchemaVersion": "1.0", "flowAssets": {"assetPaths": [flow_id]}}, indent=2).encode(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--flow-id", required=True)
    parser.add_argument("--connection-display-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_package(args.output, site_url=args.site_url, list_id=args.list_id, flow_id=args.flow_id, connection_display_name=args.connection_display_name))
