#!/usr/bin/env python3
"""Create keyless research governance and funding fields on SharePoint list."""
import json
import os
import subprocess
import sys
import time

LIST_GUID = "{{SHAREPOINT_LIST_ID}}"
WEB_URL = os.environ.get("SHAREPOINT_WEB_URL", "")
if not WEB_URL:
    raise RuntimeError("Set SHAREPOINT_WEB_URL to the approved SharePoint site/web path")

FIELDS_XML = [
    '<Field Type="Note" Name="AuthorORCIDs" DisplayName="Author ORCIDs" NumLines="3" />',
    '<Field Type="Choice" Name="FundingType" DisplayName="Funding Type" Indexed="TRUE"><CHOICES><CHOICE>Commonwealth (NHMRC/MRFF)</CHOICE><CHOICE>State / Qld Health</CHOICE><CHOICE>Philanthropic / Foundation</CHOICE><CHOICE>Commercial / Industry Trial</CHOICE><CHOICE>University Partner</CHOICE><CHOICE>Unfunded / Departmental</CHOICE><CHOICE>Other External Funder</CHOICE></CHOICES></Field>',
    '<Field Type="Choice" Name="IsInternalFunding" DisplayName="Internal Funding"><CHOICES><CHOICE>Yes</CHOICE><CHOICE>No</CHOICE></CHOICES></Field>',
    '<Field Type="Text" Name="ClinicalTrialID" DisplayName="Clinical Trial ID" Indexed="TRUE" />',
    '<Field Type="Choice" Name="IndigenousHealthFocus" DisplayName="Indigenous Health Focus" Indexed="TRUE"><CHOICES><CHOICE>Yes</CHOICE><CHOICE>No</CHOICE></CHOICES></Field>',
    '<Field Type="Choice" Name="StudyDesign" DisplayName="Study Design" Indexed="TRUE"><CHOICES><CHOICE>Randomized Controlled Trial</CHOICE><CHOICE>Systematic Review / Meta-Analysis</CHOICE><CHOICE>Observational / Cohort Study</CHOICE><CHOICE>Clinical Practice Guideline</CHOICE><CHOICE>Case Report</CHOICE><CHOICE>Other Biomedical / Translational</CHOICE></CHOICES></Field>',
    '<Field Type="Text" Name="FieldOfResearch" DisplayName="Field of Research" />',
    '<Field Type="Text" Name="EuropePMC_OpenAccess" DisplayName="Europe PMC Open Access" />',
    '<Field Type="URL" Name="EuropePMC_FullTextURL" DisplayName="Europe PMC Full Text URL" />',
    '<Field Type="Number" Name="EuropePMC_CitedByCount" DisplayName="Europe PMC Citations" />',
]


def create_field(xml: str) -> dict:
    js_code = f"""async () => {{
      const digestResp = await fetch('{WEB_URL}/_api/contextinfo', {{
        method: 'POST',
        headers: {{ 'Accept': 'application/json;odata=verbose' }}
      }});
      const digest = (await digestResp.json()).d.GetContextWebInformation.FormDigestValue;

      const resp = await fetch("{WEB_URL}/_api/web/lists(guid'{LIST_GUID}')/fields/createFieldAsXml", {{
        method: 'POST',
        headers: {{
          'Accept': 'application/json;odata=verbose',
          'Content-Type': 'application/json;odata=verbose',
          'X-RequestDigest': digest
        }},
        body: JSON.stringify({{
          parameters: {{
            '__metadata': {{ 'type': 'SP.XmlSchemaFieldCreationInformation' }},
            'SchemaXml': {json.dumps(xml)}
          }}
        }})
      }});
      const res = await resp.json();
      return {{ status: resp.status, ok: resp.ok, data: res }};
    }}"""

    cmd = ["playwright-cli", "-s=chrome", "eval", js_code]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return {"error": res.stderr or res.stdout}

    stdout = res.stdout
    if "### Result" in stdout:
        json_part = stdout.split("### Result")[1].split("### Ran Playwright code")[0].strip()
        try:
            return json.loads(json_part)
        except Exception:
            return {"raw": json_part}
    return {"raw": stdout}


def main():
    print("Creating fields on SharePoint list...")
    for fxml in FIELDS_XML:
        name = fxml.split('Name="')[1].split('"')[0]
        print(f"Creating field: {name}...")
        res = create_field(fxml)
        if res.get("ok"):
            print(f"  OK: {name} created.")
        else:
            print(f"  Result for {name}: {res}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
