"""
program3_diagnose.py

============================================================
Program 3 — Clinical Diagnostics Engine
============================================================
Reads a urinalysis strip image, extracts biomarker concentrations using the
Polyline Projection model (Program 2), and evaluates multivariate clinical 
diagnosis heuristics based on peer-reviewed medical guidelines.
"""
import argparse
import json
from pathlib import Path

from core.calibration import CalibrationModel
from core.strip_analyzer import StripAnalyzer
from api.clinical_classifier import evaluate_diagnoses

def main():
    parser = argparse.ArgumentParser(description="Program 3 - Clinical Urinalysis Diagnostics")
    parser.add_argument("--image", required=True, help="Path to input strip image")
    parser.add_argument("--model", default="models/model.json", help="Path to JSON calibration model")
    parser.add_argument("--config", default="config/strip_config.json", help="Path to strip config")
    parser.add_argument("--debug", action="store_true", help="Save annotated debug image")
    parser.add_argument("--output", help="Optional JSON output path for diagnosis results")
    args = parser.parse_args()

    print(f"\n[Program 3] Clinical Diagnostics Engine")
    print(f"            Strip: {args.image}\n")

    model = CalibrationModel.load(args.model)
    analyzer = StripAnalyzer()
    
    # 1. Image extraction using previous API logic
    if args.debug:
        debug_path = Path(args.image).with_name(Path(args.image).stem + "_diagnosed.png")
        results = analyzer.analyze_with_debug(
            args.image, model, args.config, debug_output_path=str(debug_path)
        )
    else:
        results = analyzer.analyze(args.image, model, args.config)

    # 2. Clinical Classification
    diagnoses = evaluate_diagnoses(results)
    
    # 3. Output
    print("\n============================================================")
    print("  CLINICAL DIAGNOSTIC EVALUATION")
    print("============================================================")
    for d in diagnoses:
        print(f" • {d}")
    print("============================================================\n")

    if args.output:
        out_data = {
            "biomarkers": {
                k: {"value": v.value, "unit": v.unit, "confidence": v.confidence} 
                for k, v in results.items()
            },
            "diagnoses": diagnoses
        }
        with open(args.output, "w") as f:
            json.dump(out_data, f, indent=2)
        print(f"[INFO] Saved diagnosis output to {args.output}")

if __name__ == "__main__":
    main()
