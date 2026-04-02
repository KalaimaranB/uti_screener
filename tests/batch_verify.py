#!/usr/bin/env python3
"""
Batch verification script for testing the UTI strip analyzer against
known ground-truth samples using the FULL pipeline (YOLO + segmenter).

Runs images through the same YOLO→crop→resize→segment→analyze pipeline
as the real UI, then compares results to expected ground truth.
"""
import sys
import os
import traceback
import tempfile
import cv2

# Force unbuffered stdout
sys.stdout.reconfigure(line_buffering=True)

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=" * 72, flush=True)
print("  UTI Strip Analyzer — Batch Verification (YOLO Pipeline)", flush=True)
print("=" * 72, flush=True)

print("\n[1/5] Loading YOLO model...", flush=True)
from ultralytics import YOLO
yolo_model = YOLO("runs/detect/train2/weights/best.pt")
print("  ✅ YOLO model loaded.", flush=True)

print("[2/5] Loading calibration modules...", flush=True)
from core.calibration import CalibrationModel
from core.strip_analyzer import StripAnalyzer
print("  ✅ Core modules loaded.", flush=True)

SAMPLES_DIR = Path("tests/samples/true_samples/top_level")
MODEL_PATH = "models/model.json"
CONFIG_PATH = "config/strip_config.json"
NEGATIVE_REF = str(SAMPLES_DIR / "Pure_negative.jpg")

# Ground truth
# NOTE: For analytes without a NEGATIVE swatch (pH, urobilinogen, sp_gravity),
# "baseline" means the lowest reference value: pH=5.0, urobilinogen=3.2, sp_gravity=1.000
BASELINE_VALUES = {"pH": 5.0, "urobilinogen": 3.2, "sp_gravity": 1.000}

GROUND_TRUTH = {
    "Pure_negative.jpg": {
        "leukocytes": "NEGATIVE", "nitrite": "NEGATIVE", "urobilinogen": "baseline",
        "protein": "NEGATIVE", "pH": "baseline", "blood": "NEGATIVE",
        "sp_gravity": "baseline", "ketone": "NEGATIVE", "bilirubin": "NEGATIVE",
        "glucose": "NEGATIVE",
    },
    "Glu30Ph7.jpg": {
        "leukocytes": "NEGATIVE", "nitrite": "NEGATIVE", "urobilinogen": "baseline",
        "protein": "NEGATIVE", "pH": 7.0, "blood": "NEGATIVE",
        "sp_gravity": "baseline", "ketone": "NEGATIVE", "bilirubin": "NEGATIVE",
        "glucose": 30.0,
    },
    "Spg_1.020Bili50.jpg": {
        "leukocytes": "NEGATIVE", "nitrite": "NEGATIVE", "urobilinogen": "baseline",
        "protein": "NEGATIVE", "pH": "baseline", "blood": "NEGATIVE",
        "sp_gravity": 1.020, "ketone": "NEGATIVE", "bilirubin": 50.0,
        "glucose": "NEGATIVE",
    },
    "Uro32Ket4.jpg": {
        "leukocytes": "NEGATIVE", "nitrite": "NEGATIVE", "urobilinogen": 32.0,
        "protein": "NEGATIVE", "pH": "baseline", "blood": "NEGATIVE",
        "sp_gravity": "baseline", "ketone": 4.0, "bilirubin": "NEGATIVE",
        "glucose": "NEGATIVE",
    },
    "Leu75Nit1.jpg": {
        "leukocytes": 75.0, "nitrite": "POSITIVE", "urobilinogen": "baseline",
        "protein": "NEGATIVE", "pH": "baseline", "blood": "NEGATIVE",
        "sp_gravity": "baseline", "ketone": "NEGATIVE", "bilirubin": "NEGATIVE",
        "glucose": "NEGATIVE",
    },
    "Pro3.0Blo25.jpg": {
        "leukocytes": "NEGATIVE", "nitrite": "NEGATIVE", "urobilinogen": "baseline",
        "protein": 3.0, "pH": "baseline", "blood": 25.0,
        "sp_gravity": "baseline", "ketone": "NEGATIVE", "bilirubin": "NEGATIVE",
        "glucose": "NEGATIVE",
    },
}


def crop_with_yolo(image_path: str) -> str | None:
    """Use YOLO to detect and crop the strip, resize to 100x800. Returns temp path."""
    image = cv2.imread(image_path)
    if image is None:
        print(f"    ❌ Could not read image: {image_path}", flush=True)
        return None

    results = yolo_model.predict(image, conf=0.7, verbose=False)
    if len(results[0].boxes) == 0:
        print(f"    ❌ YOLO found no strip in image.", flush=True)
        return None

    for box in results[0].boxes:
        class_id = int(box.cls[0])
        class_name = yolo_model.names[class_id]
        if class_name == 'strip':
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cropped = image[y1:y2, x1:x2]
            if (x2 - x1) > (y2 - y1):
                cropped = cv2.rotate(cropped, cv2.ROTATE_90_COUNTERCLOCKWISE)
            standardized = cv2.resize(cropped, (100, 800))
            fd, temp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            cv2.imwrite(temp_path, standardized)
            print(f"    ✅ YOLO crop: ({x2-x1}×{y2-y1}) → 100×800", flush=True)
            return temp_path

    print(f"    ❌ YOLO found boxes but none labeled 'strip'.", flush=True)
    return None


def is_negative_value(value):
    if isinstance(value, str):
        return value.upper() in ("NEGATIVE", "BASELINE")
    if isinstance(value, (int, float)):
        return abs(value) < 1e-6
    return False


def evaluate_result(analyte, expected, actual_value):
    if expected == "baseline":
        # For analytes with no NEGATIVE swatch, accept NEGATIVE or the baseline value
        baseline_val = BASELINE_VALUES.get(analyte)
        if is_negative_value(actual_value):
            return True, f"OK (NEGATIVE/baseline)"
        if baseline_val is not None:
            try:
                actual_num = float(actual_value)
                ratio = actual_num / baseline_val if baseline_val != 0 else 999
                if 0.5 <= ratio <= 2.0:
                    return True, f"OK ({actual_num:.3g} ≈ baseline {baseline_val})"
            except (ValueError, TypeError):
                pass
        return False, f"EXPECTED baseline, GOT {actual_value}"
    elif expected == "NEGATIVE":
        if is_negative_value(actual_value):
            return True, f"OK (NEGATIVE)"
        else:
            return False, f"EXPECTED NEGATIVE, GOT {actual_value}"
    elif expected == "POSITIVE":
        if isinstance(actual_value, str) and "POS" in actual_value.upper():
            return True, f"OK (POSITIVE)"
        else:
            return False, f"EXPECTED POSITIVE, GOT {actual_value}"
    else:
        try:
            actual_num = float(actual_value)
            expected_num = float(expected)
            if expected_num == 0:
                if abs(actual_num) < 1.0:
                    return True, f"OK ({actual_num:.3g})"
                return False, f"EXPECTED ~0, GOT {actual_num:.3g}"
            ratio = actual_num / expected_num
            if 0.3 <= ratio <= 3.0:
                return True, f"OK ({actual_num:.3g} vs exp {expected_num:.3g})"
            else:
                return False, f"MISS ({actual_num:.3g} vs exp {expected_num:.3g})"
        except (ValueError, TypeError):
            return False, f"EXPECTED {expected}, GOT {actual_value}"


def run_single_test(image_name, cropped_paths, neg_cropped_path=None):
    """Run analysis on a pre-cropped strip image."""
    cropped_path = cropped_paths.get(image_name)
    if not cropped_path:
        print(f"    ⏭️  Skipping — no YOLO crop available.", flush=True)
        return 0, 0, []

    debug_dir = Path("tests/debug_output")
    debug_dir.mkdir(exist_ok=True)
    suffix = "_cal" if neg_cropped_path else "_auto"
    debug_path = str(debug_dir / f"{Path(image_name).stem}{suffix}_debug.png")

    model = CalibrationModel.load(MODEL_PATH)
    analyzer = StripAnalyzer()

    print(f"    Analyzing (pre_cropped=True)...", flush=True)
    try:
        results = analyzer.analyze_with_debug(
            image_path=cropped_path,
            model=model,
            strip_config_path=CONFIG_PATH,
            debug_output_path=debug_path,
            pre_cropped=True,
            negative_image_path=neg_cropped_path,
        )
    except Exception as e:
        print(f"    ❌ ANALYSIS FAILED: {e}", flush=True)
        traceback.print_exc()
        return 0, 0, []

    ground_truth = GROUND_TRUTH.get(image_name, {})
    total = 0
    passed = 0
    details = []

    for analyte, expected in ground_truth.items():
        if analyte not in results:
            details.append(f"    {analyte:18s} MISSING")
            total += 1
            continue
        actual = results[analyte].value
        ok, detail = evaluate_result(analyte, expected, actual)
        total += 1
        if ok:
            passed += 1
            details.append(f"    ✅ {analyte:18s} {detail}")
        else:
            details.append(f"    ❌ {analyte:18s} {detail}")

    return passed, total, details


def main():
    # Step 1: Verify sample images exist
    print("\n[3/5] Checking sample images...", flush=True)
    for name in sorted(GROUND_TRUTH.keys()):
        path = SAMPLES_DIR / name
        exists = "✅" if path.exists() else "❌ MISSING"
        print(f"  {name}: {exists}", flush=True)

    # Step 2: YOLO-crop ALL images up front
    print("\n[4/5] YOLO-cropping all images...", flush=True)
    cropped_paths = {}
    for name in sorted(GROUND_TRUTH.keys()):
        print(f"  📷 {name}", flush=True)
        raw_path = str(SAMPLES_DIR / name)
        cropped = crop_with_yolo(raw_path)
        if cropped:
            cropped_paths[name] = cropped
            # Also save a copy for visual inspection
            debug_dir = Path("tests/debug_output")
            debug_dir.mkdir(exist_ok=True)
            cv2.imwrite(str(debug_dir / f"{Path(name).stem}_cropped.jpg"), cv2.imread(cropped))
    
    print(f"\n  Cropped {len(cropped_paths)}/{len(GROUND_TRUTH)} images successfully.", flush=True)

    neg_cropped = cropped_paths.get("Pure_negative.jpg")
    if neg_cropped:
        print(f"  ✅ Negative reference available: {neg_cropped}", flush=True)
    else:
        print(f"  ⚠️  No negative reference — calibration mode unavailable.", flush=True)

    # Step 3: Run tests WITHOUT negative baseline
    print("\n[5a/5] Tests WITHOUT negative baseline...", flush=True)
    print("─" * 72, flush=True)

    grand_pass = 0
    grand_total = 0

    for i, name in enumerate(sorted(GROUND_TRUTH.keys()), 1):
        print(f"\n  [{i}/6] 📷 {name}", flush=True)
        p, t, details = run_single_test(name, cropped_paths, neg_cropped_path=None)
        grand_pass += p
        grand_total += t
        for d in details:
            print(d, flush=True)
        if t > 0:
            print(f"    Score: {p}/{t}", flush=True)

    pct = (grand_pass / grand_total * 100) if grand_total > 0 else 0
    print(f"\n{'═' * 72}", flush=True)
    print(f"  TOTAL [Auto WB]: {grand_pass}/{grand_total} ({pct:.0f}%)", flush=True)
    print(f"{'═' * 72}", flush=True)

    # Step 4: Run tests WITH negative baseline
    if neg_cropped:
        print("\n[5b/5] Tests WITH negative baseline...", flush=True)
        print("─" * 72, flush=True)

        grand_pass2 = 0
        grand_total2 = 0

        for i, name in enumerate(sorted(GROUND_TRUTH.keys()), 1):
            print(f"\n  [{i}/6] 📷 {name} (+ neg ref)", flush=True)
            p, t, details = run_single_test(name, cropped_paths, neg_cropped_path=neg_cropped)
            grand_pass2 += p
            grand_total2 += t
            for d in details:
                print(d, flush=True)
            if t > 0:
                print(f"    Score: {p}/{t}", flush=True)

        pct2 = (grand_pass2 / grand_total2 * 100) if grand_total2 > 0 else 0
        print(f"\n{'═' * 72}", flush=True)
        print(f"  TOTAL [Neg Baseline]: {grand_pass2}/{grand_total2} ({pct2:.0f}%)", flush=True)
        print(f"{'═' * 72}", flush=True)
        print(f"\n  Summary: Auto WB {pct:.0f}% → Neg Baseline {pct2:.0f}%", flush=True)

    # Cleanup temp files
    for path in cropped_paths.values():
        try:
            os.remove(path)
        except Exception:
            pass

    print("\n  Done! Check tests/debug_output/ for annotated images.", flush=True)


if __name__ == "__main__":
    main()
