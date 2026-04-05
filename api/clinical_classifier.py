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
    ph = get_num("pH")
    
    # 1. UTI Sub-classification
    # UTI identification uses three primary biomarkers: Nitrite, Leukocytes, and pH.
    if leukocytes > 10.0 or nitrite == "POSITIVE" or ph > 7.5:
        if nitrite == "POSITIVE":
            diagnoses.append("Gram-Negative Bacterial UTI (e.g. E. coli or Klebsiella) - Indicated by Positive Leukocyte Esterase and bacterial nitrate reductase activity (Positive Nitrite). Pad color typically shifts to PINK.")
        
        elif ph > 7.5:
            diagnoses.append("Urease-Positive Bacterial UTI (e.g. Proteus or Klebsiella) - Indicated by highly alkaline urine (pH > 7.5) caused by the urease enzyme converting urea to ammonia. Often associated with struvite stone risk.")
            
        else:
            if blood > 15.0:
                diagnoses.append("Viral Hemorrhagic Cystitis or Gram-Positive Bacterial UTI - Indicated by inflammation (Positive Leukocytes) and Hematuria (Blood in urine) without bacterial nitrate reductase.")
            else:
                diagnoses.append("Gram-Positive Bacterial UTI (e.g. Staphylococcus or Enterococcus) - Indicated by pyuria (Positive Leukocytes shifting pad from BEIGE to BROWN/PURPLE) without nitrate reductase.")


    # 2. Liver & Biliary Screening
    # Bilirubin: Any positive result (>0) is abnormal.
    # Urobilinogen: >1.0 mg/dL is usually the upper limit of normal; >2.0 is clinically significant.
    if bilirubin > 0:
        diagnoses.append("Bilirubinuria detected - Possible Cholestasis or Hepatocellular injury.")

    if urobilinogen > 2.0:
        diagnoses.append("Elevated Urobilinogen - Suggestive of Hepatic Pathology or Hemolysis.")
    elif urobilinogen == 0 and bilirubin > 0:
        diagnoses.append("Bilirubinuria with Absent Urobilinogen - Possible Biliary Obstruction.")

    # 4. Kidney Disease
    # Normal protein is 'NEGATIVE'. Small/Trace is 0.3 g/L. >0.3 is proteinuria.
    if protein > 0.3:
        diagnoses.append("Glomerular / Renal Disease (e.g. Diabetic Nephropathy) - Suggested by clinically significant proteinuria (albuminuria).")
        
    # 5. Dehydration
    if sg > 1.025:
        diagnoses.append("Dehydration - Suggested by highly concentrated urine specific gravity.")

    if not diagnoses:
        diagnoses.append("Normal - No significant pathogenic biomarker combinations detected.")
        
    return diagnoses
