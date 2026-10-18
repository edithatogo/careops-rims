# Open Access Mandate Compliance & Clinical Trial Linkage Specification

## 1. Open Access Policy Framework (NHMRC / MRFF)

Under the NHMRC Open Access Policy, peer-reviewed publications arising from NHMRC-supported research must be made immediately open access with a Creative Commons Attribution (CC BY) license.

### Open Access Categories
| Category | Definition | Compliance State |
| :--- | :--- | :--- |
| **Gold** | Published immediately open in open access journal (DOAJ indexed) | **Fully Compliant** |
| **Hybrid** | Published open access in subscription journal with APC paid | **Fully Compliant** |
| **Green** | Author Accepted Manuscript (AAM) archived in repository | **Fully Compliant** |
| **Bronze** | Free to view on publisher site, but without formal CC license | **Conditionally Compliant** |
| **Closed** | Behind subscription paywall, no repository version | **Non-Compliant** |

### DAX Compliance Measures
```dax
Open Access Publications = 
CALCULATE(
    [Publications],
    Publication[OACategory] IN {"Gold", "Hybrid", "Green"}
)

% Open Access Compliant = 
DIVIDE([Open Access Publications], [Publications], 0)
```

---

## 2. Clinical Trial Registry Linkages

Clinical research governance requires linking peer-reviewed publications to registered clinical trials to monitor translation and prevent publication bias.

### Registry Matching Rules
1. **ANZCTR (Australian New Zealand Clinical Trials Registry):**
   - Pattern: `ACTRN\d{14}`
   - Resolver: `https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={id}`
2. **ClinicalTrials.gov:**
   - Pattern: `NCT\d{8}`
   - Resolver: `https://clinicaltrials.gov/study/{id}`

### Schema Columns for SharePoint List
- `OACategory`: Choice (`Gold`, `Hybrid`, `Green`, `Bronze`, `Closed`)
- `OALicense`: Single line of text (e.g. `CC-BY 4.0`)
- `OAUrl`: Hyperlink (Direct link to open version / PDF)
- `TrialRegistryID`: Single line of text (e.g. `ACTRN12621000123456`)
- `TrialRegistryURL`: Hyperlink (Link to registry trial record)
