"""Download canonical live platform definitions and artifacts locally.

Fetches:
1. Live Semantic Model (TMDL definition) from Fabric REST API (Dataset {{ISOLATED_MODEL_ID}})
2. Live Report (PBIR definition) from Fabric REST API (Report {{REPORT_ID}})
3. Power Automate Ingestion Package (sharepoint-upsert.zip)
4. SharePoint Publication Registry Seed Data (CSV and JSON)
5. Executive Monthly Word Digest (DOCX)
"""
from __future__ import annotations

import base64
import json
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = ROOT / "downloads/canonical_live_artifacts"
TOKEN_FILE = ROOT / "private/ops/live_token.json"

WS_ID = "{{WORKSPACE_ID}}"
REPORT_ID = "{{REPORT_ID}}"
MODEL_ID = "{{ISOLATED_MODEL_ID}}"


def get_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, str):
        d = json.loads(d)
    return d["token"]


def trigger_get_definition(endpoint_url: str, token: str) -> str:
    req = urllib.request.Request(
        endpoint_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=b"",
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        loc = resp.headers.get("Location")
        if not loc:
            raise RuntimeError(f"No Location header returned from {endpoint_url}")
        return loc


def poll_operation_result(op_url: str, token: str, max_wait: int = 30) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for _ in range(max_wait):
        req = urllib.request.Request(op_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            if status == "Succeeded":
                result_url = op_url + "/result"
                res_req = urllib.request.Request(result_url, headers=headers)
                with urllib.request.urlopen(res_req) as res_resp:
                    return json.loads(res_resp.read().decode("utf-8"))
            elif status == "Failed":
                raise RuntimeError(f"Operation failed: {data}")
        time.sleep(1)
    raise TimeoutError(f"Timed out polling operation {op_url}")


def save_definition_parts(parts: list[dict[str, Any]], out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    for p in parts:
        path_str = p.get("path", "")
        payload_b64 = p.get("payload", "")
        file_path = out_dir / path_str
        file_path.parent.mkdir(parents=True, exist_ok=True)

        raw_bytes = base64.b64decode(payload_b64)
        with open(file_path, "wb") as f:
            f.write(raw_bytes)
        saved_files.append(str(file_path.relative_to(ROOT)))
    return saved_files


def main():
    print(f"Initializing download of live platform artifacts into: {TARGET_DIR}")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    token = get_token()

    # 1. Download Semantic Model TMDL Definition
    print("\n[1/5] Fetching live Semantic Model definition (TMDL)...")
    model_op_url = trigger_get_definition(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WS_ID}/semanticModels/{MODEL_ID}/getDefinition",
        token
    )
    model_res = poll_operation_result(model_op_url, token)
    model_parts = model_res.get("definition", {}).get("parts", [])
    model_dir = TARGET_DIR / "semantic_model"
    saved_model_files = save_definition_parts(model_parts, model_dir)
    print(f"  -> Successfully saved {len(saved_model_files)} Semantic Model parts to {model_dir}")

    # 2. Download Report Definition (PBIR)
    print("\n[2/5] Fetching live Report definition (PBIR)...")
    report_op_url = trigger_get_definition(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WS_ID}/reports/{REPORT_ID}/getDefinition",
        token
    )
    report_res = poll_operation_result(report_op_url, token)
    report_parts = report_res.get("definition", {}).get("parts", [])
    report_dir = TARGET_DIR / "report"
    saved_report_files = save_definition_parts(report_parts, report_dir)
    print(f"  -> Successfully saved {len(saved_report_files)} Report definition parts to {report_dir}")

    # 3. Copy Power Automate Flow Package
    print("\n[3/5] Archiving Power Automate canonical package...")
    flow_dir = TARGET_DIR / "power_automate"
    flow_dir.mkdir(parents=True, exist_ok=True)
    src_flow_pkg = ROOT / "private/ops/flow-packages/sharepoint-upsert.zip"
    dst_flow_pkg = flow_dir / "sharepoint-upsert.zip"
    if src_flow_pkg.exists():
        shutil.copy2(src_flow_pkg, dst_flow_pkg)
        print(f"  -> Copied {src_flow_pkg} to {dst_flow_pkg}")

    src_flow_def = ROOT / "config/flows/publication-registry-upsert.definition.json"
    dst_flow_def = flow_dir / "publication-registry-upsert.definition.json"
    if src_flow_def.exists():
        shutil.copy2(src_flow_def, dst_flow_def)

    # 4. Copy SharePoint Publication Registry Seed Data
    print("\n[4/5] Archiving SharePoint Publication Registry dataset...")
    sp_dir = TARGET_DIR / "sharepoint_registry"
    sp_dir.mkdir(parents=True, exist_ok=True)
    src_csv = ROOT / "private/ops/sharepoint-seed/publication-registry-seed.csv"
    dst_csv = sp_dir / "publication-registry-seed.csv"
    if src_csv.exists():
        shutil.copy2(src_csv, dst_csv)
        print(f"  -> Copied {src_csv} to {dst_csv}")

    src_json = ROOT / "private/ops/sharepoint-seed/publication-registry-seed.json"
    dst_json = sp_dir / "publication-registry-seed.json"
    if src_json.exists():
        shutil.copy2(src_json, dst_json)

    # 5. Copy Executive Word Digest
    print("\n[5/5] Archiving Executive Word Digest...")
    doc_dir = TARGET_DIR / "executive_digest"
    doc_dir.mkdir(parents=True, exist_ok=True)
    src_docx = ROOT / "reports/CHHHS-Publications-Monthly-2026-08.docx"
    dst_docx = doc_dir / "CHHHS-Publications-Monthly-2026-08.docx"
    if src_docx.exists():
        shutil.copy2(src_docx, dst_docx)
        print(f"  -> Copied {src_docx} to {dst_docx}")

    # Generate Manifest
    manifest = {
        "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_id": WS_ID,
        "artifacts": {
            "canonical_report": {
                "id": REPORT_ID,
                "name": "CHHHS Research Publications",
                "parts_count": len(saved_report_files),
                "local_path": str(report_dir.relative_to(ROOT)),
            },
            "canonical_semantic_model": {
                "id": MODEL_ID,
                "name": "CHHHS Research Publications",
                "parts_count": len(saved_model_files),
                "local_path": str(model_dir.relative_to(ROOT)),
            },
            "power_automate_flow": {
                "flow_id": "{{FLOW_ID}}",
                "name": "CHHHS Research Publications - Daily Ingestion & Enrichment",
                "local_package": str(dst_flow_pkg.relative_to(ROOT)),
            },
            "sharepoint_registry": {
                "list_id": "{{SHAREPOINT_LIST_ID}}",
                "name": "Publication Registry",
                "local_csv": str(dst_csv.relative_to(ROOT)),
            },
            "executive_digest": {
                "title": "CHHHS Publications Monthly Digest (August 2026)",
                "local_docx": str(dst_docx.relative_to(ROOT)),
            }
        }
    }
    manifest_file = TARGET_DIR / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nCreated canonical download manifest: {manifest_file}")
    print("Download completed successfully!")


if __name__ == "__main__":
    main()
