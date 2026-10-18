# Clinical Analytics & Advanced Attribution Specification

## 1. Cairns Authorship Leadership Indicator

Queensland Health research governance prioritizes recognizing locally initiated and led research versus participation in external multi-center clinical trials.

### Attribution Rules
```
IF Affiliation(FirstAuthor) IN CHHHS_FACILITIES THEN "Cairns-Led"
ELSE IF Affiliation(LastAuthor) IN CHHHS_FACILITIES AND Count(Authors) > 1 THEN "Cairns-Led"
ELSE IF ANY(Author) IN CHHHS_FACILITIES THEN "Collaborative"
ELSE "Unattributed"
```

### DAX Measures
```dax
Cairns Led Publications = 
CALCULATE(
    [Publications],
    Publication[LeadershipRole] = "Cairns-Led"
)

Collaborative Publications = 
CALCULATE(
    [Publications],
    Publication[LeadershipRole] = "Collaborative"
)

% Cairns Led = 
DIVIDE([Cairns Led Publications], [Publications], 0)
```

---

## 2. ANZSRC 2020 Fields of Research (FoR) Division Mapping

Australian national research reporting requires alignment with the Australian and New Zealand Standard Research Classification (ANZSRC) 2020:

| Division Code | Division Title | Common Hospital Specialties |
| :--- | :--- | :--- |
| **32** | Biomedical and Clinical Sciences | Cardiology, Oncology, Renal, Surgery, Pathology |
| **42** | Health Sciences | Allied Health, Nursing, Health Services, Physiotherapy |
| **31** | Biological Sciences | Genetics, Microbiology, Biochemistry |
| **41** | Environmental Sciences | Tropical Ecology, Vector Biology, Environmental Health |
| **44** | Human Society | Public Health Policy, Health Economics, Medical Anthropology |
| **52** | Psychology | Clinical Psychology, Neuropsychology, Mental Health |

---

## 3. Clinical Service Line Taxonomy

To support Clinical Directors and Operations Directors, publications map to eight standard hospital directorates:
1. **Emergency & Critical Care:** Emergency Medicine, Intensive Care Unit (ICU), Retrieval Medicine.
2. **Medical Specialties:** Renal Medicine, Cardiology, Neurology, Gastroenterology, Endocrinology, Dermatology.
3. **Infectious Diseases & Tropical Health:** Tropical Medicine, Infection Control, Sexual Health, Microbiology.
4. **Surgical Specialties:** General Surgery, Orthopaedics, ENT, Ophthalmology, Urology, Vascular Surgery.
5. **Cancer Care:** Medical Oncology, Radiation Oncology, Haematology, Palliative Care.
6. **Women's and Child Health:** Paediatrics, Obstetrics & Gynaecology, Neonatal ICU (SCBU).
7. **Mental Health & Addictions:** Adult Acute Mental Health, Child & Youth Mental Health, ATODS.
8. **Allied Health & Nursing:** Physiotherapy, Pharmacy, Social Work, Nutrition & Dietetics, Occupational Therapy.
