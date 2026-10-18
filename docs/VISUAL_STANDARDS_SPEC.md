# Microsoft Fluent 2 & IBCS Visual Design Standards Specification

## 1. Geometric Grid Foundation (8-Point Base Grid)

Every visual on the Power BI canvas adheres strictly to an 8-point base grid to ensure clean alignment, visual stability, and effortless scanning for executive leadership.

### Rules
- **Canvas Resolution:** 1920 × 1080 (FHD, 16:9).
- **Outer Canvas Margins:** Exactly 32px (top, bottom, left, right).
- **Internal Gutters:** Exactly 16px horizontal and vertical gutters between adjacent visual containers.
- **Coordinate Rule:** `x % 8 == 0`, `y % 8 == 0`, `width % 8 == 0`, `height % 8 == 0`.

### Standard Layout Coordinates (FHD 1920 × 1080)
- **Top Header Bar:** `x = 32`, `y = 32`, `w = 1856`, `h = 80`.
- **Top KPI Cards (Row 1):**
  - Card 1 (Total Publications): `x = 32`, `y = 128`, `w = 448`, `h = 128`.
  - Card 2 (PubMed Harvest): `x = 496`, `y = 128`, `w = 448`, `h = 128`.
  - Card 3 (DORA Harvest): `x = 960`, `y = 128`, `w = 448`, `h = 128`.
  - Card 4 (Multi-Source Reconciled): `x = 1424`, `y = 128`, `w = 464`, `h = 128`.
- **Primary Visual Area (Row 2):**
  - Left Chart / Filters: `x = 32`, `y = 272`, `w = 448`, `h = 704`.
  - Main Reconciled Table / Matrix: `x = 496`, `y = 272`, `w = 1392`, `h = 704`.
- **Footer Bar:** `x = 32`, `y = 992`, `w = 1856`, `h = 56`.

---

## 2. Visual Archetypes & IBCS Conventions

### A. Modern New Card Visual (`actionCard`)
- **Primary Metric:** 32pt Segoe UI Bold, Dark Charcoal (`#201F1E`).
- **Reference Label 1 (Prior Period):** 11pt Segoe UI Regular, muted grey (`#605E5C`), e.g. *"vs prior year (+14%)"*.
- **Reference Label 2 (Leadership):** 11pt Segoe UI Regular, teal accent (`#00828A`), e.g. *"68% Cairns-Led"*.
- **Accent Bar:** 4px vertical bar on the left edge of each card using theme primary accent.

### B. Specialty Horizontal Bar Chart
- **Orientation:** Horizontal (bars flow left to right).
- **Rationale:** Medical specialties (e.g. *"Infectious Diseases & Tropical Health"*) have long titles. Horizontal bars prevent vertical text rotation, truncation, or ellipsis.
- **Sorting:** Strict descending order by publication volume.
- **Labels:** Metric values placed on the inside end of each bar; category labels left-aligned.

### C. Contextual Report Tooltip Canvas
- **Dimensions:** 320 × 200.
- **Content:**
  - Title (11pt Bold, max 3 lines).
  - Authors (9pt Regular, truncated to first 3 + *et al.*).
  - Journal & Year (9pt Italic).
  - Open Access Badge (Gold / Green / Closed).
  - Citations count badge.

---

## 3. Accessible Color Palette (Fluent 2)

| Token Name | Hex Code | Usage | Contrast Ratio |
| :--- | :--- | :--- | :--- |
| **Neutral Primary** | `#201F1E` | Primary titles, headlines, table text | 15.8:1 (AAA) |
| **Neutral Secondary** | `#605E5C` | Subtitles, reference labels, axis text | 4.6:1 (AA) |
| **Neutral Light** | `#F3F2F1` | Alternating table row fills, card containers | Background |
| **Theme Primary (Teal)**| `#00828A` | Queensland Health accent, primary data bars | 4.8:1 (AA) |
| **Success (Green)** | `#107C41` | Open access compliant, positive YoY delta | 4.5:1 (AA) |
| **Warning (Amber)** | `#D83B01` | Needs review status, conditional access | 4.6:1 (AA) |
