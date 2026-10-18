#!/usr/bin/env python3
"""Sync enriched publication registry seed CSV to SharePoint list via Playwright-CLI.

Updates all 1,265 items in-place with:
- MatchedFacilities, CHHHSAffiliatedAuthors, AttributionEvidence
- ReviewStatus ('Included' vs 'Needs Review')
- OpenAlex metrics (OpenAlexID, CitationCount_OpenAlex, OpenAccessStatus, OAUrl)
- Crossref metrics (CitationCount_Crossref, CitationMetricsObservedUTC)
- Bibliometric metadata (MeSHHeadings, AffiliationsRaw, AffiliationHierarchy, FunderNames, GrantIDs)
"""

from __future__ import annotations

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


def load_seed_rows() -> list[dict[str, any]]:
    if not SEED_CSV.exists():
        raise FileNotFoundError(f"Seed CSV not found: {SEED_CSV}")

    items = []
    with open(SEED_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, r in enumerate(reader):
            item_id = idx + 1
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
            if r.get("DORAURL"):
                entry["field_13"] = {
                    "__metadata": {"type": "SP.FieldUrlValue"},
                    "Url": r["DORAURL"],
                    "Description": r["DORAURL"],
                }
            epmc_url = r.get("EuropePMC_FullTextURL")
            if r.get("PMCID") and (not epmc_url or len(epmc_url) > 255):
                epmc_url = f"https://europepmc.org/articles/{r['PMCID']}"
            if epmc_url and len(epmc_url) <= 255:
                entry["Europe_x0020_PMC_x0020_Full_x002"] = {
                    "__metadata": {"type": "SP.FieldUrlValue"},
                    "Url": epmc_url,
                    "Description": clamp_text(f"Europe PMC ({r.get('PMCID', 'Article')})", 255),
                }
            items.append(entry)

    return items


def execute_batch(items_chunk: list[dict[str, any]]) -> dict:
    js_code = f"""async () => {{
      const items = {json.dumps(items_chunk)};
      const digestResp = await fetch('{WEB_URL}/_api/contextinfo', {{
        method: 'POST',
        headers: {{ 'Accept': 'application/json;odata=verbose' }}
      }});
      const digest = (await digestResp.json()).d.GetContextWebInformation.FormDigestValue;

      let successCount = 0;
      let errorCount = 0;
      const errors = [];

      await Promise.all(items.map(async (item) => {{
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
          if (resp.ok) {{
            successCount++;
          }} else {{
            errorCount++;
            errors.push({{ id, status: resp.status, statusText: resp.statusText }});
          }}
        }} catch (err) {{
          errorCount++;
          errors.push({{ id, error: String(err) }});
        }}
      }}));

      return {{ successCount, errorCount, errors }};
    }}"""

    cmd = ["playwright-cli", "-s=chrome", "eval", js_code]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Playwright CLI failed: {res.stderr or res.stdout}")

    # Parse output from playwright-cli
    stdout = res.stdout
    # Locate JSON result after "### Result"
    if "### Result" in stdout:
        json_part = stdout.split("### Result")[1].split("### Ran Playwright code")[0].strip()
        try:
            return json.loads(json_part)
        except Exception as e:
            return {"raw_output": json_part, "parse_error": str(e)}

    return {"raw": stdout}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sync enriched publication registry seed to SharePoint list.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to sync")
    parser.add_argument("--offset", type=int, default=0, help="Offset index to start syncing from")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size per request")
    args = parser.parse_args()

    print(f"Loading seed rows from {SEED_CSV}...")
    items = load_seed_rows()
    total_available = len(items)

    if args.offset:
        items = items[args.offset:]
    if args.limit:
        items = items[:args.limit]

    total = len(items)
    print(f"Items to sync: {total} (from available {total_available}, offset {args.offset})")

    chunk_size = args.batch_size
    chunks = [items[i : i + chunk_size] for i in range(0, total, chunk_size)]
    print(f"Divided into {len(chunks)} batches of {chunk_size} items.")

    total_success = 0
    total_errors = 0
    start_time = time.time()

    for idx, chunk in enumerate(chunks, start=1):
        batch_start = time.time()
        res = execute_batch(chunk)
        duration = time.time() - batch_start

        success = res.get("successCount", 0)
        errors = res.get("errorCount", 0)
        total_success += success
        total_errors += errors

        print(
            f"Batch {idx:02d}/{len(chunks):02d} (IDs {chunk[0]['id']:04d}-{chunk[-1]['id']:04d}): "
            f"OK={success}, Err={errors} ({duration:.1f}s)"
        )

        if errors > 0 and res.get("errors"):
            print(f"   Errors in batch {idx}: {res['errors'][:3]}")

        # Slight pause to prevent rate limiting
        time.sleep(0.5)

    elapsed = time.time() - start_time
    print("-" * 60)
    print(f"Sync complete in {elapsed:.1f}s: Success={total_success}/{total}, Errors={total_errors}")


if __name__ == "__main__":
    main()
