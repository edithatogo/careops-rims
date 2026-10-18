"""Deploy updated PBIR-Legacy report definition to isolated report {{ISOLATED_REPORT_ID}} via Fabric REST API."""
from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPDATED_FILE = ROOT / "private/ops/report-definition-updated.json"

def main():
    with open(UPDATED_FILE) as f:
        payload = json.load(f)
        
    script_content = f"""async (page) => {{
        const res = await page.evaluate(async (bodyData) => {{
            const pbiKey = Object.keys(sessionStorage).find(k => k.includes('analysis.windows.net/powerbi/api'));
            const token = JSON.parse(sessionStorage.getItem(pbiKey)).secret;
            
            const updateUrl = 'https://api.fabric.microsoft.com/v1/workspaces/{{WORKSPACE_ID}}/reports/{{ISOLATED_REPORT_ID}}/updateDefinition';
            
            const res = await fetch(updateUrl, {{
                method: 'POST',
                headers: {{
                    'Authorization': 'Bearer ' + token,
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify(bodyData)
            }});
            
            const location = res.headers.get('location');
            return {{
                status: res.status,
                statusText: res.statusText,
                location: location
            }};
        }}, {json.dumps(payload)});
        return JSON.stringify(res);
    }}"""
    
    script_path = ROOT / "private/ops/deploy_report_run.js"
    with open(script_path, "w") as sf:
        sf.write(script_content)
        
    res = subprocess.run([
        "playwright-cli", "-s=chrome", "--raw", "run-code", f"--filename={script_path}"
    ], capture_output=True, text=True)
    
    print("Deploy call output:", res.stdout, res.stderr)
    try:
        data = json.loads(res.stdout.strip())
        if isinstance(data, str):
            data = json.loads(data)
        print("Deploy response:", data)
        location = data.get("location")
        if location:
            print("Polling operation status at:", location)
            poll_content = f"""async (page) => {{
                const res = await page.evaluate(async (loc) => {{
                    const pbiKey = Object.keys(sessionStorage).find(k => k.includes('analysis.windows.net/powerbi/api'));
                    const token = JSON.parse(sessionStorage.getItem(pbiKey)).secret;
                    const r = await fetch(loc, {{
                        headers: {{ 'Authorization': 'Bearer ' + token }}
                    }});
                    return await r.json();
                }}, '{location}');
                return JSON.stringify(res);
            }}"""
            poll_path = ROOT / "private/ops/poll_report_op.js"
            with open(poll_path, "w") as pf:
                pf.write(poll_content)
                
            for attempt in range(10):
                time.sleep(2)
                pres = subprocess.run([
                    "playwright-cli", "-s=chrome", "--raw", "run-code", f"--filename={poll_path}"
                ], capture_output=True, text=True)
                pdata = json.loads(pres.stdout.strip())
                if isinstance(pdata, str):
                    pdata = json.loads(pdata)
                print(f"Poll attempt {attempt + 1}: status = {pdata.get('status')}")
                if pdata.get("status") in ("Succeeded", "Failed"):
                    if pdata.get("status") == "Failed":
                        print("Error details:", pdata.get("error"))
                    break
    except Exception as e:
        print("Error parsing deploy output:", e)

if __name__ == "__main__":
    main()
