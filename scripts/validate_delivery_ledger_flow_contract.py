"""Validate the local current-user Funding Delivery Ledger flow contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "config/flows/funding-delivery-ledger-upsert.definition.json"
SCHEMA = ROOT / "config/funding-delivery-ledger.schema.json"

def _graph_errors(actions: dict[str, Any], scope: str = "root") -> list[str]:
    errors: list[str] = []
    names = set(actions)
    for name, action in actions.items():
        unknown = set(action.get("runAfter", {})) - names
        if unknown:
            errors.append(f"{scope}.{name}: unknown runAfter {sorted(unknown)}")
        for branch in ("actions", "else"):
            nested = action.get(branch, {})
            if branch == "else": nested = nested.get("actions", {}) if isinstance(nested, dict) else {}
            if isinstance(nested, dict): errors.extend(_graph_errors(nested, f"{scope}.{name}.{branch}"))
    return errors

def validate(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fields = {field["display_name"] for field in schema["fields"]}
    actions = definition.get("actions", {})
    errors.extend(_graph_errors(actions))
    trigger = definition.get("triggers", {}).get("manual", {})
    if trigger.get("type") != "Request" or "DeliveryRowsJson" not in trigger.get("inputs", {}).get("schema", {}).get("required", []): errors.append("manual trigger must require DeliveryRowsJson")
    loop = actions.get("Apply_to_each_Delivery_Row", {})
    if loop.get("type") != "Foreach" or "Parse_Delivery_Rows" not in str(loop.get("foreach", "")): errors.append("delivery writes must loop over parsed rows")
    if loop.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions") != 1: errors.append("delivery loop must use single-write concurrency")
    nested = loop.get("actions", {})
    lookup = nested.get("SharePoint_Get_items", {})
    params = lookup.get("inputs", {}).get("parameters", {})
    if lookup.get("inputs", {}).get("host", {}).get("operationId") != "GetItems" or "Title" not in str(params.get("$filter", "")) or params.get("$top") != 2: errors.append("delivery lookup must use SharePoint GetItems, filter identity and cap results")
    if "DUPLICATE_DELIVERY_EVENT_KEY" not in json.dumps(nested.get("Condition_Duplicate_DeliveryEventKey", {})): errors.append("duplicate delivery keys need an explicit diagnostic")
    is_new = nested.get("Condition_Is_New_Delivery_Row", {})
    exactly_one = is_new.get("else", {}).get("actions", {}).get("Condition_Exactly_One_Delivery_Row", {})
    if is_new.get("expression", {}).get("equals", [None, None])[1:] != [0]: errors.append("new delivery branch must require zero matches")
    if exactly_one.get("expression", {}).get("equals", [None, None])[1:] != [1]: errors.append("delivery update must require exactly one match")
    create = is_new.get("actions", {}).get("SharePoint_Create_item", {})
    update = exactly_one.get("actions", {}).get("SharePoint_Update_item", {})
    mapped = {key.removeprefix("item/") for key in create.get("inputs", {}).get("parameters", {}) if key.startswith("item/")}
    expected = {"Title", *(field for field in fields if field != "DeliveryEventKey")}
    if mapped != expected: errors.append("delivery create mappings must match the canonical schema fields")
    for label, action, operation in (("create", create, "PostItem"), ("update", update, "PatchItem")):
        host = action.get("inputs", {}).get("host", {})
        action_params = action.get("inputs", {}).get("parameters", {})
        if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or host.get("operationId") != operation: errors.append(f"delivery {label} must use SharePoint {operation}")
        if action_params.get("dataset") != params.get("dataset") or action_params.get("table") != params.get("table"): errors.append(f"delivery {label} must target the same SharePoint list as lookup")
        if not action.get("inputs", {}).get("authentication"): errors.append(f"delivery {label} must declare connector authentication")
    if "shared_onedriveforbusiness" in json.dumps(definition).lower(): errors.append("delivery definition must not use OneDrive")
    return errors

def main() -> int:
    definition = json.loads(DEFINITION.read_text(encoding="utf-8"))
    errors = validate(definition["properties"]["definition"])
    if errors:
        for error in errors: print(f"FAIL: {error}")
        return 1
    print("PASS: funding delivery ledger SharePoint flow contract is structurally valid")
    return 0

if __name__ == "__main__": raise SystemExit(main())
