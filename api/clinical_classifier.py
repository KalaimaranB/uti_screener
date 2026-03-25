"""
api/clinical_classifier.py — Multivariate heuristic diagnostic engine for urinalysis results.
"""
from typing import Any

def evaluate_diagnoses(results: dict[str, Any]) -> list[str]:
    """
    Given a dictionary of BoxResult instances, return a list of clinical diagnosis strings.
    """
    diagnoses = []
    
    # Helper to safely extract value
    def get_val(analyte: str) -> Any:
        if analyte not in results: return None
        return results[analyte].value
        
    def get_num(analyte: str) -> float:
        v = get_val(analyte)
        if v == "NEGATIVE" or v is None or isinstance(v, str):
            return 0.0
        return float(v)
        
    leukocytes = get_num("leukocytes")
    nitrite = get_val("nitrite")
    blood = get_num("blood")
    glucose = get_num("glucose")
    ketone = get_num("ketone")
    protein = get_num("protein")
    bilirubin = get_num("bilirubin")
    urobilinogen = get_num("urobilinogen")
    sg = get_num("sp_gravity")
    
    # 1. UTI Sub-classification
    # Trace leukocytes is usually ~15 cells/uL. 
    if leukocytes > 10.0 or nitrite == "POSITIVE":
        if nitrite == "POSITIVE":
            diagnoses.append("Gram-Negative Bacterial UTI (e.g. E. coli or Klebsiella) - Indicated by Positive Leukocyte Esterase combined with nitrate reductase activity (Positive Nitrite).")
        else:
            if blood > 15.0:
                diagnoses.append("Viral Hemorrhagic Cystitis or Gram-Positive Bacterial UTI - Indicated by inflammation (Positive Leukocytes) and Hematuria (Blood in urine) without bacterial nitrate reductase.")
            else:
                diagnoses.append("Gram-Positive Bacterial UTI (e.g. Staphylococcus or Enterococcus) - Indicated by pyuria (Positive Leukocytes) without nitrate reductase.")

    # 2. Diabetes / DKA
    if glucose > 0:
        if ketone > 0.5:
            diagnoses.append("Diabetic Ketoacidosis (DKA) - Severe metabolic state indicated by concomitant glucosuria and ketonuria.")
        else:
            diagnoses.append("Poorly Controlled Diabetes - Indicated by glucosuria exceeding the renal reabsorption threshold.")

    # 3. Liver Disease
    if bilirubin > 0 or urobilinogen > 3.2:
        diagnoses.append("Hepatic/Biliary Pathology - Evidenced by elevated bilirubin or excessive urobilinogen excretion.")

    # 4. Kidney Disease
    # Normal protein is 'NEGATIVE'. Small/Trace is 0.3 g/L. >0.3 is proteinuria.
    if protein > 0.5:
        diagnoses.append("Glomerular / Renal Disease (e.g. Diabetic Nephropathy) - Suggested by clinically significant proteinuria (albuminuria).")
        
    # 5. Dehydration
    if sg > 1.025:
        diagnoses.append("Dehydration - Suggested by highly concentrated urine specific gravity.")

    if not diagnoses:
        diagnoses.append("Normal - No significant pathogenic biomarker combinations detected.")
        
    return diagnoses
