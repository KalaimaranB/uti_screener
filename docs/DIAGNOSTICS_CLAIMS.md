# Urinalysis Clinical Diagnostic Engine

**File:** `program3_diagnose.py`

## Overview
This diagnostic engine employs multi-variate rule-based heuristics derived from peer-reviewed medical literature to analyze urinalysis data. Because urinalysis primarily offers screening thresholds rather than continuously scaled structural patterns, evaluating hard-coded biomarker logic provides higher interpretability, transparency, and scientific rigor than sparse machine learning models like Principal Component Analysis (PCA).

Below are the clinical rationales used to build the classifier endpoints, complete with primary literature citations and specific claim mappings.

---

## Clinical Rationale & Diagnostic Heuristics

### 1. Urinary Tract Infection (UTI) Subclassification
Urinary Tract Infections elicit an immune inflammatory response, typically raising **Leukocyte Esterase** levels in the urine (indicating pyuria, or white blood cells) [[PMC4408713]](https://pmc.ncbi.nlm.nih.gov/articles/PMC4408713/). The distinction between bacterial strains primarily relies on the **Nitrite** test.

* **Gram-Negative Bacteria:** Pathogens such as *Escherichia coli* and *Klebsiella* possess the enzyme **nitrate reductase**, which converts dietary urine nitrates into nitrites [[PMC85454]](https://pmc.ncbi.nlm.nih.gov/articles/PMC85454/). A combination of Positive Leukocyte Esterase + Positive Nitrite is highly specific for a Gram-Negative bacterial UTI [[PMC4408713]](https://pmc.ncbi.nlm.nih.gov/articles/PMC4408713/).
* **Gram-Positive Bacteria:** Pathogens such as *Staphylococcus saprophyticus* and *Enterococcus* **do not** possess nitrate reductase [[PMC85454]](https://pmc.ncbi.nlm.nih.gov/articles/PMC85454/). Consequently, they present with Positive Leukocytes but a **Negative Nitrite** test.
* **Viral Infection:** While relatively rare, viral UTIs (such as Adenovirus, particularly in pediatric or immunocompromised patients) cause significant inflammation (High Leukocytes, Negative Nitrite) and frequently present with hematuria (Positive Blood) due to acute hemorrhagic cystitis [[PMC4408713]](https://pmc.ncbi.nlm.nih.gov/articles/PMC4408713/).
* https://pmc.ncbi.nlm.nih.gov/articles/PMC8357242/#:~:text=Recent%20diagnostic%20improvements%20led%20to,et%20al.%2C%202005). 

### 2. Hepatic and Biliary Disease
**Bilirubin** is a breakdown product of red blood cells. Crucially, only *conjugated* (water-soluble) bilirubin can be excreted by the kidneys [[PMC10259638]](https://pmc.ncbi.nlm.nih.gov/articles/PMC10259638/). Its presence in urine indicates impaired liver function, hepatic injury, or biliary obstruction (cholestasis) [[PMC7315332]](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315332/). **Urobilinogen** is normally present in small, trace amounts after being formed in the gut and reabsorbed; however, elevated levels similarly suggest liver disease (such as hepatitis) or hemolytic anemia [[PMC7315332]](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315332/).

* **Hepatic/Biliary Pathology:** Positive Bilirubin OR significantly elevated Urobilinogen [[PMC7315332]](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315332/).

### 3. Renal Disease / Glomerulonephritis
The kidneys' glomeruli typically prevent large macro-molecules like **Protein** (specifically albumin) from entering the urine [[NBK564390]](https://www.ncbi.nlm.nih.gov/books/NBK564390/). Persistent proteinuria is a primary early indicator of kidney disease, such as Diabetic Nephropathy or Glomerulonephritis [[NBK564390]](https://www.ncbi.nlm.nih.gov/books/NBK564390/). Because transient trace amounts can be benign—often caused by dehydration, fever, or strenuous exercise—the diagnostic classifier triggers clinically significant warnings only on `>` Trace amounts [[PMC12703532]](https://pmc.ncbi.nlm.nih.gov/articles/PMC12703532/).

---

## Literature Verification Mapping

For strict verification of the implemented logic, the specific claims and thresholds can be found in the cited literature at the following locations:

**1. Urinary Tract Infection (UTI)**
* **PMC4408713:** Refer to the "Results" section (Table 2 discussion) for the highest sensitivity occurring when nitrite, leukocyte, and blood are combined. See the "Discussion" section for the mechanism of leukocyte esterase.
* **PMC85454:** Refer to the "Results" section (paragraph 4) and "Materials and Methods" for the distinction between gram-negative (nitrate reductase positive) and gram-positive bacteria regarding the nitrite test.

**2. Hepatic and Biliary Disease**
* **PMC10259638:** Refer to the "Introduction" and "Case Presentation" for the physiological distinction between unconjugated and conjugated (water-soluble/renally excreted) bilirubin.
* **PMC7315332:** Refer to the "Biliary Tract Disease" subsections detailing cholestasis and renal excretion.

**3. Renal Disease / Glomerulonephritis**
* **PMC12703532:** Refer to the "Transient Proteinuria" subsection regarding benign trace amounts caused by fever, heavy exercise, etc., necessitating thresholds above trace.
* **NBK564390:** Refer to the "Pathophysiology" section detailing the glomerular capillary wall's restriction of albumin.

---

**Disclaimer:** *These heuristic models exist exclusively for project demonstration purposes. Urinalysis is a screening tool, and diagnostic results require clinical review and further laboratory confirmation (e.g., formal urine cultures, serum metabolic panels). This software is not intended for actual medical diagnosis.*
