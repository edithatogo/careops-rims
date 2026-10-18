# Specification: E04 Microsoft Fluent 2 Visual Polishing and IBCS Standards Alignment

## 1. Overview & Visual Design Mandate
Power BI dashboards for hospital executive leadership must convey complex bibliometric and governance data with zero visual clutter, strict typographic hierarchy, and unambiguous navigation.

This track establishes the design standards adhering to **Microsoft Fluent 2 design language** and **International Business Communication Standards (IBCS)**:
1. **8-Point Base Grid:** Exact geometric alignment across all page canvases.
2. **Modern New Card Visuals:** KPI summary cards with integrated reference labels.
3. **Horizontal Bar Charts:** Used exclusively for clinical specialty breakdowns to ensure legibility of lengthy departmental names.
4. **Custom Report Tooltip Canvas:** Hover cards showing rich contextual citation metadata without page switching.
5. **Accessible Color System:** High-contrast neutral palette (`#323130`, `#605E5C`, `#FFFFFF`) with purposeful accent colors (`#00828A` Queensland Health teal).

## 2. Detailed Standards
### A. Grid System & Canvas Spacing
- Target Resolution: Full High Definition (FHD 1920x1080, 16:9 aspect ratio).
- Outer Page Margins: Exactly 32px left/right/top/bottom.
- Visual Gutters: Exactly 16px horizontal and vertical spacing between neighboring cards.
- Coordinate Math: Every visual's `x`, `y`, `width`, and `height` must satisfy `n % 8 == 0`.

### B. Visual Archetypes
| Visual Archetype | Purpose | Standard Configuration |
| :--- | :--- | :--- |
| **New Card Visual** | Headline KPIs (Total Publications, Open Access %, Cairns-Led) | Accent bar left, primary metric 32pt Segoe UI Bold, reference label 11pt with YoY delta and % share. |
| **Horizontal Bar Chart** | Specialty Breakdown & Directorate Attribution | Sorted descending by volume, data labels on inside end, no truncated text or rotated category labels. |
| **Line & Area Chart** | Multi-Year Publication Trajectory | Direct data labels on final data points, subtle grey gridlines, zero decorative 3D effects. |
| **Matrix & Table** | Reconciled Publication Register | Alternating row fills (`#F3F2F1`), sticky headers, monospace DOI and PMID links. |
| **Modern Tooltip** | Contextual Hover Card | 320x200 canvas displaying Title, All Authors, Journal, Open Access status, and Citation count. |

## 3. Acceptance Criteria
- [x] All visual positions and sizes on production report audited and certified on the 8px grid.
- [x] Modern Card visual specification documented in `docs/VISUAL_STANDARDS_SPEC.md`.
- [x] Contrast ratios validated to exceed WCAG 2.1 AA requirement (minimum 4.5:1 for normal text).
