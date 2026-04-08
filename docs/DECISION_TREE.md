# Clinical Decision Tree (Quantified)

This document provides a detailed breakdown of the mathematical thresholds and logic paths used by the `api/clinical_classifier.py` engine to generate diagnostic warnings.

---

## 📊 Biomarker Thresholds

The following table lists the specific markers and numerical values used to trigger diagnostic alerts.

| Marker | Unit | Threshold | Rationale |
| :--- | :--- | :--- | :--- |
| **Leukocytes** | cells/uL | `> 10.0` | Indicates inflammation/pyuria. |
| **Nitrite** | Categorical | `"POSITIVE"` | Indicates bacterial nitrate reductase activity. |
| **pH** | pH units | `> 7.5` | Indicates alkaline urine (often urease-producing bacteria). |
| **Protein** | g/L | `> 0.3` | Indicates clinically significant proteinuria (> Trace). |
| **Specific Gravity** | SG | `> 1.025` | Indicates highly concentrated urine. |
| **Bilirubin** | umol/L | `> 0` | Any detectable bilirubin is abnormal. |
| **Urobilinogen** | umol/L | `> 2.0` | Suggestive of hepatic pathology or hemolysis. |

---

## 🌲 Diagnostic Flowchart

The screening engine evaluates results in a sequential pipeline. Multiple diagnoses can be triggered simultaneously if multiple conditions are met.

```mermaid
graph TD
    Start([Start Analysis]) --> Extract[Extract Values from Strip]
    
    %% 1. UTI
    Extract --> UTI_Check{UTI Marker?<br/>'Leuk > 10' OR 'Nitrite +' OR 'pH > 7.5'}
    UTI_Check -- Yes --> Nitrite_Match{Nitrite POSITIVE?}
    Nitrite_Match -- Yes --> GramNeg[Gram-Negative Bacterial UTI]
    Nitrite_Match -- No --> Ph_Match{pH > 7.5?}
    Ph_Match -- Yes --> Urease[Urease-Positive Bacterial UTI]
    Ph_Match -- No --> GramPos[Gram-Positive Bacterial UTI]
    
    %% 2. Liver
    UTI_Check -- No --> Liver_Section
    GramNeg --> Liver_Section
    Urease --> Liver_Section
    GramPos --> Liver_Section

    subgraph Liver_Biliary [Liver & Biliary Screen]
    Liver_Section[Evaluate Liver Markers] --> Bil_Pos{Bilirubin > 0?}
    Bil_Pos -- Yes --> Bil_Diag[Bilirubinuria detected]
    Bil_Pos -- No --> Uro_High{Urobilinogen > 2.0?}
    Uro_High -- Yes --> Uro_Diag[Elevated Urobilinogen]
    Uro_High -- No --> Biliary_Obs{Uro == 0 AND Bil > 0?}
    Biliary_Obs -- Yes --> Obs_Diag[Possible Biliary Obstruction]
    Biliary_Obs -- No --> Kidney_Section
    Bil_Diag --> Kidney_Section
    Uro_Diag --> Kidney_Section
    Obs_Diag --> Kidney_Section
    end

    %% 3. Kidney & Systemic
    subgraph Kidney_Systemic [Kidney & Systemic]
    Kidney_Section[Evaluate Kidney/SG] --> Pro_Pos{Protein > 0.3?}
    Pro_Pos -- Yes --> Pro_Diag[Glomerular / Renal Disease]
    Pro_Pos -- No --> SG_High{SG > 1.025?}
    SG_High -- Yes --> SG_Diag[Dehydration]
    SG_High -- No --> Normal_Check{Any Diagnosis Added?}
    Pro_Diag --> SG_High
    SG_Diag --> Normal_Check
    end

    %% Final
    Normal_Check -- No --> Normal_Diag[NORMAL STATUS]
    Normal_Check -- Yes --> Finish([End Analysis])
    Normal_Diag --> Finish
```

---

## ⚖️ Path Descriptions

### 1. Urinary Tract Infection (UTI) Pipeline
- **Gram-Negative Bacterial UTI**: Triggered by Nitrite detection.
- **Urease-Positive Bacterial UTI**: Triggered by alkaline pH (> 7.5), suggesting organisms like *Proteus*.
- **Gram-Positive Bacterial UTI**: Triggered by pyuria (Leukocytes > 10) without Nitrite or pH elevation.

### 2. Liver & Biliary Screen
- **Bilirubinuria**: Any positive Bilirubin result.
- **Elevated Urobilinogen**: Values > 2.0 umol/L.
- **Biliary Obstruction Pattern**: The combination of Bilirubinuria with absent Urobilinogen.

### 3. Renal & Systemic Status
- **Renal Disease**: Proteinuria (> 0.3 g/L) suggests glomerular damage.
- **Dehydration**: High Specific Gravity (> 1.025) suggests concentrated urine.

---

> [!TIP]
> **Unit Consistency:** The numerical thresholds match the `models/model.json` units exactly. If you update the swatches in the model, verify that these logical cutoffs remain clinically valid for your training set.
