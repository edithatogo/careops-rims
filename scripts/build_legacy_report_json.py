"""Build clean PBIR-Legacy report.json matching the 4-page research specification."""
from __future__ import annotations
import json
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_FILE = ROOT / "private/ops/report-definition-backup.json"
OUTPUT_FILE = ROOT / "private/ops/report-definition-updated.json"

def literal(val: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + val.replace("'", "''") + "'"}}}

def col_ref(entity: str, prop: str) -> dict:
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}, "queryRef": f"{entity}.{prop}"}

def met_ref(prop: str) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Publication"}}, "Property": prop}}, "queryRef": f"Publication.{prop}"}

def make_prototype_query(roles: dict) -> dict:
    entities = {}
    selects = []
    
    for role, items in roles.items():
        for item in items:
            qref = item["queryRef"]
            entity, prop = qref.split(".", 1)
            if entity not in entities:
                alias = entity[0].lower() + str(len(entities))
                entities[entity] = alias
            alias = entities[entity]
            
            is_measure = "Measure" in item["field"]
            if is_measure:
                selects.append({
                    "Measure": {
                        "Expression": {"SourceRef": {"Source": alias}},
                        "Property": prop
                    },
                    "Name": qref
                })
            else:
                selects.append({
                    "Column": {
                        "Expression": {"SourceRef": {"Source": alias}},
                        "Property": prop
                    },
                    "Name": qref
                })
                
    from_clause = [{"Name": alias, "Entity": entity, "Type": 0} for entity, alias in entities.items()]
    return {
        "Version": 2,
        "From": from_clause,
        "Select": selects
    }

def make_visual_container(name: str, kind: str, title: str, xywh: tuple, roles: dict | None = None, text: str | None = None, order: int = 0) -> dict:
    x, y, w, h = xywh
    
    single_visual: dict = {
        "visualType": kind,
        "drillFilterOtherVisuals": True
    }
    
    if roles:
        projections = {}
        for role, items in roles.items():
            projections[role] = [{"queryRef": item["queryRef"]} for item in items]
        single_visual["projections"] = projections
        single_visual["prototypeQuery"] = make_prototype_query(roles)
        
    if text is not None:
        single_visual["objects"] = {
            "general": [{
                "properties": {
                    "paragraphs": [{
                        "textRuns": [{
                            "value": text,
                            "textStyle": {
                                "fontFamily": "Segoe UI",
                                "fontSize": "22px" if name == "heading" else "13px",
                                "color": "#0F172A" if name == "heading" else "#475569"
                            }
                        }]
                    }]
                }
            }]
        }
    elif kind == "card":
        is_footer = "refresh" in name or "footer" in name
        font_size = "14D" if is_footer else "22D" if name in ("month", "warnings", "searches") else "28D"
        single_visual["objects"] = {
            "labels": [{
                "properties": {
                    "fontSize": {"expr": {"Literal": {"Value": font_size}}}
                }
            }],
            "categoryLabels": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "false"}}}
                }
            }]
        }
    elif kind == "slicer":
        single_visual["objects"] = {
            "data": [{
                "properties": {
                    "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}
                }
            }],
            "header": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "false"}}}
                }
            }]
        }
    elif kind == "tableEx":
        single_visual["objects"] = {
            "columnHeaders": [{
                "properties": {
                    "columnAdjustment": {"expr": {"Literal": {"Value": "'growToFit'"}}},
                    "autoSizeColumnWidth": {"expr": {"Literal": {"Value": "true"}}},
                    "wordWrap": {"expr": {"Literal": {"Value": "true"}}}
                }
            }],
            "values": [{
                "properties": {
                    "wordWrap": {"expr": {"Literal": {"Value": "true"}}}
                }
            }]
        }
        
    vc_objects = {
        "title": [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "false" if kind == "textbox" else "true"}}},
                "text": literal(title),
                "fontSize": {"expr": {"Literal": {"Value": "15D"}}}
            }
        }],
        "background": [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "false" if kind == "textbox" else "true"}}},
                "transparency": {"expr": {"Literal": {"Value": "0D"}}}
            }
        }]
    }
    if kind in ("slicer", "card"):
        vc_objects["padding"] = [{
            "properties": {
                "top": {"expr": {"Literal": {"Value": "4D" if kind == "card" else "8D"}}},
                "bottom": {"expr": {"Literal": {"Value": "4D" if kind == "card" else "8D"}}},
                "left": {"expr": {"Literal": {"Value": "8D"}}},
                "right": {"expr": {"Literal": {"Value": "8D"}}}
            }
        }]
    single_visual["vcObjects"] = vc_objects
    
    config = {
        "name": name,
        "layouts": [{
            "id": 0,
            "position": {
                "x": x,
                "y": y,
                "z": order * 100,
                "width": w,
                "height": h,
                "tabOrder": order
            }
        }],
        "singleVisual": single_visual
    }
    
    return {
        "x": float(x),
        "y": float(y),
        "z": float(order * 100),
        "width": float(w),
        "height": float(h),
        "filters": "[]",
        "config": json.dumps(config)
    }

def build_all_sections() -> list[dict]:
    sections = []
    
    # Page 1: CHHHS Publications (ReportSection3)
    p1_visuals = []
    p1_visuals.append(make_visual_container("heading", "textbox", "", (32, 16, 1856, 48), text="CHHHS RESEARCH PUBLICATIONS  |  CHHHS Publications", order=0))
    p1_visuals.append(make_visual_container("caption", "textbox", "", (32, 64, 1856, 40), text="PubMed and DORA publication records. Counts remain provisional while identity and institutional scope reviews are open.", order=1))
    
    cards_p1 = [
        ("all-papers", "Canonical publications", "Publications"),
        ("pubmed", "Found in PubMed", "PubMed Publications"),
        ("dora", "Found in DORA", "DORA Publications"),
        ("overlap", "Found in both sources", "Cross-source Matches")
    ]
    p1_card_xs = [32, 504, 976, 1448]
    for idx, (n, t, m) in enumerate(cards_p1):
        p1_visuals.append(make_visual_container(n, "card", t, (p1_card_xs[idx], 112, 440, 96), {"Values": [met_ref(m)]}, order=2 + idx))
        
    p1_visuals.append(make_visual_container("facility-filter", "slicer", "Facility / service", (32, 224, 520, 72), {"Values": [col_ref("Facility", "FacilityName")]}, order=6))
    p1_visuals.append(make_visual_container("year-filter", "slicer", "Publication year", (568, 224, 280, 72), {"Values": [col_ref("Publication", "PublicationYear")]}, order=7))
    p1_visuals.append(make_visual_container("source-filter", "slicer", "Source provenance", (864, 224, 440, 72), {"Values": [col_ref("Publication", "SourceSet")]}, order=8))
    p1_visuals.append(make_visual_container("review-filter", "slicer", "Attribution status", (1320, 224, 568, 72), {"Values": [col_ref("Publication", "AttributionStatus")]}, order=9))
    
    # Executive Analytics Visuals (Replacing raw publication title table)
    p1_visuals.append(make_visual_container("annual-trajectory", "lineChart", "Annual publication trajectory (2014–2026)", (32, 312, 912, 312), {
        "Category": [col_ref("Publication", "PublicationYear")],
        "Y": [met_ref("Publications")]
    }, order=10))
    p1_visuals.append(make_visual_container("facility-breakdown", "barChart", "Publications by CHHHS facility / service", (960, 312, 928, 312), {
        "Category": [col_ref("Facility", "FacilityName")],
        "Y": [met_ref("Publications")]
    }, order=11))
    p1_visuals.append(make_visual_container("attribution-breakdown", "barChart", "Institutional attribution status breakdown", (32, 640, 912, 304), {
        "Category": [col_ref("Publication", "AttributionStatus")],
        "Y": [met_ref("Publications")]
    }, order=12))
    p1_visuals.append(make_visual_container("provenance-breakdown", "donutChart", "Source provenance distribution", (960, 640, 928, 304), {
        "Category": [col_ref("Publication", "SourceSet")],
        "Y": [met_ref("Publications")]
    }, order=13))
    p1_visuals.append(make_visual_container("footer", "card", "Last model refresh (UTC)", (32, 960, 1856, 80), {"Values": [met_ref("Refresh Timestamp UTC")]}, order=14))
    
    sections.append({
        "name": "ReportSection3",
        "displayName": "CHHHS Publications",
        "ordinal": 0,
        "width": 1920.0,
        "height": 1080.0,
        "displayOption": 1,
        "config": "{\"visibility\":0}",
        "filters": "[]",
        "visualContainers": p1_visuals
    })
    
    # Page 2: Monthly Publications (ReportSection2)
    p2_visuals = []
    p2_visuals.append(make_visual_container("heading", "textbox", "", (32, 16, 1856, 48), text="CHHHS RESEARCH PUBLICATIONS  |  Monthly Publications", order=0))
    p2_visuals.append(make_visual_container("caption", "textbox", "", (32, 64, 1856, 40), text="Select one publication month; clear the selection for the previous complete Brisbane month. Publication dates determine inclusion.", order=1))
    
    p2_visuals.append(make_visual_container("month", "card", "Reporting month", (32, 112, 440, 96), {"Values": [met_ref("Reporting Month")]}, order=2))
    p2_visuals.append(make_visual_container("monthly-papers", "card", "Publications in reporting month", (504, 112, 440, 96), {"Values": [met_ref("Selected Month Publications")]}, order=3))
    p2_visuals.append(make_visual_container("month-slicer", "slicer", "Publication month (choose one; clear for default)", (976, 112, 440, 96), {"Values": [col_ref("Date", "YearMonth")]}, order=4))
    p2_visuals.append(make_visual_container("undated", "card", "Records without usable month", (1448, 112, 440, 96), {"Values": [met_ref("Publications Without Usable Month")]}, order=5))
    
    p2_visuals.append(make_visual_container("publication-trend", "barChart", "Facility / service matches in reporting month", (32, 224, 1200, 328), {
        "Category": [col_ref("Facility", "FacilityName")],
        "Y": [met_ref("Selected Month Publications")]
    }, order=6))
    p2_visuals.append(make_visual_container("monthly-source", "donutChart", "Source provenance", (1256, 224, 632, 328), {
        "Category": [col_ref("Publication", "SourceSet")],
        "Y": [met_ref("Selected Month Publications")]
    }, order=7))
    
    # Executive Monthly Analytics (Replacing raw monthly title table)
    p2_visuals.append(make_visual_container("monthly-history-trend", "lineChart", "Monthly publication trend (Last 24 complete months)", (32, 568, 1200, 432), {
        "Category": [col_ref("Date", "YearMonth")],
        "Y": [met_ref("Selected Month Publications")]
    }, order=8))
    p2_visuals.append(make_visual_container("monthly-attribution", "barChart", "Reporting month attribution status", (1256, 568, 632, 432), {
        "Category": [col_ref("Publication", "AttributionStatus")],
        "Y": [met_ref("Selected Month Publications")]
    }, order=9))
    p2_visuals.append(make_visual_container("footer", "textbox", "", (32, 1016, 1856, 32), text="Indexing delays can revise prior months. Partial and absent dates are not silently assigned to January or the refresh date.", order=10))
    
    sections.append({
        "name": "ReportSection2",
        "displayName": "Monthly Publications",
        "ordinal": 1,
        "width": 1920.0,
        "height": 1080.0,
        "displayOption": 1,
        "config": "{\"visibility\":0}",
        "filters": "[]",
        "visualContainers": p2_visuals
    })
    
    # Page 3: Source Reconciliation (ReportSection)
    p3_visuals = []
    p3_visuals.append(make_visual_container("heading", "textbox", "", (32, 16, 1856, 48), text="CHHHS RESEARCH PUBLICATIONS  |  Source Reconciliation", order=0))
    p3_visuals.append(make_visual_container("caption", "textbox", "", (32, 64, 1856, 40), text="Audit PubMed and DORA coverage, deduplication and institutional-attribution evidence before using counts externally.", order=1))
    
    cards_p3 = [
        ("pubmed", "PubMed publications", "PubMed Publications"),
        ("dora", "DORA publications", "DORA Publications"),
        ("dora-only", "DORA-only publications", "DORA-only Publications"),
        ("needs-review", "Needs reconciliation review", "Reconciliation Needs Review")
    ]
    p3_card_xs = [32, 504, 976, 1448]
    for idx, (n, t, m) in enumerate(cards_p3):
        p3_visuals.append(make_visual_container(n, "card", t, (p3_card_xs[idx], 112, 440, 96), {"Values": [met_ref(m)]}, order=2 + idx))
        
    p3_visuals.append(make_visual_container("source-overlap", "donutChart", "Canonical publications by source provenance", (32, 224, 736, 312), {
        "Category": [col_ref("Publication", "SourceSet")],
        "Y": [met_ref("Publications")]
    }, order=6))
    p3_visuals.append(make_visual_container("dedup-method", "barChart", "Reconciliation method", (792, 224, 528, 312), {
        "Category": [col_ref("Publication", "DedupMethod")],
        "Y": [met_ref("Publications")]
    }, order=7))
    p3_visuals.append(make_visual_container("facility-contributions", "tableEx", "PubMed search coverage and warnings", (1344, 224, 544, 312), {
        "Values": [
            col_ref("SearchAudit", "FacilityKey"),
            col_ref("SearchAudit", "SearchCount"),
            col_ref("SearchAudit", "Warnings"),
            col_ref("SearchAudit", "QueryVersion")
        ]
    }, order=8))
    
    table_p3_cols = [
        col_ref("Publication", "Title"),
        col_ref("Publication", "AttributionEvidence"),
        col_ref("Publication", "SourceSet"),
        col_ref("Publication", "DedupMethod"),
        col_ref("Publication", "AttributionStatus"),
        col_ref("Publication", "CHHHSAffiliatedAuthors"),
        col_ref("Publication", "MatchedFacilities"),
        col_ref("Publication", "PMID"),
        col_ref("Publication", "DORAURL")
    ]
    p3_visuals.append(make_visual_container("reconciliation-register", "tableEx", "Reconciliation and attribution register", (32, 552, 1856, 352), {"Values": table_p3_cols}, order=9))
    
    p3_visuals.append(make_visual_container("refresh-time", "card", "Last model refresh (UTC)", (32, 912, 584, 96), {"Values": [met_ref("Refresh Timestamp UTC")]}, order=10))
    p3_visuals.append(make_visual_container("warnings", "card", "PubMed queries with warnings", (640, 912, 584, 96), {"Values": [met_ref("Query Warnings")]}, order=11))
    p3_visuals.append(make_visual_container("searches", "card", "Configured PubMed affiliation searches", (1248, 912, 640, 96), {"Values": [met_ref("Configured Facility Searches")]}, order=12))
    p3_visuals.append(make_visual_container("footer", "textbox", "", (32, 1016, 1856, 32), text="Identifier conflicts and title/year candidates remain separate for review. DORA coverage is an observed collection snapshot; durable history and native count acceptance remain pending.", order=13))
    
    sections.append({
        "name": "ReportSection",
        "displayName": "Source Reconciliation",
        "ordinal": 2,
        "width": 1920.0,
        "height": 1080.0,
        "displayOption": 1,
        "config": "{\"visibility\":0}",
        "filters": "[]",
        "visualContainers": p3_visuals
    })

    # Page 4: Clinical Analytics & Research Intelligence (ReportSection4)
    p4_visuals = []
    p4_visuals.append(make_visual_container("heading", "textbox", "", (32, 16, 1856, 48), text="CHHHS RESEARCH PUBLICATIONS  |  Clinical Analytics & Research Intelligence", order=0))
    p4_visuals.append(make_visual_container("caption", "textbox", "", (32, 64, 1856, 40), text="Clinical directorate specialty mapping, ANZSRC Field of Research (FoR) classification, Open Access compliance, and clinical trial activity.", order=1))

    cards_p4 = [
        ("oa-rate", "Open access compliance rate", "Open Access Rate"),
        ("oa-papers", "Open access publications", "Open Access Publications"),
        ("trials-count", "Clinical trial linked papers", "Clinical Trials Count"),
        ("funded-papers", "Grant-funded publications", "Funded Publications")
    ]
    p4_card_xs = [32, 504, 976, 1448]
    for idx, (n, t, m) in enumerate(cards_p4):
        p4_visuals.append(make_visual_container(n, "card", t, (p4_card_xs[idx], 112, 440, 96), {"Values": [met_ref(m)]}, order=2 + idx))

    p4_visuals.append(make_visual_container("facility-filter", "slicer", "Clinical facility / service", (32, 224, 608, 72), {"Values": [col_ref("Facility", "FacilityName")]}, order=6))
    p4_visuals.append(make_visual_container("year-filter", "slicer", "Publication year", (656, 224, 304, 72), {"Values": [col_ref("Publication", "PublicationYear")]}, order=7))
    p4_visuals.append(make_visual_container("oa-filter", "slicer", "Open access status", (976, 224, 440, 72), {"Values": [col_ref("Publication", "OpenAccessStatus")]}, order=8))
    p4_visuals.append(make_visual_container("study-filter", "slicer", "Study design", (1432, 224, 456, 72), {"Values": [col_ref("Publication", "StudyDesign")]}, order=9))

    p4_visuals.append(make_visual_container("specialty-distribution", "barChart", "Publications by clinical directorate and specialty", (32, 312, 912, 312), {
        "Category": [col_ref("Facility", "FacilityName")],
        "Y": [met_ref("Publications")]
    }, order=10))
    p4_visuals.append(make_visual_container("for-division", "barChart", "ANZSRC 2020 Field of Research (FoR) division", (960, 312, 928, 312), {
        "Category": [col_ref("Publication", "FieldOfResearch")],
        "Y": [met_ref("Publications")]
    }, order=11))

    p4_visuals.append(make_visual_container("oa-distribution", "donutChart", "Open access distribution (Gold / Green / Hybrid / Closed)", (32, 640, 912, 304), {
        "Category": [col_ref("Publication", "OpenAccessStatus")],
        "Y": [met_ref("Publications")]
    }, order=12))
    p4_visuals.append(make_visual_container("study-design-breakdown", "barChart", "Evidence hierarchy and study designs", (960, 640, 928, 304), {
        "Category": [col_ref("Publication", "StudyDesign")],
        "Y": [met_ref("Publications")]
    }, order=13))

    p4_visuals.append(make_visual_container("footer", "textbox", "", (32, 960, 1856, 40), text="Field of Research mapped using ANZSRC 2020 2-digit divisions. Open access classification verified via Europe PMC and OpenAlex APIs in accordance with the NHMRC Open Access Policy.", order=14))

    sections.append({
        "name": "ReportSection4",
        "displayName": "Clinical Analytics",
        "ordinal": 3,
        "width": 1920.0,
        "height": 1080.0,
        "displayOption": 1,
        "config": "{\"visibility\":0}",
        "filters": "[]",
        "visualContainers": p4_visuals
    })
    
    return sections

def main():
    with open(BACKUP_FILE) as f:
        raw = json.load(f)
        data = json.loads(raw) if isinstance(raw, str) else raw

    parts = data.get("definition", {}).get("parts", [])
    report_part = next(p for p in parts if p["path"] == "report.json")
    report_content = json.loads(base64.b64decode(report_part["payload"]).decode("utf-8"))

    sections = build_all_sections()
    report_content["sections"] = sections
    
    valid_section_names = {s["name"] for s in sections}
    report_content["pods"] = [
        p for p in report_content.get("pods", [])
        if p.get("boundSection") in valid_section_names and "Employee" not in str(p)
    ]
    
    total_visuals = sum(len(s["visualContainers"]) for s in sections)
    print(f"Generated {len(sections)} sections with {total_visuals} total visuals.")
    
    updated_payload = base64.b64encode(json.dumps(report_content, separators=(",", ":")).encode("utf-8")).decode("utf-8")
    report_part["payload"] = updated_payload
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"definition": {"parts": parts}}, f)
        
    print(f"Wrote updated definition to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
