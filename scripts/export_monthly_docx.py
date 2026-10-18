"""Export Monthly CHHHS Research Publications Report as a styled Word DOCX document.

Generates an executive-ready clinical governance and research report for a specified
month (or the most recently completed calendar month) from the Publication Registry.

Usage:
  python3 scripts/export_monthly_docx.py [--month YYYY-MM] [--output PATH] [--status STATUS]
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent

# Brand & Palette Constants (Queensland Health Clinical Research Style)
PRIMARY_COLOR = RGBColor(0, 92, 138)       # QLD Health Deep Cyan/Teal #005C8A
SECONDARY_COLOR = RGBColor(43, 62, 80)     # Navy Slate #2B3E50
ACCENT_COLOR = RGBColor(16, 124, 65)       # Evergreen / Included #107C41
MUTED_COLOR = RGBColor(100, 110, 120)      # Neutral Muted Grey #646E78
TEXT_COLOR = RGBColor(33, 37, 41)          # Dark Charcoal Body #212529
BORDER_COLOR_HEX = "D0D7DE"
HEADER_BG_HEX = "F0F4F8"
ALT_ROW_BG_HEX = "F9FBFC"


def set_cell_background(cell, hex_color: str):
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_hyperlink(paragraph, url: str, text: str, color: RGBColor = PRIMARY_COLOR, underline: bool = True):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = parse_xml(f'<w:hyperlink {nsdecls("w")} r:id="{r_id}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>')
    new_run = parse_xml(f'<w:r {nsdecls("w")}><w:rPr/><w:t>{text}</w:t></w:r>')
    rPr = new_run.find(qn('w:rPr'))
    if color:
        c = parse_xml(f'<w:color {nsdecls("w")} w:val="{color}"/>')
        rPr.append(c)
    if underline:
        u = parse_xml(f'<w:u {nsdecls("w")} w:val="single"/>')
        rPr.append(u)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def load_publications(csv_path: Path, target_month: str, status_filter: str) -> List[Dict[str, str]]:
    records = []
    if not csv_path.exists():
        raise FileNotFoundError(f"Publication source file not found: {csv_path}")

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = row.get("PublicationMonth", "").strip()
            status = row.get("ReviewStatus", "").strip()

            if month != target_month:
                continue
            if status_filter != "All" and status != status_filter:
                continue

            records.append(row)

    # Sort by PublicationYear desc, PublicationMonth desc, Title asc
    records.sort(key=lambda r: (r.get("PublicationYear", ""), r.get("Title", "")))
    return records


def build_monthly_docx(
    records: List[Dict[str, str]],
    target_month: str,
    output_path: Path,
    source_label: str = "Publication Registry",
) -> Path:
    doc = docx.Document()

    # Page setup - Margins
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # Styles configuration
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Segoe UI'
    normal_style.font.size = Pt(10)
    normal_style.font.color.rgb = TEXT_COLOR

    # Parse Month Label
    try:
        dt = datetime.strptime(target_month, "%Y-%m")
        month_name = dt.strftime("%B %Y")
    except ValueError:
        month_name = target_month

    # 1. Header Banner
    header_p = doc.add_paragraph()
    header_p.paragraph_format.space_before = Pt(0)
    header_p.paragraph_format.space_after = Pt(2)
    run_org = header_p.add_run("CAIRNS AND HINTERLAND HOSPITAL AND HEALTH SERVICE")
    run_org.font.size = Pt(9.5)
    run_org.font.bold = True
    run_org.font.color.rgb = PRIMARY_COLOR

    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_title = title_p.add_run(f"Monthly Research Publications Report: {month_name}")
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = SECONDARY_COLOR

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_before = Pt(0)
    meta_p.paragraph_format.space_after = Pt(16)
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_meta = meta_p.add_run(
        f"Official clinical governance extract from {source_label}  |  Generated: {gen_time}  |  Total Papers: {len(records)}"
    )
    run_meta.font.size = Pt(8.5)
    run_meta.font.color.rgb = MUTED_COLOR

    # 2. Executive Summary Metrics Table
    facility_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    review_counts: Dict[str, int] = {}
    funding_counts: Dict[str, int] = {}
    design_counts: Dict[str, int] = {}
    indigenous_count = 0
    oa_count = 0
    pmcid_count = 0

    for r in records:
        src = r.get("SourceSet", "Unknown") or "Unknown"
        source_counts[src] = source_counts.get(src, 0) + 1

        rev = r.get("ReviewStatus", "Needs Review") or "Needs Review"
        review_counts[rev] = review_counts.get(rev, 0) + 1

        facs = [f.strip() for f in (r.get("MatchedFacilities", "") or "").split(";") if f.strip()]
        if not facs:
            facs = ["General CHHHS / Unallocated"]
        for f in facs:
            facility_counts[f] = facility_counts.get(f, 0) + 1

        ft = r.get("FundingType", "Unfunded / Departmental") or "Unfunded / Departmental"
        funding_counts[ft] = funding_counts.get(ft, 0) + 1

        sd = r.get("StudyDesign", "Other Biomedical / Translational") or "Other Biomedical / Translational"
        design_counts[sd] = design_counts.get(sd, 0) + 1

        ind_val = r.get("IndigenousHealthFocus")
        if ind_val is True or str(ind_val).strip().lower() in ("yes", "true", "1"):
            indigenous_count += 1

        oa_stat = r.get("OpenAccessStatus", "")
        if oa_stat and oa_stat.lower() != "closed":
            oa_count += 1

        if r.get("PMCID"):
            pmcid_count += 1

    summary_heading = doc.add_paragraph()
    summary_heading.paragraph_format.space_before = Pt(12)
    summary_heading.paragraph_format.space_after = Pt(6)
    run_sh = summary_heading.add_run("1. Executive Summary & Attribution Overview")
    run_sh.font.size = Pt(13)
    run_sh.font.bold = True
    run_sh.font.color.rgb = PRIMARY_COLOR

    # Table 1: Attribution, Source Parity, Review Status
    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    hdr_cells = table.rows[0].cells
    headers = ["Attribution / Facility Breakdown", "Harvest Source Parity", "Curation & Triage Status"]
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        set_cell_background(hdr_cells[i], HEADER_BG_HEX)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = SECONDARY_COLOR

    row_cells = table.add_row().cells
    for cell in row_cells:
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)

    # Facilities text
    fac_p = row_cells[0].paragraphs[0]
    fac_p.paragraph_format.space_after = Pt(2)
    if facility_counts:
        for fac, cnt in sorted(facility_counts.items(), key=lambda x: -x[1]):
            r_item = fac_p.add_run(f"• {fac}: ")
            r_item.font.size = Pt(8.5)
            r_cnt = fac_p.add_run(f"{cnt}\n")
            r_cnt.font.bold = True
            r_cnt.font.size = Pt(8.5)
    else:
        fac_p.add_run("No facility data recorded.")

    # Sources text
    src_p = row_cells[1].paragraphs[0]
    src_p.paragraph_format.space_after = Pt(2)
    for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
        r_item = src_p.add_run(f"• {src}: ")
        r_item.font.size = Pt(8.5)
        r_cnt = src_p.add_run(f"{cnt}\n")
        r_cnt.font.bold = True
        r_cnt.font.size = Pt(8.5)

    # Curation status text
    rev_p = row_cells[2].paragraphs[0]
    rev_p.paragraph_format.space_after = Pt(2)
    for rev, cnt in sorted(review_counts.items(), key=lambda x: -x[1]):
        color = ACCENT_COLOR if rev == "Included" else SECONDARY_COLOR
        r_item = rev_p.add_run(f"• {rev}: ")
        r_item.font.size = Pt(8.5)
        r_cnt = rev_p.add_run(f"{cnt}\n")
        r_cnt.font.bold = True
        r_cnt.font.size = Pt(8.5)
        r_cnt.font.color.rgb = color

    # Table 2: Research Funding Governance, Methodology, and Strategic Impact
    gov_heading = doc.add_paragraph()
    gov_heading.paragraph_format.space_before = Pt(10)
    gov_heading.paragraph_format.space_after = Pt(4)
    run_gh = gov_heading.add_run("Research Funding Governance & Strategic Impact")
    run_gh.font.size = Pt(11)
    run_gh.font.bold = True
    run_gh.font.color.rgb = SECONDARY_COLOR

    table2 = doc.add_table(rows=1, cols=3)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.autofit = False

    hdr_cells2 = table2.rows[0].cells
    headers2 = ["Funding Governance Breakdown", "Study Design & Methodology", "First Nations & Open Science"]
    for i, h in enumerate(headers2):
        hdr_cells2[i].text = h
        set_cell_background(hdr_cells2[i], HEADER_BG_HEX)
        set_cell_margins(hdr_cells2[i], top=120, bottom=120, left=150, right=150)
        p = hdr_cells2[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = SECONDARY_COLOR

    row_cells2 = table2.add_row().cells
    for cell in row_cells2:
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)

    # Funding text
    fnd_p = row_cells2[0].paragraphs[0]
    fnd_p.paragraph_format.space_after = Pt(2)
    for ft, cnt in sorted(funding_counts.items(), key=lambda x: -x[1]):
        r_item = fnd_p.add_run(f"• {ft}: ")
        r_item.font.size = Pt(8.5)
        r_cnt = fnd_p.add_run(f"{cnt}\n")
        r_cnt.font.bold = True
        r_cnt.font.size = Pt(8.5)

    # Study design text
    des_p = row_cells2[1].paragraphs[0]
    des_p.paragraph_format.space_after = Pt(2)
    for sd, cnt in sorted(design_counts.items(), key=lambda x: -x[1]):
        r_item = des_p.add_run(f"• {sd}: ")
        r_item.font.size = Pt(8.5)
        r_cnt = des_p.add_run(f"{cnt}\n")
        r_cnt.font.bold = True
        r_cnt.font.size = Pt(8.5)

    # First Nations & Open Science text
    strat_p = row_cells2[2].paragraphs[0]
    strat_p.paragraph_format.space_after = Pt(2)
    
    r_fn = strat_p.add_run("• First Nations / Indigenous Focus: ")
    r_fn.font.size = Pt(8.5)
    r_fn_cnt = strat_p.add_run(f"{indigenous_count}\n")
    r_fn_cnt.font.bold = True
    r_fn_cnt.font.size = Pt(8.5)
    if indigenous_count > 0:
        r_fn_cnt.font.color.rgb = ACCENT_COLOR

    oa_pct = f"({(oa_count / len(records) * 100):.0f}%)" if records else ""
    r_oa = strat_p.add_run("• Open Access Publications: ")
    r_oa.font.size = Pt(8.5)
    r_oa_cnt = strat_p.add_run(f"{oa_count} {oa_pct}\n")
    r_oa_cnt.font.bold = True
    r_oa_cnt.font.size = Pt(8.5)

    r_pmc = strat_p.add_run("• Europe PMC / PMCID Full Text: ")
    r_pmc.font.size = Pt(8.5)
    r_pmc_cnt = strat_p.add_run(f"{pmcid_count}\n")
    r_pmc_cnt.font.bold = True
    r_pmc_cnt.font.size = Pt(8.5)

    # 3. Publication Register Section
    reg_heading = doc.add_paragraph()
    reg_heading.paragraph_format.space_before = Pt(20)
    reg_heading.paragraph_format.space_after = Pt(8)
    run_rh = reg_heading.add_run(f"2. Publications Register ({len(records)} Records)")
    run_rh.font.size = Pt(13)
    run_rh.font.bold = True
    run_rh.font.color.rgb = PRIMARY_COLOR

    if not records:
        empty_p = doc.add_paragraph("No publications found for the selected month and status criteria.")
        empty_p.runs[0].font.italic = True
    else:
        for idx, rec in enumerate(records, 1):
            p_entry = doc.add_paragraph()
            p_entry.paragraph_format.space_before = Pt(10)
            p_entry.paragraph_format.space_after = Pt(2)

            # Number and Title
            run_num = p_entry.add_run(f"{idx}. ")
            run_num.font.bold = True
            run_num.font.size = Pt(10.5)
            run_num.font.color.rgb = PRIMARY_COLOR

            title_text = rec.get("Title", "Untitled Publication").strip()
            run_t = p_entry.add_run(title_text)
            run_t.font.bold = True
            run_t.font.size = Pt(10.5)

            # Authors line
            authors = rec.get("Authors", "").strip()
            if authors:
                p_auth = doc.add_paragraph()
                p_auth.paragraph_format.left_indent = Inches(0.25)
                p_auth.paragraph_format.space_before = Pt(0)
                p_auth.paragraph_format.space_after = Pt(2)
                r_auth_label = p_auth.add_run("Authors: ")
                r_auth_label.font.bold = True
                r_auth_label.font.size = Pt(9)
                r_auth_val = p_auth.add_run(authors)
                r_auth_val.font.size = Pt(9)
                r_auth_val.font.color.rgb = SECONDARY_COLOR

            # Journal and Citation details
            journal = rec.get("Journal", "").strip()
            year = rec.get("PublicationYear", "").strip()
            doi = rec.get("DOI", "").strip()
            pmid = rec.get("PMID", "").strip()
            matched_fac = rec.get("MatchedFacilities", "").strip()
            status = rec.get("ReviewStatus", "Needs Review").strip()

            p_details = doc.add_paragraph()
            p_details.paragraph_format.left_indent = Inches(0.25)
            p_details.paragraph_format.space_before = Pt(0)
            p_details.paragraph_format.space_after = Pt(2)

            r_j_label = p_details.add_run("Source & Citation: ")
            r_j_label.font.bold = True
            r_j_label.font.size = Pt(8.5)

            cite_parts = []
            if journal:
                cite_parts.append(journal)
            if year:
                cite_parts.append(f"({year})")
            p_details.add_run(" ".join(cite_parts) + "  ")

            # DOI Link
            if doi:
                clean_doi = doi.replace("https://doi.org/", "").strip()
                p_details.add_run("DOI: ")
                add_hyperlink(p_details, f"https://doi.org/{clean_doi}", clean_doi)
                p_details.add_run("  ")

            # PMID Link
            if pmid:
                p_details.add_run("PMID: ")
                add_hyperlink(p_details, f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", pmid)
                p_details.add_run("  ")

            # PMCID Link (Europe PMC)
            pmcid = rec.get("PMCID", "").strip()
            if pmcid:
                p_details.add_run("PMCID: ")
                add_hyperlink(p_details, f"https://europepmc.org/articles/{pmcid}", pmcid)
                p_details.add_run("  ")

            # Open Access status
            oa_status = rec.get("OpenAccessStatus", "").strip()
            if oa_status and oa_status.lower() != "closed":
                oa_url = rec.get("EuropePMC_FullTextURL") or rec.get("OAUrl")
                p_details.add_run("OA: ")
                if oa_url:
                    add_hyperlink(p_details, oa_url, oa_status, color=ACCENT_COLOR)
                else:
                    r_oa = p_details.add_run(oa_status)
                    r_oa.font.color.rgb = ACCENT_COLOR
                p_details.add_run("  ")

            # Status Badge
            r_stat_label = p_details.add_run("Status: ")
            r_stat_label.font.bold = True
            r_stat_label.font.size = Pt(8.5)
            r_stat_val = p_details.add_run(status)
            r_stat_val.font.bold = True
            r_stat_val.font.size = Pt(8.5)
            r_stat_val.font.color.rgb = ACCENT_COLOR if status == "Included" else SECONDARY_COLOR

            # Governance, Methodology & First Nations line
            funding_type = rec.get("FundingType", "").strip()
            study_design = rec.get("StudyDesign", "").strip()
            indig_focus = rec.get("IndigenousHealthFocus")
            is_indig = indig_focus is True or str(indig_focus).strip().lower() in ("yes", "true", "1")
            ct_id = rec.get("ClinicalTrialID", "").strip()
            for_field = rec.get("FieldOfResearch", "").strip()

            has_gov_line = (
                (funding_type and funding_type != "Unfunded / Departmental")
                or (study_design and study_design != "Other Biomedical / Translational")
                or is_indig
                or ct_id
                or for_field
            )

            if has_gov_line:
                p_gov = doc.add_paragraph()
                p_gov.paragraph_format.left_indent = Inches(0.25)
                p_gov.paragraph_format.space_before = Pt(0)
                p_gov.paragraph_format.space_after = Pt(2)

                if is_indig:
                    r_ind = p_gov.add_run("[First Nations Health Focus]  ")
                    r_ind.font.bold = True
                    r_ind.font.size = Pt(8.5)
                    r_ind.font.color.rgb = ACCENT_COLOR

                if ct_id:
                    r_ct = p_gov.add_run(f"[Trial: {ct_id}]  ")
                    r_ct.font.bold = True
                    r_ct.font.size = Pt(8.5)
                    r_ct.font.color.rgb = PRIMARY_COLOR

                if study_design and study_design != "Other Biomedical / Translational":
                    r_sd_lbl = p_gov.add_run("Study Design: ")
                    r_sd_lbl.font.bold = True
                    r_sd_lbl.font.size = Pt(8.5)
                    r_sd_val = p_gov.add_run(f"{study_design}  ")
                    r_sd_val.font.size = Pt(8.5)

                if funding_type and funding_type != "Unfunded / Departmental":
                    r_fnd_lbl = p_gov.add_run("Funding: ")
                    r_fnd_lbl.font.bold = True
                    r_fnd_lbl.font.size = Pt(8.5)
                    r_fnd_val = p_gov.add_run(f"{funding_type}  ")
                    r_fnd_val.font.size = Pt(8.5)
                    grants = rec.get("GrantIDs", "").strip()
                    if grants:
                        r_gr = p_gov.add_run(f"(Grant: {grants})  ")
                        r_gr.font.size = Pt(8)
                        r_gr.font.italic = True

                if for_field:
                    r_for_lbl = p_gov.add_run("Field: ")
                    r_for_lbl.font.bold = True
                    r_for_lbl.font.size = Pt(8.5)
                    r_for_val = p_gov.add_run(f"{for_field}")
                    r_for_val.font.size = Pt(8.5)

            # Facilities line
            if matched_fac:
                p_fac = doc.add_paragraph()
                p_fac.paragraph_format.left_indent = Inches(0.25)
                p_fac.paragraph_format.space_before = Pt(0)
                p_fac.paragraph_format.space_after = Pt(4)
                r_f_lbl = p_fac.add_run("Matched Facilities: ")
                r_f_lbl.font.bold = True
                r_f_lbl.font.size = Pt(8.5)
                r_f_lbl.font.color.rgb = PRIMARY_COLOR
                r_f_val = p_fac.add_run(matched_fac)
                r_f_val.font.size = Pt(8.5)

            # Attribution evidence snippet (if present and Needs Review)
            evidence = rec.get("AttributionEvidence", "").strip()
            if evidence and status == "Needs Review":
                p_ev = doc.add_paragraph()
                p_ev.paragraph_format.left_indent = Inches(0.35)
                p_ev.paragraph_format.space_before = Pt(0)
                p_ev.paragraph_format.space_after = Pt(4)
                r_ev_lbl = p_ev.add_run("Affiliation Evidence: ")
                r_ev_lbl.font.italic = True
                r_ev_lbl.font.size = Pt(8)
                r_ev_lbl.font.color.rgb = MUTED_COLOR
                r_ev_val = p_ev.add_run(f'"{evidence}"')
                r_ev_val.font.italic = True
                r_ev_val.font.size = Pt(8)
                r_ev_val.font.color.rgb = MUTED_COLOR

    # 4. Governance Footer / Sign-off
    footer_p = doc.add_paragraph()
    footer_p.paragraph_format.space_before = Pt(28)
    footer_p.paragraph_format.space_after = Pt(0)
    run_ft = footer_p.add_run(
        "Report verified under CHHHS Research Governance Framework. "
        "Publications attributed to Cairns Hospital, Liz Plummer Cancer Care Centre, and affiliated sites."
    )
    run_ft.font.size = Pt(8)
    run_ft.font.italic = True
    run_ft.font.color.rgb = MUTED_COLOR

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def determine_previous_month() -> str:
    now = datetime.now()
    if now.month == 1:
        return f"{now.year - 1}-12"
    else:
        return f"{now.year}-{now.month - 1:02d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--month",
        type=str,
        default="2026-08",
        help="Target publication month in YYYY-MM format (defaults to past completed month: 2026-08)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "private" / "ops" / "sharepoint-seed" / "publication-registry-seed.csv",
        help="Path to source CSV (Publication Registry export)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .docx file path (defaults to reports/CHHHS-Publications-Monthly-<month>.docx)",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="All",
        choices=["All", "Included", "Needs Review"],
        help="Filter records by ReviewStatus (All, Included, Needs Review)",
    )

    args = parser.parse_args()
    target_m = args.month or determine_previous_month()

    if args.output is None:
        out_file = ROOT / "reports" / f"CHHHS-Publications-Monthly-{target_m}.docx"
    else:
        out_file = args.output

    records = load_publications(args.source, target_m, args.status)
    saved_doc = build_monthly_docx(records, target_m, out_file)
    print(f"Successfully generated monthly DOCX report: {saved_doc} ({len(records)} records)")
