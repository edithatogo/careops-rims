"""Compare an unmanaged solution candidate with its preserved native baseline.

Only explicitly selected workflow actions and the solution version may differ.
This offline guard neither imports a package nor proves native acceptance.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import sys
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from powerplatform_validation import loads as strict_loads, validate_members



def _entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        result = {name: archive.read(name) for name in names}
    if not {"solution.xml", "customizations.xml", "[Content_Types].xml"} <= result.keys():
        raise ValueError("Missing solution package metadata")
    manifest = ET.fromstring(result["solution.xml"]).find("SolutionManifest")
    if manifest is None or manifest.findtext("Managed") != "0":
        raise ValueError("Expected an unmanaged solution")
    return result


def _xml(data: bytes, *, version_allowed: bool = False) -> tuple:
    root = ET.fromstring(data)
    if version_allowed:
        version = root.find("SolutionManifest/Version")
        if version is None:
            raise ValueError("Missing solution version")
        version.text = "VERSION"
    def node(element):
        children = [node(child) for child in element]
        # PAC's supported unpack/pack round trip can reorder the workflow
        # collection in customizations.xml. Workflow order is not identity;
        # compare the complete entries by their stable WorkflowId while
        # preserving every field within each entry.
        if (element.tag == "Workflows" and len(element) > 0 and
                all(child.tag == "Workflow" and child.get("WorkflowId") for child in element)):
            ids = [child.get("WorkflowId") for child in element]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate workflow IDs in solution metadata")
            children.sort(key=lambda child: dict(child[1])["WorkflowId"])
        return (element.tag, tuple(sorted(element.attrib.items())),
                (element.text or "").strip(), tuple(children))
    return node(root)


def _pointer_parent(document: dict, pointer: str) -> tuple[dict, str]:
    """Return a JSON Pointer's parent and final token, rejecting bad escapes."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Allowed action pointer must be an absolute JSON Pointer")
    raw_tokens = pointer[1:].split("/")
    tokens = []
    for token in raw_tokens:
        decoded = ""
        index = 0
        while index < len(token):
            if token[index] != "~":
                decoded += token[index]
                index += 1
                continue
            if index + 1 == len(token) or token[index + 1] not in "01":
                raise ValueError("Allowed action pointer has an invalid escape")
            decoded += "~" if token[index + 1] == "0" else "/"
            index += 2
        tokens.append(decoded)
    if tokens[:3] != ["properties", "definition", "actions"] or len(tokens) < 5:
        raise ValueError("Allowed pointer must select content beneath a workflow action")
    current = document
    for token in tokens[:-1]:
        if not isinstance(current, dict) or token not in current:
            raise ValueError("Allowed action pointer does not resolve in both definitions")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError("Allowed action pointer parent must be an object")
    return current, tokens[-1]


def _remove_allowed(document: dict, pointer: str) -> None:
    parent, key = _pointer_parent(document, pointer)
    # New mappings are valid for an explicitly allowed field. Removing the
    # field from both sides makes an absent baseline value compare consistently.
    parent.pop(key, None)


def compare_release(baseline: Path, candidate: Path, allowed_workflows=(),
                    allowed_action_pointers=()) -> dict:
    before, after = _entries(baseline), _entries(candidate)
    if before.keys() != after.keys():
        raise ValueError("Package component membership changed")
    allowed = set(allowed_workflows)
    workflows = {name for name in before if name.startswith("Workflows/") and name.endswith(".json")}
    if not workflows or not allowed <= workflows:
        raise ValueError("Unknown allowed workflow or missing workflow definitions")
    action_pointers = list(allowed_action_pointers)
    if len(action_pointers) != len(set(action_pointers)):
        raise ValueError("Duplicate allowed action pointer")
    pointers_by_workflow: dict[str, list[str]] = {}
    for workflow, pointer in action_pointers:
        if workflow not in workflows or workflow in allowed:
            raise ValueError("Allowed action pointer references an unknown workflow")
        pointers_by_workflow.setdefault(workflow, []).append(pointer)
    changed = 0
    for name in before:
        left, right = before[name], after[name]
        if name in workflows:
            old, new = strict_loads(left), strict_loads(right)
            if old != new:
                changed += 1
            if name in allowed:
                old, new = copy.deepcopy(old), copy.deepcopy(new)
                # Preserve triggers, bindings, schema, metadata and every other field.
                for document in (old, new):
                    actions = document["properties"]["definition"].pop("actions")
                    if not isinstance(actions, dict):
                        raise ValueError("Workflow actions must be an object")
            for pointer in pointers_by_workflow.get(name, ()):
                old, new = copy.deepcopy(old), copy.deepcopy(new)
                _remove_allowed(old, pointer)
                _remove_allowed(new, pointer)
            if old != new:
                raise ValueError("Workflow changed outside the permitted action scope")
        elif name.endswith(".xml"):
            if _xml(left, version_allowed=name == "solution.xml") != _xml(right, version_allowed=name == "solution.xml"):
                raise ValueError("Solution metadata or component configuration changed")
        elif left != right:
            raise ValueError("Unrelated package entry changed")
    return {"status": "PASS_OFFLINE_SOLUTION_COMPARISON", "workflow_count": len(workflows),
            "changed_workflow_count": changed, "permitted_workflow_count": len(allowed),
            "permitted_action_pointer_count": len(action_pointers),
            "native_acceptance": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--validate-structure", action="store_true", help="Validate supported graph/profile and solution membership before comparison")
    parser.add_argument("--allow-workflow", action="append", default=[],
                        help="Legacy: exact workflow whose full action map may change")
    parser.add_argument("--allow-action-pointer", action="append", default=[], metavar="ENTRY::POINTER",
                        help="Allow one exact JSON Pointer beneath a workflow action; repeat as needed")
    args = parser.parse_args()
    try:
        pointers = []
        for selector in args.allow_action_pointer:
            entry, separator, pointer = selector.partition("::")
            if not separator:
                raise ValueError("Action pointer selector must use ENTRY::POINTER")
            pointers.append((entry, pointer))
        result = compare_release(args.baseline, args.candidate, args.allow_workflow, pointers)
        if args.validate_structure:
            result['assurance'] = {label: validate_members(_entries(path)) for label, path in [('baseline', args.baseline), ('candidate', args.candidate)]}
            if any(item['status'] == 'FAIL' for item in result['assurance'].values()):
                print(json.dumps(result, indent=2))
                return 1
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, ET.ParseError) as error:
        parser.exit(1, f"Solution comparison rejected: {type(error).__name__}; inspect inputs privately.\n")


if __name__ == "__main__":
    raise SystemExit(main())
