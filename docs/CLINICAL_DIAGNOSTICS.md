# Clinical Diagnostics & Literature Rationale

The `api/clinical_classifier.py` engine translates raw chemical concentration data into actionable medical screening warnings. This document explains the heuristic rules used and provides the primary literature citations justifying our approach.

---

## ⚕️ Rules-Based Heuristics
Because urinalysis is primarily a screening tool, the classifier evaluates **hard-coded biomarker logic** rather than "black box" machine learning models. This provides transparency and high clinical interpretability.

### 1. Urinary Tract Infection (UTI) Subclassification
Our detection pipeline evaluates three primary biomarkers to identify a UTI: **Nitrite presence**, **Leukocyte presence**, and **increased pH**. 

- **Leukocyte Response:** While healthy urine contains minimal leukocytes, an infection triggers a dramatic inflammatory response (pyuria), shifting the reagent pad from **beige to brown or purple**.
- **Nitrate Reductase (Gram-Negative):** Bacteria like *E. coli* possess the **nitrate reductase** enzyme, which converts nitrates to nitrites. This chemical reaction turns the corresponding pad **pink**. 
  - **Match**: `Positive Leukocytes` + `Positive Nitrites`.
  - **Source**: [[PMC4408713]](https://pmc.ncbi.nlm.nih.gov/articles/PMC4408713/)
- **Urease Enzyme (Alkaline pH):** Pathogens such as *Proteus* or *Klebsiella* carry the **urease enzyme**, which splits urea into ammonia. This mechanism makes the urine significantly more alkaline (**pH > 7.5**).
  - **Match**: `Positive Leukocytes` + `pH > 7.5`.
  - **Source**: [[PMC6351000]](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6351000/)
- **Gram-Positive Bacteria:** Certain pathogens like *Staph. saprophyticus* do **not** possess nitrate reductase.
  - **Match**: `Positive Leukocytes` + `Negative Nitrites` + `Neutral pH`.
  - **Source**: [[PMC85454]](https://pmc.ncbi.nlm.nih.gov/articles/PMC85454/)

### 2. Metabolic Disorders (Diabetes & DKA)
Glucose is typically reabsorbed by the kidneys. Glucosuria occurs when blood sugar exceeds the renal threshold (>180 mg/dL).
- **Poorly Controlled Diabetes**: `High Glucose` + `Negative Ketones`.
- **Diabetic Ketoacidosis (DKA)**: `High Glucose` + `Positive Ketones`. DKA is a severe metabolic emergency requiring immediate intervention.
- **Source**: [[NBK247]](https://www.ncbi.nlm.nih.gov/books/NBK247/)

### 3. Hepatic and Biliary Disease
Bilirubin in the urine (specifically conjugated bilirubin) indicates impaired liver function or biliary obstruction.
- **Pathology**: `Positive Bilirubin` OR `Extremely High Urobilinogen`.
- **Source**: [[PMC10259638]](https://pmc.ncbi.nlm.nih.gov/articles/PMC10259638/)

### 4. Renal Disease / Glomerulonephritis
Persistent proteinuria (specifically albuminuria) is an early indicator of kidney disease.
- **Constraint**: The classifier triggers only for measurements `>` Trace, as transient trace amounts can the benign (caused by dehydration or exercise).
- **Source**: [[PMC12703532]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12703532/)

---

## 📚 Literature Verification Mapping

For strict verification of the implemented code logic, find the specific claims in the following sections of the literature:

| Category | Source | Key Section |
|----------|---------|-------------|
| **UTI Sensitivity** | [PMC4408713](https://pmc.ncbi.nlm.nih.gov/articles/PMC4408713/) | Table 2 (Combined Nitrite/Leukocyte response) |
| **Bacterial Strain** | [PMC85454](https://pmc.ncbi.nlm.nih.gov/articles/PMC85454/) | "Results" (paragraph 4) regarding nitrate reductase |
| **Urease Activity** | [PMC6351000](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6351000/) | Section "Urease and UTI" regarding pH elevation |
| **Bilirubin Excretion** | [PMC10259638](https://pmc.ncbi.nlm.nih.gov/articles/PMC10259638/) | "Introduction" explaining water-soluble conjugation |
| **Kidney Filtration** | [NBK564390](https://www.ncbi.nlm.nih.gov/books/NBK564390/) | "Pathophysiology" of the glomerular capillary wall |
| **Transient Protein** | [PMC12703532](https://pmc.ncbi.nlm.nih.gov/articles/PMC12703532/) | "Transient Proteinuria" subsection |

---

## 🔗 Related Documentation
- [Decision Tree (Quantified)](DECISION_TREE.md) — Exact numerical thresholds and logic paths.
- [Algorithm Design](ALGORITHM.md) — How the raw pixels are converted to colors.
- [API Reference](API_REFERENCE.md) — How to call the `evaluate_diagnoses()` function.

---

> [!WARNING]
> **Medical Disclaimer:** These heuristic models exist exclusively for project demonstration purposes. Urinalysis is a screening tool, and results require clinical review and laboratory confirmation (e.g., formal urine cultures). This software is not intended for actual medical diagnosis.
