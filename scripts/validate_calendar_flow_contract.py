"""Validate the local current-user Funding Calendar Power Automate contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "config/flows/funding-calendar-upsert.definition.json"
SCHEMA = ROOT / "config/funding-calendar.schema.json"


def _graph_errors(actions: dict[str, Any], scope: str = "root") -> list[str]:
    errors: list[str] = []
    names = set(actions)
    for name, action in actions.items():
        errors.extend(f"{scope}.{name}: unknown runAfter {sorted(set(action.get('runAfter', {})) - names)}" for _ in [0] if set(action.get('runAfter', {})) - names)
        for branch in ("actions", "else"):
            nested = action.get(branch, {})
            if branch == "else":
                nested = nested.get("actions", {}) if isinstance(nested, dict) else {}
            if isinstance(nested, dict):
                errors.extend(_graph_errors(nested, f"{scope}.{name}.{branch}"))
    return errors


def validate(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fields = {field["display_name"]: field for field in schema["fields"]}
    actions = definition.get("actions", {})
    errors.extend(_graph_errors(actions))
    trigger = definition.get("triggers", {}).get("manual", {})
    if trigger.get("type") != "Request" or "CalendarRowsJson" not in trigger.get("inputs", {}).get("schema", {}).get("required", []):
        errors.append("manual trigger must require CalendarRowsJson")
    loop = actions.get("Apply_to_each_Calendar_Row", {})
    if loop.get("type") != "Foreach" or "Parse_Calendar_Rows" not in str(loop.get("foreach", "")):
        errors.append("calendar writes must loop over parsed rows")
    if loop.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions") != 1:
        errors.append("calendar loop must use single-write concurrency")
    nested = loop.get("actions", {})
    lookup = nested.get("SharePoint_Get_items", {})
    lookup_inputs = lookup.get("inputs", {})
    lookup_host = lookup_inputs.get("host", {})
    params = lookup_inputs.get("parameters", {})
    if lookup_host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or lookup_host.get("operationId") != "GetItems":
        errors.append("calendar lookup must use SharePoint GetItems")
    if "DeadlineKey" not in str(params.get("$filter", "")) or params.get("$top") != 2:
        errors.append("calendar lookup must filter DeadlineKey and cap results at two")
    if "DUPLICATE_DEADLINE_KEY" not in json.dumps(nested.get("Condition_Duplicate_DeadlineKey", {})):
        errors.append("duplicate deadline keys must have an explicit diagnostic")
    is_new = nested.get("Condition_Is_New_Calendar_Row", {})
    exactly_one = is_new.get("else", {}).get("actions", {}).get("Condition_Exactly_One_Calendar_Row", {})
    if is_new.get("expression", {}).get("equals", [None, None])[1:] != [0]:
        errors.append("new calendar branch must require zero matches")
    if exactly_one.get("expression", {}).get("equals", [None, None])[1:] != [1]:
        errors.append("calendar update must require exactly one match")
    create = is_new.get("actions", {}).get("SharePoint_Create_item", {})
    update = exactly_one.get("actions", {}).get("SharePoint_Update_item", {})
    mapped = {key.removeprefix("item/") for key in create.get("inputs", {}).get("parameters", {}) if key.startswith("item/")}
    if mapped != set(fields):
        errors.append("calendar create mappings must match the canonical schema fields")
    for label, action, operation in (("create", create, "PostItem"), ("update", update, "PatchItem")):
        host = action.get("inputs", {}).get("host", {})
        action_params = action.get("inputs", {}).get("parameters", {})
        if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or host.get("operationId") != operation:
            errors.append(f"calendar {label} must use SharePoint {operation}")
        if action_params.get("dataset") != params.get("dataset") or action_params.get("table") != params.get("table"):
            errors.append(f"calendar {label} must target the same SharePoint list as lookup")
        if not action.get("inputs", {}).get("authentication"):
            errors.append(f"calendar {label} must declare connector authentication")
    if "shared_onedriveforbusiness" in json.dumps(definition).lower():
        errors.append("calendar definition must not use OneDrive")
    return errors


def main() -> int:
    definition = json.loads(DEFINITION.read_text(encoding="utf-8"))
    errors = validate(definition["properties"]["definition"])
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: funding calendar SharePoint flow contract is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
