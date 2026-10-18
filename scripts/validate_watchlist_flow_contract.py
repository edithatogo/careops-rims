"""Validate the local current-user Funding Watchlist Power Automate contract.

Structural proof only: this does not certify native import, permissions, or a live run.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRACKED_DEFINITION = ROOT / "config/flows/funding-watchlist-upsert.definition.json"
SCHEMA_PATH = ROOT / "config/funding-watchlist.schema.json"
PRIVATE_PACKAGE_DIR = ROOT / "private" / "ops" / "flow-packages"


def _graph_errors(actions: dict[str, Any], scope: str = "root") -> list[str]:
    errors: list[str] = []
    names = set(actions)
    for name, action in actions.items():
        unknown = set(action.get("runAfter", {})) - names
        if unknown:
            errors.append(f"{scope}.{name} has unknown runAfter action(s): {sorted(unknown)}")
        for branch in ("actions", "else"):
            nested = action.get(branch, {})
            if branch == "else":
                nested = nested.get("actions", {}) if isinstance(nested, dict) else {}
            if isinstance(nested, dict):
                errors.extend(_graph_errors(nested, f"{scope}.{name}.{branch}"))
    return errors


def _package_definitions() -> list[tuple[Path, dict[str, Any]]]:
    definitions: list[tuple[Path, dict[str, Any]]] = []
    if not PRIVATE_PACKAGE_DIR.exists():
        return definitions
    for package in sorted(PRIVATE_PACKAGE_DIR.glob("*watchlist*.zip")):
        with zipfile.ZipFile(package) as archive:
            members = [name for name in archive.namelist() if name.endswith("/definition.json")]
            if len(members) != 1:
                raise ValueError(f"{package}: expected exactly one flow definition")
            definitions.append((package, json.loads(archive.read(members[0]))["properties"]["definition"]))
    return definitions


def validate(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fields = {field.get("display_name"): field for field in schema.get("fields", [])}
    if schema.get("scope") != "current_user_personal_list":
        errors.append("watchlist schema must be current-user personal scope")
    if fields.get("OpportunityKey", {}).get("unique") is not True:
        errors.append("watchlist schema must declare OpportunityKey unique")
    actions = definition.get("actions", {})
    errors.extend(_graph_errors(actions))
    trigger = definition.get("triggers", {}).get("manual", {})
    if trigger.get("type") != "Request" or "WatchlistRowsJson" not in trigger.get("inputs", {}).get("schema", {}).get("required", []):
        errors.append("manual trigger must require WatchlistRowsJson")
    loop = actions.get("Apply_to_each_Watchlist_Row", {})
    if loop.get("type") != "Foreach" or "Parse_Watchlist_Rows" not in str(loop.get("foreach", "")):
        errors.append("watchlist writes must loop over parsed rows")
    if loop.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions") != 1:
        errors.append("watchlist loop must use single-write concurrency")
    nested = loop.get("actions", {})
    lookup = nested.get("SharePoint_Get_items", {})
    lookup_inputs = lookup.get("inputs", {})
    lookup_host = lookup_inputs.get("host", {})
    params = lookup_inputs.get("parameters", {})
    if lookup_host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or lookup_host.get("operationId") != "GetItems":
        errors.append("watchlist lookup must use SharePoint GetItems")
    if "OpportunityKey" not in str(params.get("$filter", "")) or params.get("$top") != 2:
        errors.append("watchlist lookup must filter OpportunityKey and cap results at two")
    if "DUPLICATE_WATCHLIST_KEY" not in json.dumps(nested.get("Condition_Duplicate_OpportunityKey", {})):
        errors.append("duplicate watchlist keys must have an explicit diagnostic")
    is_new = nested.get("Condition_Is_New_Watchlist_Row", {})
    exactly_one = is_new.get("else", {}).get("actions", {}).get("Condition_Exactly_One_Watchlist_Row", {})
    if is_new.get("expression", {}).get("equals", [None, None])[1:] != [0]:
        errors.append("new watchlist branch must require zero matches")
    if exactly_one.get("expression", {}).get("equals", [None, None])[1:] != [1]:
        errors.append("watchlist update must require exactly one match")
    create = is_new.get("actions", {}).get("SharePoint_Create_item", {})
    update = exactly_one.get("actions", {}).get("SharePoint_Update_item", {})
    create_params = create.get("inputs", {}).get("parameters", {})
    mapped = {key.removeprefix("item/") for key in create_params if key.startswith("item/")}
    if mapped != set(fields):
        errors.append("watchlist create mappings must match the canonical schema fields")
    for label, action, operation in (("create", create, "PostItem"), ("update", update, "PatchItem")):
        host = action.get("inputs", {}).get("host", {})
        action_params = action.get("inputs", {}).get("parameters", {})
        if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or host.get("operationId") != operation:
            errors.append(f"watchlist {label} must use SharePoint {operation}")
        if action_params.get("dataset") != params.get("dataset") or action_params.get("table") != params.get("table"):
            errors.append(f"watchlist {label} must target the same SharePoint list as lookup")
        if not action.get("inputs", {}).get("authentication"):
            errors.append(f"watchlist {label} must declare connector authentication")
    if "shared_onedriveforbusiness" in json.dumps(definition).lower():
        errors.append("watchlist definition must not use OneDrive")
    if any(name in actions for name in {"SharePoint_Get_items", "SharePoint_Create_item", "SharePoint_Update_item"}):
        errors.append("record-scoped SharePoint actions must not be top-level")
    return errors


def main() -> int:
    tracked = json.loads(TRACKED_DEFINITION.read_text(encoding="utf-8"))
    errors = [f"tracked definition: {error}" for error in validate(tracked["properties"]["definition"])]
    for package, definition in _package_definitions():
        errors.extend(f"{package.name}: {error}" for error in validate(definition))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: funding watchlist SharePoint flow contract is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
