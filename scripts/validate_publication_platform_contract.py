"""Validate the local publication SharePoint flow contract.

This is a structural guard only. It does not certify tenant state or a live run.
"""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

try:
    from publication_batch_contract import validate_update_allowlist
except ModuleNotFoundError:
    from scripts.publication_batch_contract import validate_update_allowlist


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "private" / "ops" / "flow-packages" / "sharepoint-upsert.zip"
TRACKED_DEFINITION = ROOT / "config" / "flows" / "publication-registry-upsert.definition.json"
MANIFEST = ROOT / "config" / "flows" / "manifest.template.json"
CANONICAL_DISPLAY_NAME = "CHHHS Research Publications - Daily Ingestion & Enrichment"


def _graph_errors(actions: dict, scope: str = "root") -> list[str]:
    errors: list[str] = []
    names = set(actions)
    for name, action in actions.items():
        unknown = set((action.get("runAfter") or {})) - names
        if unknown:
            errors.append(f"{scope}.{name} has unknown runAfter action(s): {sorted(unknown)}")
        for branch in ("actions", "else"):
            nested = action.get(branch, {})
            if branch == "else":
                nested = nested.get("actions", {}) if isinstance(nested, dict) else {}
            if isinstance(nested, dict):
                errors.extend(_graph_errors(nested, f"{scope}.{name}.{branch}"))
    return errors


def _definition() -> dict:
    with zipfile.ZipFile(PACKAGE) as archive:
        name = next(n for n in archive.namelist() if n.endswith("/definition.json"))
        return json.loads(archive.read(name))["properties"]["definition"]


def _manifest() -> dict:
    with zipfile.ZipFile(PACKAGE) as archive:
        return json.loads(archive.read("manifest.json"))


def _tracked_definition() -> dict:
    return json.loads(TRACKED_DEFINITION.read_text(encoding="utf-8"))["properties"]["definition"]


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("details", {}).get("displayName") != CANONICAL_DISPLAY_NAME:
        errors.append("manifest root must use the canonical flow display name")
    resources = manifest.get("resources", {})
    flows = [resource for resource in resources.values() if resource.get("type") == "Microsoft.Flow/flows"]
    if len(flows) != 1:
        errors.append("manifest must contain exactly one flow resource")
    elif flows[0].get("details", {}).get("displayName") != CANONICAL_DISPLAY_NAME:
        errors.append("manifest flow resource must use the canonical flow display name")
    return errors


def validate(definition: dict) -> list[str]:
    errors: list[str] = []
    if definition.get("triggers", {}).get("Recurrence", {}).get("type") != "Recurrence":
        errors.append("canonical publication flow must use a Recurrence trigger")
    recurrence = definition.get("triggers", {}).get("Recurrence", {}).get("recurrence", {})
    if (
        recurrence.get("frequency") != "Day"
        or recurrence.get("interval") != 1
        or recurrence.get("timeZone") != "UTC"
        or recurrence.get("schedule", {}).get("hours") != ["20"]
        or recurrence.get("schedule", {}).get("minutes") != [0]
    ):
        errors.append("recurrence must run daily at 20:00 UTC")
    actions = definition.get("actions", {})
    errors.extend(_graph_errors(actions))
    loop = actions.get("Apply_to_each_Publication", {})
    if loop.get("type") != "Foreach":
        errors.append("registry writes must be inside an explicit record loop")
    if not loop.get("foreach") or "rows" not in str(loop.get("foreach")):
        errors.append("record loop must consume the validated query rows")
    if loop.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions") != 1:
        errors.append("record loop must use single-write concurrency")
    record_actions = loop.get("actions", {})
    get_items = record_actions.get("SharePoint_Get_items", {})
    get_inputs = get_items.get("inputs", {})
    host = get_inputs.get("host", {})
    parameters = get_inputs.get("parameters", {})

    if host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline":
        errors.append("registry lookup must use the SharePoint Online connector")
    if host.get("operationId") != "GetItems":
        errors.append("registry lookup must use the SharePoint GetItems operation")
    if not parameters.get("dataset") or not parameters.get("table"):
        errors.append("registry lookup must specify site and list identifiers")
    if "SourceKey" not in str(parameters.get("$filter", "")):
        errors.append("registry lookup must filter by SourceKey")

    row_query = actions.get("Run_publication_rows_query", {})
    row_query_text = json.dumps(row_query)
    if row_query.get("type") != "OpenApiConnection" or "Publication" not in row_query_text:
        errors.append("publication rows must come from a dedicated Power BI query")
    row_query_dax = str(row_query.get("inputs", {}).get("parameters", {}).get("specification/query", ""))
    if "SourceKey" not in row_query_dax or "NOT ISBLANK" not in row_query_dax:
        errors.append("publication rows query must emit nonblank SourceKey values")
    if loop.get("runAfter") != {"Run_publication_rows_query": ["Succeeded"]} or "Run_publication_rows_query" not in str(loop.get("foreach", "")):
        errors.append("record loop must depend on the publication rows query")
    readiness_query = actions.get("Run_a_query_against_a_dataset", {})
    readiness_model = readiness_query.get("inputs", {}).get("parameters", {}).get("datasetid")
    rows_model = row_query.get("inputs", {}).get("parameters", {}).get("datasetid")
    if not readiness_model or readiness_model != rows_model:
        errors.append("readiness and publication rows queries must use the same Power BI model")

    condition = record_actions.get("Condition_Is_New_Publication", {})
    if "length(body('SharePoint_Get_items')?['value'])" not in json.dumps(condition):
        errors.append("registry upsert must branch on SharePoint lookup result")

    create = condition.get("actions", {}).get("SharePoint_Create_item", {})
    create_text = json.dumps(create)
    update_guard = condition.get("else", {}).get("actions", {}).get("Condition_Exactly_One_Publication", {})
    if update_guard.get("expression", {}).get("equals", [None, None])[1:] != [1]:
        errors.append("existing-record update must require exactly one SharePoint match")
    update_for_connector = update_guard.get("actions", {}).get("SharePoint_Update_item", {})
    for action_name, action in (("SharePoint_Create_item", create), ("SharePoint_Update_item", update_for_connector)):
        action_host = action.get("inputs", {}).get("host", {})
        action_parameters = action.get("inputs", {}).get("parameters", {})
        if action_host.get("apiId") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline":
            errors.append(f"{action_name} must use the SharePoint Online connector")
        expected_operation = {
            "SharePoint_Create_item": "PostItem",
            "SharePoint_Update_item": "PatchItem",
        }[action_name]
        if action_host.get("operationId") != expected_operation:
            errors.append(f"{action_name} must use the SharePoint {expected_operation} operation")
        if action_parameters.get("dataset") != parameters.get("dataset") or action_parameters.get("table") != parameters.get("table"):
            errors.append(f"{action_name} must target the same SharePoint site and list as lookup")
        if not action.get("inputs", {}).get("authentication"):
            errors.append(f"{action_name} must declare connector authentication")
    if "item/field_19" not in create_text or "item/field_20" not in create_text:
        errors.append("new records must set first and last observed timestamps")

    update = update_guard.get("actions", {}).get("SharePoint_Update_item", {})
    update_text = json.dumps(update)
    if "item/field_20" not in update_text or "item/field_19" in update_text:
        errors.append("existing records must update last observed without overwriting first observed")
    update_parameters = update.get("inputs", {}).get("parameters", {})
    update_fields = [key.removeprefix("item/") for key in update_parameters if key.startswith("item/")]
    errors.extend(validate_update_allowlist(update_fields, internal_allowed={"field_20"}))

    duplicate = record_actions.get("Condition_Duplicate_SourceKey", {})
    duplicate_text = json.dumps(duplicate)
    if "greater" not in duplicate_text or "DUPLICATE_SOURCE_KEY" not in duplicate_text:
        errors.append("duplicate SourceKey results must fail closed")
    if "Compose_Duplicate_SourceKey_Failure" not in duplicate_text or "int('DUPLICATE_SOURCE_KEY')" not in duplicate_text:
        errors.append("duplicate SourceKey failure must use a foreach-compatible failing action")
    if "replace(" not in str(parameters.get("$filter", "")):
        errors.append("SourceKey filter must escape apostrophes")
    if any(name in actions for name in {"SharePoint_Get_items", "Condition_Is_New_Publication", "SharePoint_Create_item", "SharePoint_Update_item"}):
        errors.append("record-scoped SharePoint actions must not be top-level")

    if "shared_onedriveforbusiness" in json.dumps(definition).lower():
        errors.append("registry definition must not use OneDrive for registry persistence")
    return errors


def main() -> int:
    errors = validate(_tracked_definition())
    errors.extend(validate_manifest(json.loads(MANIFEST.read_text(encoding="utf-8"))))
    if PACKAGE.exists():
        errors.extend(validate(_definition()))
        errors.extend(validate_manifest(_manifest()))
    else:
        print(f"INFO: private package not present; validating tracked definition only: {PACKAGE}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: publication SharePoint flow contract is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
