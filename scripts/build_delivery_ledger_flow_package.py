"""Build a private, target-injected Funding Delivery Ledger flow package."""
from __future__ import annotations

import argparse
from pathlib import Path

from build_grants_flow_package import build_package

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITION = ROOT / "config/flows/funding-delivery-ledger-upsert.definition.json"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--flow-id", required=True)
    parser.add_argument("--connection-display-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--creation-type", choices=("New", "Update"), default="New")
    args = parser.parse_args()
    print(build_package(args.output, site_url=args.site_url, list_id=args.list_id, flow_id=args.flow_id, connection_display_name=args.connection_display_name, definition_path=DEFAULT_DEFINITION, description="Isolated DEV funding delivery ledger upsert; remains disabled until native test approval.", creation_type=args.creation_type))
