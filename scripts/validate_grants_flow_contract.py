"""Validate the local reviewed-grants Power Automate flow contract.

This is a structural guard only. It does not certify tenant state, connector
permissions, a native import, or a live run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TRACKED_DEFINITION = ROOT / "config/flows/grants-registry-reviewed-import.definition.json"
SCHEMA_PATH = ROOT / "config/grants-registry.schema.json"
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


def _definition() -> dict[str, Any]:
    return json.loads(TRACKED_DEFINITION.read_text(encoding="utf-8"))["properties"]["definition"]


def _package_definitions() -> list[tuple[Path, dict[str, Any]]]:
    """Load generated grants packages when ignored private artefacts exist."""
    definitions: list[tuple[Path, dict[str, Any]]] = []
    if not PRIVATE_PACKAGE_DIR.exists():
        return definitions
    for package in sorted(PRIVATE_PACKAGE_DIR.glob("*grant*.zip")):
        with zipfile.ZipFile(package) as archive:
            members = [name for name in archive.namelist() if name.endswith("/definition.json")]
            if len(members) != 1:
                raise ValueError(f"{package}: expected exactly one flow definition")
            definitions.append((package, json.loads(archive.read(members[0]))["properties"]["definition"]))
    return definitions


def validate(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        registry_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"grants registry schema cannot be loaded: {exc}")
        registry_schema = {}
    identity_fields = {
        field.get("display_name"): field
        for field in registry_schema.get("fields", [])
        if isinstance(field, dict)
    }
    if identity_fields.get("OpportunityKey", {}).get("unique") is not True:
        errors.append("grants registry schema must declare OpportunityKey unique")
    actions = definition.get("actions", {})
    errors.extend(_graph_errors(actions))

    trigger = definition.get("triggers", {}).get("manual", {})
    schema = trigger.get("inputs", {}).get("schema", {})
    if trigger.get("type") != "Request" or "ReviewedRowsJson" not in schema.get("required", []):
        errors.append("manual trigger must require ReviewedRowsJson")

    loop = actions.get("Apply_to_each_Reviewed_Row", {})
    if loop.get("type") != "Foreach":
        errors.append("reviewed registry writes must be inside an explicit record loop")
    if "Parse_Reviewed_Rows" not in str(loop.get("foreach", "")):
        errors.append("record loop must consume parsed reviewed rows")
    if loop.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions") != 1:
        errors.append("reviewed record loop must use single-write concurrency")

    nested = loop.get("actions", {})
    lookup = nested.get("SharePoint_Get_items", {})
    lookup_inputs = lookup.get("inputs", {})
    lookup_host = lookup_inputs.get("host", {})
    lookup_parameters = lookup_inputs.get("parameters", {})
    if lookup_host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline":
        errors.append("grants lookup must use the SharePoint Online connector")
    if lookup_host.get("operationId") != "GetItems":
        errors.append("grants lookup must use the SharePoint GetItems operation")
    if "OpportunityKey" not in str(lookup_parameters.get("$filter", "")):
        errors.append("grants lookup must filter by OpportunityKey")
    if lookup_parameters.get("$top") != 2:
        errors.append("grants lookup must cap results at two rows")

    duplicate = nested.get("Condition_Duplicate_OpportunityKey", {})
    duplicate_text = json.dumps(duplicate)
    if "greater" not in duplicate_text or "DUPLICATE_OPPORTUNITY_KEY" not in duplicate_text:
        errors.append("duplicate OpportunityKey results must fail closed")

    is_new = nested.get("Condition_Is_New_Opportunity", {})
    if is_new.get("expression", {}).get("equals", [None, None])[1:] != [0]:
        errors.append("new-record branch must require zero SharePoint matches")
    exactly_one = is_new.get("else", {}).get("actions", {}).get("Condition_Exactly_One_Opportunity", {})
    if exactly_one.get("expression", {}).get("equals", [None, None])[1:] != [1]:
        errors.append("existing-record update must require exactly one SharePoint match")

    create = is_new.get("actions", {}).get("SharePoint_Create_item", {})
    update = exactly_one.get("actions", {}).get("SharePoint_Update_item", {})
    create_parameters = create.get("inputs", {}).get("parameters", {})
    mapped_create_fields = {key.removeprefix("item/") for key in create_parameters if key.startswith("item/")}
    if mapped_create_fields != set(identity_fields):
        errors.append("grants create mappings must match the canonical registry schema fields")
    for label, action, operation in (("create", create, "PostItem"), ("update", update, "PatchItem")):
        host = action.get("inputs", {}).get("host", {})
        parameters = action.get("inputs", {}).get("parameters", {})
        if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline":
            errors.append(f"{label} action must use the SharePoint Online connector")
        if host.get("operationId") != operation:
            errors.append(f"{label} action must use SharePoint {operation}")
        if parameters.get("dataset") != lookup_parameters.get("dataset") or parameters.get("table") != lookup_parameters.get("table"):
            errors.append(f"{label} action must target the same SharePoint site and list as lookup")
        if not action.get("inputs", {}).get("authentication"):
            errors.append(f"{label} action must declare connector authentication")
        if "item/SourceRowURL" not in parameters:
            errors.append(f"{label} action must persist SourceRowURL evidence")

    update_parameters = update.get("inputs", {}).get("parameters", {})
    if any(key in update_parameters for key in ("item/ReviewStatus", "item/ReviewNotes")):
        errors.append("existing records must preserve manual review fields")
    if "shared_onedriveforbusiness" in json.dumps(definition).lower():
        errors.append("grants registry definition must not use OneDrive")
    if any(name in actions for name in {"SharePoint_Get_items", "SharePoint_Create_item", "SharePoint_Update_item"}):
        errors.append("record-scoped SharePoint actions must not be top-level")
    return errors


def main() -> int:
    errors = [f"tracked definition: {error}" for error in validate(_definition())]
    for package, definition in _package_definitions():
        errors.extend(f"{package.name}: {error}" for error in validate(definition))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: grants SharePoint flow contract is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
