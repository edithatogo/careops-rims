# Specification: E03 Open Access Mandate Compliance and Clinical Trial Linkage

## 1. Overview & Policy Context
Australian public health services receiving NHMRC and Medical Research Future Fund (MRFF) funding operate under strict Open Access mandates requiring immediate open availability of peer-reviewed research outputs. Furthermore, hospital clinical research governance prioritizes linking clinical trial registrations to resulting publications.

## 2. Functional Requirements
1. **Open Access Category Tracking:**
   - Classification per work:
     - `Gold`: Published directly in an open access journal under CC-BY license.
     - `Hybrid`: Published in a subscription journal with open access fee paid.
     - `Green`: Author accepted manuscript self-archived in a repository (e.g. DORA / institutional repository).
     - `Bronze`: Free to read on publisher website without formal open license.
     - `Closed`: Behind paywall without repository copy.
2. **NHMRC / MRFF Mandate Compliance Flag:**
   ```
   IF OACategory IN ("Gold", "Hybrid", "Green") THEN "Compliant"
   ELSE IF OACategory == "Bronze" THEN "Conditionally Accessible"
   ELSE "Non-Compliant / Paywalled"
   ```
3. **Clinical Trial Registry Cross-Referencing:**
   - Detect secondary identifiers:
     - ANZCTR: Australian New Zealand Clinical Trials Registry format: `ACTRN\d{14}`.
     - ClinicalTrials.gov format: `NCT\d{8}`.
   - Field `TrialRegistrationID`: Populated with trial identifier and link to registry.
4. **Zero-Key Ingestion Protocol:**
   - Ingestion via Europe PMC free public API (`https://www.ebi.ac.uk/europepmc/webservices/rest/search`) and Crossref polite-pool. Zero token or API key requirements.

## 3. Acceptance Criteria
- [x] Specification established in `docs/OPEN_ACCESS_TRIALS_SPEC.md`.
- [x] Open Access compliance categorization matches NHMRC Open Access Policy 2022.
- [x] Trial identifier extraction regex validated against ANZCTR and ClinicalTrials.gov standards.
