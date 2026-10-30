"""Read-only local preflight for Microsoft Power Platform ALM tooling.

This does not authenticate, create service principals, import solutions, or
change a tenant. PAC/Build Tools are used only when a Dataverse solution path
exists; SharePoint, Power BI and native report acceptance retain their own
gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TERMINAL_RUN_STATUSES = {'Succeeded', 'Failed', 'Cancelled', 'Canceled', 'TimedOut', 'Aborted'}
RUN_STATUSES = TERMINAL_RUN_STATUSES | {'Running', 'Waiting', 'Suspended'}
CONTROL_ACTIONS = {'Require_archive_persisted', 'Verify_commit_readback',
                   'Require_validation', 'Require_commit_marker_absent',
                   'Verify_existing_commit_marker', 'Condition_commit_marker'}


def summarize_flowagent(receipt: dict) -> dict:
    """Project recorded control evidence; never echo payloads or signed links."""
    summary = {'scope': 'RECORDED_RECEIPT_ONLY', 'native_acceptance': False,
               'is_error': False, 'observations': []}
    if not isinstance(receipt, dict):
        raise ValueError('A JSON object receipt is required')
    if receipt.get('error'):
        summary['is_error'] = True
    result = receipt.get('result', receipt)
    if not isinstance(result, dict):
        return summary
    summary['is_error'] |= result.get('isError') is True
    documents = []
    if 'content' in result and isinstance(result['content'], list):
        for block in result['content']:
            if isinstance(block, dict) and block.get('type') == 'text':
                try:
                    documents.append(json.loads(block.get('text', '')))
                except (ValueError, TypeError):
                    pass  # Free text may contain credentials or business content.
    else:
        documents.append(result)
    if isinstance(result.get('structuredContent'), dict):
        documents.append(result['structuredContent'])

    # Failed transport/tool observations cannot establish a successful native
    # run, even if an error envelope also contains status-shaped JSON.
    if summary['is_error']:
        return summary

    # Existing combined observations store the run object and paginated action
    # collection separately. Unwrap only these control envelopes; never recurse
    # into arbitrary inputs/outputs, error messages, or retained business data.
    expanded = []
    for document in documents:
        if isinstance(document, dict) and ('run' in document or 'actions' in document):
            run = document.get('run')
            actions = document.get('actions')
            own_properties = document.get('properties', document)
            own_run = (isinstance(own_properties, dict)
                       and isinstance(own_properties.get('status'), str)
                       and own_properties['status'] in RUN_STATUSES)
            if own_run:
                expanded.append(document)
            unwrapped = own_run
            if isinstance(run, dict):
                expanded.append(run)
                unwrapped = True
            if isinstance(actions, dict) and isinstance(actions.get('value'), list):
                expanded.append(actions)
                unwrapped = True
            elif isinstance(actions, list):
                expanded.append({'actions': actions})
                unwrapped = True
            if not unwrapped:
                expanded.append(document)
        else:
            expanded.append(document)
    documents = expanded

    def safe_name(value):
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) else None

    for document in documents:
        if not isinstance(document, (dict, list)):
            continue
        if isinstance(document, dict):
            properties = document.get('properties', document)
            if (isinstance(properties, dict) and isinstance(properties.get('status'), str)
                    and properties['status'] in RUN_STATUSES):
                status = properties['status']
                observation = {'kind': 'run', 'status': status,
                               'terminal': status in TERMINAL_RUN_STATUSES}
                # Times are useful; IDs, content links and correlation envelopes are not.
                for key in ('startTime', 'endTime'):
                    value = properties.get(key)
                    if isinstance(value, str) and re.fullmatch(r'[0-9T:Z.+-]{1,40}', value):
                        observation[key] = value
                summary['observations'].append(observation)
                continue
            if 'action' in document and 'which' in document:
                action = safe_name(document['action'])
                observation = {'kind': 'action_content', 'action': action,
                               'payload_withheld': True}
                size = document.get('contentSize')
                if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
                    observation['content_size'] = size
                # Only exact known guard outcomes may leave the private receipt.
                content = document.get('content')
                if action == 'Verify_commit_readback' and content == 'COMMIT_READBACK_VERIFIED':
                    observation['reported_commit_readback_verified'] = True
                if action == 'Require_archive_persisted' and content == (
                    'All three paginated source keysets and both audit sidecars verified; '
                    'commit marker may follow only after this action succeeds.'
                ):
                    observation['reported_archive_guard_passed'] = True
                summary['observations'].append(observation)
                continue
        rows = document if isinstance(document, list) else document.get('actions', document.get('value', []))
        if not isinstance(rows, list):
            continue
        counts, selected, unclassified = {}, [], 0
        for row in rows:
            if not isinstance(row, dict):
                unclassified += 1
                continue
            properties = row.get('properties', row)
            if not isinstance(properties, dict):
                unclassified += 1
                continue
            status = properties.get('status')
            if not isinstance(status, str) or status not in RUN_STATUSES | {'Skipped'}:
                unclassified += 1
                continue
            counts[status] = counts.get(status, 0) + 1
            name = safe_name(row.get('name'))
            if name and (name in CONTROL_ACTIONS or status in {'Failed', 'TimedOut'}):
                selected.append({'action': name, 'status': status})
        if counts:
            selected.sort(key=lambda row: row['action'] not in CONTROL_ACTIONS)
            summary['observations'].append({'kind': 'actions', 'status_counts': counts,
                                            'unclassified_actions': unclassified,
                                            'selected_actions_omitted': max(0, len(selected) - 20),
                                            'control_and_failed_actions': selected[:20]})
    return summary


def validate_report(report: Path, *, timeout=60, executor=subprocess.run) -> dict:
    """Run both required local validation modes; unavailable checks stay incomplete."""
    report = report.resolve(strict=True)
    if not report.is_dir() or timeout <= 0:
        raise ValueError("Report directory and positive timeout required")
    def fingerprint():
        return {str(p.relative_to(report)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in report.rglob('*') if p.is_file()}
    before = fingerprint()
    results = []
    for mode in ("offline", "schema"):
        command = ["powerbi-report-author", "validate", str(report), "--format", "text"]
        if mode == "offline":
            command.append("--no-schema")
        try:
            child = executor(command, text=True, capture_output=True, check=False, timeout=timeout)
            result = {"mode": mode, "command": command, "exit_code": child.returncode,
                      "stdout": child.stdout, "stderr": child.stderr,
                      "status": "PASS" if child.returncode == 0 else "FAIL"}
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            def partial(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            result = {"mode": mode, "command": command, "exit_code": None,
                      "status": "INCOMPLETE", "reason": "missing-tool" if isinstance(exc, FileNotFoundError) else "timeout",
                      "stdout": partial(getattr(exc, "stdout", None)),
                      "stderr": partial(getattr(exc, "stderr", None))}
        results.append(result)
    unchanged = before == fingerprint()
    statuses = {r["status"] for r in results}
    status = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if "INCOMPLETE" in statuses or not unchanged else "PASS_LOCAL_ONLY"
    return {"status": status, "report": str(report), "checks": results,
            "source_sha256": before, "source_unchanged": unchanged,
            "native": {"status": "NOT_ASSESSED"}, "native_acceptance": False}


def command_output(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=15)
    return result.returncode, (result.stdout + result.stderr).strip()


def check(*, locator=shutil.which, executor=command_output, root: Path = ROOT) -> dict[str, object]:
    tools = {}
    for name, command in {
        "pac": ["pac", "solution"],
        "az": ["az", "extension", "show", "--name", "azure-devops"],
        "pwsh": ["pwsh", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
        "gh": ["gh", "--version"],
    }.items():
        if not locator(command[0]):
            tools[name] = {
                "installed": False,
                "locally_runnable": False,
                "authentication": "NOT_CHECKED",
                "operation_proven": False,
                "available": False,
                "status": "SKIP",
            }
            continue
        try:
            code, output = executor(command)
            locally_runnable = code == 0
            summary = output.splitlines()[0] if output else ""
            status = "PASS" if locally_runnable else "WARN"
        except subprocess.TimeoutExpired:
            locally_runnable, summary, status = False, "command timed out", "WARN"
        except FileNotFoundError:
            locally_runnable, summary, status = False, "executable disappeared after discovery", "WARN"
        tools[name] = {
            "installed": True,
            "locally_runnable": locally_runnable,
            "authentication": "NOT_CHECKED",
            "operation_proven": False,
            # Retained as a compatibility field; it means only local invocation succeeded.
            "available": locally_runnable,
            "status": status,
            "summary": summary,
        }
    solution_projects = sorted(str(path.relative_to(root)) for path in root.glob("**/Other/Solution.xml"))
    return {"status": "PASS_LOCAL_ONLY", "tools": tools, "solution_projects": solution_projects,
            "pac_solution_path": "available" if solution_projects else "not-present; no Dataverse solution is assumed",
            "native_acceptance": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check", "validate-report", "summarize-flowagent", "validate-flow", "validate-solution", "validate-release-dependencies"])
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--component-map", action="store_true")
    parser.add_argument("--deployment-settings", type=Path)
    args = parser.parse_args()
    if args.action == 'validate-release-dependencies':
        from powerplatform_validation import loads, dependency_checks, report
        metadata = loads((ROOT / 'config/release-metadata.json').read_bytes())
        result = report(dependency_checks(metadata.get('AuthoringAssurance', {}).get('externalDependencies', []), ROOT))
        print(json.dumps(result, indent=2))
        return int(result['status'] == 'FAIL')
    if args.action in {'validate-flow', 'validate-solution'}:
        if args.input is None:
            parser.error('validation requires --input; native inputs/maps remain private')
        try:
            from powerplatform_validation import loads, validate_flow, inspect_zip, component_map
            if args.action == 'validate-flow':
                document = loads(args.input.read_bytes())
                result = validate_flow(document)
                if args.component_map and result['status'] == 'PASS':
                    result['componentMap'] = component_map(document)
            else:
                result = inspect_zip(args.input, args.deployment_settings)
            print(json.dumps(result, indent=2))
            return int(result['status'] == 'FAIL')
        except (OSError, ValueError, TypeError):
            print(json.dumps({'status': 'FAIL', 'deploymentReady': False, 'checks': [{'check': 'invalid_input', 'component': 'input', 'severity': 'error', 'evidence_scope': 'offline-structure', 'outcome': 'fail'}]}))
            return 1
    if args.action == 'summarize-flowagent':
        if args.receipt is None or args.output is not None:
            parser.error('summarize-flowagent requires --receipt and writes no output file')
        path = args.receipt.resolve()
        if not path.is_relative_to((ROOT / 'private/ops').resolve()):
            parser.error('Input receipt must remain in ignored private/ops/')
        try:
            if path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('Receipt exceeds the bounded 8 MiB summary input')
            result = summarize_flowagent(json.loads(path.read_text()))
            result['receipt_ref'] = path.relative_to(ROOT).as_posix()
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return 1 if result['is_error'] or not result['observations'] else 0
    if args.action == "validate-report":
        if args.report is None or args.output is None:
            parser.error("validate-report requires --report and --output")
        if not args.output.resolve().is_relative_to((ROOT / "private").resolve()):
            parser.error("Receipt must remain in ignored private/")
        if args.output.exists():
            parser.error("Receipt already exists")
        result = validate_report(args.report, timeout=args.timeout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(result["status"] + "; native NOT_ASSESSED")
        return 0 if result["status"] == "PASS_LOCAL_ONLY" else 1
    result = check()
    for name, value in result["tools"].items():
        print(f"{name}: {value['status']} installed={value['installed']} "
              f"locally_runnable={value['locally_runnable']} auth={value['authentication']} "
              f"operation_proven={value['operation_proven']} {value.get('summary', '')}".rstrip())
    print(f"solution_projects: {len(result['solution_projects'])}")
    print("PASS_LOCAL_ONLY — tooling presence is not tenant acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
