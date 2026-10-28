"""Validate portable delivery profiles without tenant access or third-party packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PureWindowsPath


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / ".careops/module.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: {exc}"]
    if not isinstance(data, dict):
        return ["module profile must be a JSON object"]
    if type(data.get("schemaVersion")) is not int or data.get("schemaVersion") != 1:
        errors.append("unsupported schemaVersion")
    if data.get("releasePolicy") != "development-first-verified-promotion":
        errors.append(
            "releasePolicy must preserve development-first verified promotion"
        )
    if (
        data.get("standards")
        != "https://github.com/edithatogo/careops/blob/main/docs/development-and-delivery.md"
    ):
        errors.append("standards must refer to the shared delivery policy")
    if not isinstance(data.get("sourceKind"), str) or data.get("sourceKind") not in {
        "portfolio",
        "reusable-source",
        "implementation",
        "migration-toolkit",
        "historical-implementation",
    }:
        errors.append("invalid sourceKind")
    if not isinstance(data.get("module"), str) or not data["module"].strip():
        errors.append("module is required")
    guide = data.get("localGuide")
    if (
        not isinstance(guide, str)
        or "\0" in guide
        or Path(guide).is_absolute()
        or PureWindowsPath(guide).is_absolute()
        or ".." in Path(guide).parts
    ):
        errors.append("localGuide must be a repository-relative path")
    else:
        try:
            target = (root / guide).resolve()
            if not target.is_relative_to(root.resolve()):
                errors.append("localGuide must stay inside the repository")
            elif not target.is_file():
                errors.append("localGuide does not exist")
        except (OSError, ValueError):
            errors.append("localGuide is invalid")
    tasks = data.get("nextTasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("nextTasks must contain an executable queue")
        return errors
    ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("task must be an object")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id or task_id in ids:
            errors.append("task IDs must be nonempty and unique")
        else:
            ids.add(task_id)
        for field in ("operation", "success", "lane"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                errors.append(f"{task_id}: {field} is required")
        if not isinstance(task.get("status"), str) or task.get("status") not in {"queued", "in-progress", "blocked", "complete"}:
            errors.append(f"{task_id}: invalid task status")
        if not isinstance(task.get("tools"), list) or not task["tools"]:
            errors.append(f"{task_id}: tools are required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        help="repeat for independent repository roots",
    )
    args = parser.parse_args()
    roots = args.root or [Path(__file__).resolve().parents[1]]
    failed = False
    for root in roots:
        errors = validate(root)
        failed |= bool(errors)
        print(
            json.dumps(
                {"moduleRoot": root.name, "passed": not errors, "errors": errors}
            )
        )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
