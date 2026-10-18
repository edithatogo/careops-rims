#!/usr/bin/env python3
"""Retry sync for any items in SharePoint seed that had transient errors."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_CSV = ROOT_DIR / "private" / "ops" / "sharepoint-seed" / "publication-registry-seed.csv"
LIST_GUID = "{{SHAREPOINT_LIST_ID}}"
WEB_URL = os.environ.get("SHAREPOINT_WEB_URL", "")
if not WEB_URL:
    raise RuntimeError("Set SHAREPOINT_WEB_URL to the approved SharePoint site/web path")


def clamp_text(val: str | None, max_len: int = 255) -> str | None:
    if not val:
        return None
    val = val.strip()
    return val[:max_len] if len(val) > max_len else val


def build_entry(item_id: int, r: dict[str, str]) -> dict[str, any]:
    entry = {
        "id": item_id,
        "field_14": clamp_text(r.get("MatchedFacilities")),
        "field_15": clamp_text(r.get("CHHHSAffiliatedAuthors")),
        "field_16": r.get("AttributionEvidence") or None,
        "field_17": clamp_text(r.get("ReviewStatus") or "Needs Review"),
        "field_18": clamp_text(r.get("ReviewNotes")),
        "OpenAlexID": clamp_text(r.get("OpenAlexID")),
        "CitationCount_OpenAlex": int(r["CitationCount_OpenAlex"]) if r.get("CitationCount_OpenAlex") else None,
        "OpenAccessStatus": clamp_text(r.get("OpenAccessStatus")),
        "OAUrl": clamp_text(r.get("OAUrl")),
        "MeSHHeadings": r.get("MeSHHeadings") or None,
        "AffiliationsRaw": r.get("AffiliationsRaw") or None,
        "AffiliationHierarchy": r.get("AffiliationHierarchy") or None,
        "CitationCount_Crossref": int(r["CitationCount_Crossref"]) if r.get("CitationCount_Crossref") else None,
        "CitationMetricsObservedUTC": clamp_text(r.get("CitationMetricsObservedUTC")),
        "FunderNames": r.get("FunderNames") or None,
        "GrantIDs": clamp_text(r.get("GrantIDs")),
        "AuthorKeywords": r.get("AuthorKeywords") or None,
        "CitationCount_Scopus": int(r["CitationCount_Scopus"]) if r.get("CitationCount_Scopus") else None,
        "PMCID": clamp_text(r.get("PMCID")),
        "Author_x0020_ORCIDs": r.get("AuthorORCIDs") or None,
        "Funding_x0020_Type": clamp_text(r.get("FundingType")),
        "Internal_x0020_Funding": "Yes" if r.get("IsInternalFunding") in (True, "True", "true", "Yes", "yes", 1, "1") else "No",
        "Clinical_x0020_Trial_x0020_ID": clamp_text(r.get("ClinicalTrialID")),
        "Indigenous_x0020_Health_x0020_Fo": "Yes" if r.get("IndigenousHealthFocus") in (True, "True", "true", "Yes", "yes", 1, "1") else "No",
        "Study_x0020_Design": clamp_text(r.get("StudyDesign")),
        "Field_x0020_of_x0020_Research": clamp_text(r.get("FieldOfResearch")),
        "Europe_x0020_PMC_x0020_Open_x002": clamp_text(r.get("EuropePMC_OpenAccess")),
        "Europe_x0020_PMC_x0020_Citations": int(r["EuropePMC_CitedByCount"]) if r.get("EuropePMC_CitedByCount") else None,
    }
    if r.get("DORAURL") and len(r["DORAURL"]) <= 255:
        entry["field_13"] = {
            "__metadata": {"type": "SP.FieldUrlValue"},
            "Url": r["DORAURL"],
            "Description": clamp_text(r["DORAURL"], 255),
        }
    
    # Safe Europe PMC URL
    epmc_url = r.get("EuropePMC_FullTextURL")
    if r.get("PMCID") and (not epmc_url or len(epmc_url) > 255):
        epmc_url = f"https://europepmc.org/articles/{r['PMCID']}"
    if epmc_url and len(epmc_url) <= 255:
        entry["Europe_x0020_PMC_x0020_Full_x002"] = {
            "__metadata": {"type": "SP.FieldUrlValue"},
            "Url": epmc_url,
            "Description": clamp_text(f"Europe PMC ({r.get('PMCID', 'Article')})", 255),
        }

    return entry


def retry_items(items: list[dict[str, any]]) -> list[dict]:
    js_code = f"""async () => {{
      const items = {json.dumps(items)};
      const digestResp = await fetch('{WEB_URL}/_api/contextinfo', {{
        method: 'POST',
        headers: {{ 'Accept': 'application/json;odata=verbose' }}
      }});
      const digest = (await digestResp.json()).d.GetContextWebInformation.FormDigestValue;

      const results = [];
      for (const item of items) {{
        const id = item.id;
        const body = {{
          '__metadata': {{ 'type': 'SP.Data.Publication_x0020_RegistryListItem' }}
        }};
        for (const [k, v] of Object.entries(item)) {{
          if (k !== 'id' && v !== null && v !== undefined) {{
            body[k] = v;
          }}
        }}
        try {{
          const resp = await fetch(`{WEB_URL}/_api/web/lists(guid'{LIST_GUID}')/items(${{id}})`, {{
            method: 'POST',
            headers: {{
              'Accept': 'application/json;odata=verbose',
              'Content-Type': 'application/json;odata=verbose',
              'X-HTTP-Method': 'MERGE',
              'If-Match': '*',
              'X-RequestDigest': digest
            }},
            body: JSON.stringify(body)
          }});
          results.push({{ id, status: resp.status, ok: resp.ok }});
        }} catch (err) {{
          results.push({{ id, error: String(err), ok: false }});
        }}
      }}
      return results;
    }}"""

    cmd = ["playwright-cli", "-s=chrome", "eval", js_code]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if "### Result" in res.stdout:
        json_part = res.stdout.split("### Result")[1].split("### Ran Playwright code")[0].strip()
        try:
            return json.loads(json_part)
        except Exception:
            return [{"raw": json_part}]
    return [{"raw": res.stdout, "error": res.stderr}]


def main():
    parser = argparse.ArgumentParser(description="Retry failed items on SharePoint list.")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated list of item IDs to retry")
    args = parser.parse_args()

    with open(SEED_CSV, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.ids:
        target_ids = [int(x.strip()) for x in args.ids.split(",") if x.strip().isdigit()]
    else:
        target_ids = [163, 781, 979]

    print(f"Retrying {len(target_ids)} items: {target_ids}...")
    items = [build_entry(item_id, rows[item_id - 1]) for item_id in target_ids if 1 <= item_id <= len(rows)]

    results = retry_items(items)
    print("Retry results:")
    for r in results:
        print(f"  Item {r.get('id')}: status={r.get('status')} ok={r.get('ok')}")


if __name__ == "__main__":
    main()
