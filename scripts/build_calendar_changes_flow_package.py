"""Build a private, target-injected calendar-change upsert package."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from build_grants_flow_package import build_package

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITION = ROOT / "config/flows/funding-calendar-changes-upsert.definition.json"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--flow-id", required=True)
    parser.add_argument("--connection-display-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--creation-type", choices=("New", "Update"), default="New")
    parser.add_argument("--native-baseline", type=Path, help="Ignored/private tenant export used only to copy native metadata and connection shape")
    args = parser.parse_args()
    definition_path = DEFAULT_DEFINITION
    if args.native_baseline:
        baseline = json.loads(args.native_baseline.read_text(encoding="utf-8"))
        native_metadata = baseline["properties"]["definition"].get("metadata")
        native_connection = baseline["properties"]["connectionReferences"]["shared_sharepointonline"].get("connectionName")
        if not isinstance(native_metadata, dict) or not isinstance(native_connection, str):
            raise ValueError("native baseline lacks metadata or SharePoint connection shape")
        definition = json.loads(DEFAULT_DEFINITION.read_text(encoding="utf-8"))
        definition["properties"]["definition"]["metadata"] = native_metadata
        definition["properties"]["connectionReferences"]["shared_sharepointonline"]["connectionName"] = native_connection
        native_auth = "@json(decodeBase64(triggerOutputs().headers['X-MS-APIM-Tokens']))['$ConnectionKey']"
        def replace(value):
            if isinstance(value, str):
                return native_auth if value == "@parameters('$authentication')" else value
            if isinstance(value, list):
                return [replace(item) for item in value]
            if isinstance(value, dict):
                return {key: replace(item) for key, item in value.items()}
            return value
        definition_path = args.output.with_suffix(".native-shape.definition.json")
        definition_path.write_text(json.dumps(replace(definition), indent=2), encoding="utf-8")
    try:
        print(build_package(args.output, site_url=args.site_url, list_id=args.list_id, flow_id=args.flow_id, connection_display_name=args.connection_display_name, definition_path=definition_path, description="Isolated DEV funding calendar change upsert; remains disabled until native test approval.", creation_type=args.creation_type))
    finally:
        if args.native_baseline and definition_path != DEFAULT_DEFINITION:
            definition_path.unlink(missing_ok=True)
