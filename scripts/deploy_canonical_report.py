"""Retired canonical-report deploy route; only isolated targets are allowed."""
from __future__ import annotations
import argparse
import json
import time
import urllib.request
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "private/ops/live_token.json"
UPDATED_FILE = ROOT / "private/ops/report-definition-updated.json"

WS_ID = "{{WORKSPACE_ID}}"
REPORT_ID = "{{REPORT_ID}}"


def validate_deployment_target(workspace_id: str, report_id: str, target_scope: str) -> None:
    """Fail closed unless an explicit, concrete isolated target is supplied."""
    if target_scope != "isolated":
        raise ValueError("canonical/shared report deployment is disabled; target_scope must be isolated")
    if "{{" in workspace_id or "{{" in report_id:
        raise ValueError("concrete isolated workspace and report IDs are required")
    try:
        UUID(workspace_id)
        UUID(report_id)
    except ValueError as exc:
        raise ValueError("workspace and report IDs must be GUIDs") from exc

def get_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, str):
        d = json.loads(d)
    return d["token"]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-scope", default="canonical")
    args = parser.parse_args()
    validate_deployment_target(WS_ID, REPORT_ID, args.target_scope)
    token = get_token()
    with open(UPDATED_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print(f"Deploying updated definition to report {REPORT_ID} in workspace {WS_ID}...")
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{WS_ID}/reports/{REPORT_ID}/updateDefinition"
    
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            print("updateDefinition status:", resp.status)
            loc = resp.headers.get("Location")
            print("Location header:", loc)
            
            if not loc:
                print("Update succeeded immediately (no location header).")
                return

            print("Polling operation status at:", loc)
            poll_headers = {"Authorization": f"Bearer {token}"}
            for attempt in range(15):
                time.sleep(2)
                poll_req = urllib.request.Request(loc, headers=poll_headers)
                with urllib.request.urlopen(poll_req) as presp:
                    pdata = json.loads(presp.read().decode("utf-8"))
                    status = pdata.get("status")
                    print(f"Poll attempt {attempt + 1}: status = {status}")
                    if status == "Succeeded":
                        print("Deployment SUCCEEDED!")
                        break
                    elif status == "Failed":
                        print("Deployment FAILED:", pdata.get("error"))
                        raise RuntimeError(f"Deployment failed: {pdata}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        raise

if __name__ == "__main__":
    main()
