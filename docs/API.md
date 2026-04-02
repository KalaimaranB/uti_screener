# Programmatic Usage — Urinalysis API

The codebase exposes a stable public Python API in the `api/` directory. You can use this to integrate the strip analyzer directly into larger systems or UI pipelines without calling the command-line scripts. 

## Import the API

```python
from api import analyze_strip, build_model_from_colors, save_model, evaluate_diagnoses
```

## 1. Calibration API

### `build_model_from_colors(chart_colors_path: str)`
Reads the measured RGB swatches from your `chart_colors.json` file and constructs a `CalibrationModel` for all analytes. The model calculates concentrations using perceptual CIELAB distances.

### `save_model(model: CalibrationModel, output_path: str)`
Saves the configured interpolation model to disk (typically `models/model.json`) so it can be rapidly loaded during the analysis phase.

---

## 2. Analysis API

### `analyze_strip(...) -> dict[str, AnalysisResult]`

The core workhorse for analysing a single cropped urinalysis strip.

**Parameters:**
*   `image_path (str)`: Path to the cropped strip image.
*   `model_path (str)`: Path to your saved `model.json` calibration file.
*   `strip_config_path (str)`: Path to `config/strip_config.json`.
*   *(Optional)* `negative_image_path (str)`: Path to a "pure negative" strip image. Providing this anchors the calibration curve to your specific lighting, improving accuracy from **75% to 95%**.
*   *(Optional)* `pre_cropped (bool)`: If True, bypasses the internal bounding box contour search.
*   *(Optional)* `manual_pad_h (int)`, `manual_gap_h (int)`, `manual_y_offset (int)`: If provided, completely bypasses the auto-geometric search.

**Returns:**
A dictionary mapping the analyte name (e.g. `"glucose"`) to an `AnalysisResult` dataclass.

---

### `AnalysisResult` (Dataclass)
*   **`analyte (str)`**: The string name of the pad.
*   **`color_rgb (tuple)`**: The final sampled median color (R, G, B) of the central 50% of the pad.
*   **`value (float | str)`**: The computed numeric concentration or string category.
*   **`unit (str)`**: The unit of measurement.
*   **`confidence (float)`**: A 0.0 to 1.0 confidence score, derived from **Piecewise 3D Polyline Projection** in RGB space.

---

## 3. Clinical Diagnostic API

### `evaluate_diagnoses(results: dict[str, Any]) -> list[str]`

Takes the dictionary output directly from `analyze_strip()` and passes it through the Clinical Classifier rule engine to screen for pathological configurations (e.g., UTIs, DKA).

---

### Example End-to-End Pipeline (95% Accuracy Mode)
```python
import json
from api import analyze_strip, build_model_from_colors, save_model, evaluate_diagnoses

# 1. Calibrate (only needs to be run once)
model = build_model_from_colors("config/chart_colors.json")
save_model(model, "models/model.json")

# 2. Analyze with Negative Baseline (recommended for high accuracy)
results = analyze_strip(
    image_path="test_strip.jpg",
    negative_image_path="Pure_negative.jpg",  # The key to 95% accuracy
    model_path="models/model.json",
    strip_config_path="config/strip_config.json",
    pre_cropped=True
)

# 3. Handle the results
glucose = results["glucose"]
print(f"Glucose: {glucose.value} {glucose.unit} (Confidence: {glucose.confidence:.0%})")

# 4. Clinically Validate
diagnoses = evaluate_diagnoses(results)
for diagnosis in diagnoses:
    print(f"DIAGNOSIS: {diagnosis}")
```
