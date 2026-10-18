"""Validate the local SharePoint-only calendar-change flow contract."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "config/flows/funding-calendar-changes-upsert.definition.json"
SCHEMA = ROOT / "config/funding-calendar-changes.schema.json"

def _graph_errors(actions: dict[str, Any], scope: str = "root") -> list[str]:
    errors=[]; names=set(actions)
    for name, action in actions.items():
        errors.extend(f"{scope}.{name}: unknown runAfter {sorted(set(action.get('runAfter', {})) - names)}" for _ in [0] if set(action.get('runAfter', {})) - names)
        for branch in ("actions", "else"):
            nested=action.get(branch,{})
            if branch == "else": nested=nested.get("actions",{}) if isinstance(nested,dict) else {}
            if isinstance(nested,dict): errors.extend(_graph_errors(nested,f"{scope}.{name}.{branch}"))
    return errors

def validate(definition: dict[str, Any]) -> list[str]:
    schema=json.loads(SCHEMA.read_text(encoding="utf-8")); fields={f["display_name"] for f in schema["fields"]}; errors=[]
    actions=definition.get("actions",{}); errors.extend(_graph_errors(actions))
    trigger=definition.get("triggers",{}).get("manual",{})
    if trigger.get("type") != "Request" or "ChangeRowsJson" not in trigger.get("inputs",{}).get("schema",{}).get("required",[]): errors.append("manual trigger must require ChangeRowsJson")
    loop=actions.get("Apply_to_each_Calendar_Change",{}); nested=loop.get("actions",{})
    if loop.get("type") != "Foreach" or "Parse_Change_Rows" not in str(loop.get("foreach", "")): errors.append("change writes must loop over parsed rows")
    if loop.get("runtimeConfiguration",{}).get("concurrency",{}).get("repetitions") != 1: errors.append("change loop must use single-write concurrency")
    lookup=nested.get("SharePoint_Get_items",{}); params=lookup.get("inputs",{}).get("parameters",{})
    if lookup.get("inputs",{}).get("host",{}).get("operationId") != "GetItems" or "Title" not in str(params.get("$filter", "")) or params.get("$top") != 2: errors.append("change lookup must use SharePoint identity lookup capped at two")
    if "DUPLICATE_CALENDAR_CHANGE_KEY" not in json.dumps(nested.get("Condition_Duplicate_ChangeKey",{})): errors.append("duplicate change keys need an explicit diagnostic")
    is_new=nested.get("Condition_Is_New_Calendar_Change",{}); exactly_one=is_new.get("else",{}).get("actions",{}).get("Condition_Exactly_One_Calendar_Change",{})
    if is_new.get("expression",{}).get("equals",[None,None])[1:] != [0]: errors.append("new change branch must require zero matches")
    if exactly_one.get("expression",{}).get("equals",[None,None])[1:] != [1]: errors.append("change update must require exactly one match")
    create_condition=is_new.get("actions",{}).get("Condition_PreviousDate_Present_Create",{})
    update_condition=exactly_one.get("actions",{}).get("Condition_PreviousDate_Present_Update",{})
    expected={"Title", *fields}; without_date=expected-{"PreviousDate"}
    for label, condition, operation in (("create",create_condition,"PostItem"),("update",update_condition,"PatchItem")):
        if condition.get("expression",{}).get("not",{}).get("equals",[None,None])[1:] != [None]: errors.append(f"change {label} must branch on null PreviousDate")
        actions=condition.get("actions",{}); fallback=condition.get("else",{}).get("actions",{})
        with_date=next((a for n,a in actions.items() if n.endswith("_With_PreviousDate")),{})
        without_date_action=next((a for n,a in fallback.items() if n.endswith("_Without_PreviousDate")),{})
        for branch, action in (("with-date",with_date),("without-date",without_date_action)):
            mapped={k.removeprefix("item/") for k in action.get("inputs",{}).get("parameters",{}) if k.startswith("item/")}
            required=expected if branch == "with-date" else without_date
            if mapped != required: errors.append(f"change {label} {branch} mappings must match its canonical schema fields")
            host=action.get("inputs",{}).get("host",{}); action_params=action.get("inputs",{}).get("parameters",{})
            if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline" or host.get("operationId") != operation: errors.append(f"change {label} {branch} must use SharePoint {operation}")
            if action_params.get("dataset") != params.get("dataset") or action_params.get("table") != params.get("table"): errors.append(f"change {label} {branch} must target the same SharePoint list as lookup")
            if not action.get("inputs",{}).get("authentication"): errors.append(f"change {label} {branch} must declare connector authentication")
    if "shared_onedriveforbusiness" in json.dumps(definition).lower(): errors.append("change definition must not use OneDrive")
    return errors

if __name__ == "__main__":
    errors=validate(json.loads(DEFINITION.read_text(encoding="utf-8"))["properties"]["definition"])
    for error in errors: print(f"FAIL: {error}")
    if errors: raise SystemExit(1)
    print("PASS: funding calendar changes SharePoint flow contract is structurally valid")
