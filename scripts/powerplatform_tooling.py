"""Read-only local preflight for Microsoft Power Platform ALM tooling.

This does not authenticate, create service principals, import solutions, or
change a tenant. PAC/Build Tools are used only when a Dataverse solution path
exists; SharePoint, Power BI and native report acceptance retain their own
gates.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def command_output(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def check() -> dict[str, object]:
    tools = {}
    for name, command in {
        "pac": ["pac", "solution"],
        "az": ["az", "extension", "show", "--name", "azure-devops"],
        "pwsh": ["pwsh", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
        "gh": ["gh", "--version"],
    }.items():
        if not shutil.which(command[0]):
            tools[name] = {"available": False, "status": "SKIP"}
            continue
        code, output = command_output(command)
        tools[name] = {"available": code == 0, "status": "PASS" if code == 0 else "WARN", "summary": output.splitlines()[0] if output else ""}
    solution_projects = sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("**/Other/Solution.xml"))
    return {"status": "PASS_LOCAL_ONLY", "tools": tools, "solution_projects": solution_projects,
            "pac_solution_path": "available" if solution_projects else "not-present; no Dataverse solution is assumed",
            "native_acceptance": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check"])
    parser.parse_args()
    result = check()
    for name, value in result["tools"].items():
        print(f"{name}: {value['status']} {value.get('summary', '')}".rstrip())
    print(f"solution_projects: {len(result['solution_projects'])}")
    print("PASS_LOCAL_ONLY — tooling presence is not tenant acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
