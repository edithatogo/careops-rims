# Specification: E02 Clinical Directorate Attribution and ANZSRC FoR Classification

## 1. Overview & Strategic Value
Clinical leadership (Clinical Directors and Chief Executives) requires publication data broken down by clinical service lines and research domains, rather than simple global aggregates. Additionally, distinguishing between **Cairns-led publications** (where local clinicians drive the research as first or senior author) and **multi-center collaboration** (where local clinicians provide co-authorship or recruit patients) provides essential evidence of local research maturity.

## 2. Functional Requirements
1. **ANZSRC 2020 Fields of Research (FoR) Classification:**
   - Division (2-digit): e.g., `32 Biomedical and Clinical Sciences`, `42 Health Sciences`, `31 Biological Sciences`, `41 Environmental Sciences`.
   - Group (4-digit): e.g., `3202 Clinical Sciences`, `3204 Immunology`, `4203 Health Services and Systems`.
   - Integration: Derived via keyless OpenAlex / Crossref polite-pool topic mapping or MeSH heading ontology.
2. **Author Leadership Attribution:**
   - Classification logic:
     - `Cairns-Led`: First author or last (senior) author affiliated with Cairns Hospital / CHHHS.
     - `Collaborative`: Middle author affiliated with Cairns Hospital / CHHHS.
3. **Clinical Specialty Categorization:**
   - Specialized hospital service line mapping:
     - Emergency Medicine & Intensive Care
     - Renal Medicine & Transplantation
     - Infectious Diseases & Tropical Health
     - Cardiology & Cardiothoracic Surgery
     - Medical & Radiation Oncology
     - Paediatrics & Child Health
     - General Surgery & Orthopaedics
     - Allied Health & Nursing
4. **DAX Measures Specification:**
   ```dax
   [Cairns Led Publications] = CALCULATE([Publications], Publication[LeadershipRole] = "Cairns-Led")
   [Collaborative Publications] = CALCULATE([Publications], Publication[LeadershipRole] = "Collaborative")
   [% Cairns Led] = DIVIDE([Cairns Led Publications], [Publications], 0)
   ```

## 3. Acceptance Criteria
- [x] Specification documented with deterministic rules for leadership role attribution.
- [x] ANZSRC 2020 FoR taxonomy mapped to publication metadata fields.
- [x] Specialty taxonomy aligned with CHHHS clinical directorate reporting requirements.
