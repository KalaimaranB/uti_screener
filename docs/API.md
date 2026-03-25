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
*   `strip_config_path (str)`: Path to `config/strip_config.json` containing the pad order template.
*   *(Optional)* `pre_cropped (bool)`: If True, bypasses the internal bounding box contour search and assumes the entire image is the strip.
*   *(Optional)* `manual_pad_h (int)`, `manual_gap_h (int)`, `manual_y_offset (int)`: If provided, completely bypasses the automatic geometric template search, firmly locking the 10 pads to these exact pixel dimensions.

**Returns:**
A dictionary mapping the analyte name (e.g. `"glucose"`) to an `AnalysisResult` dataclass containing the final computations.

### `AnalysisResult` (Dataclass)
*   **`analyte (str)`**: The string name of the pad.
*   **`color_rgb (tuple)`**: The final sampled median color (R, G, B) of the central 75% of the pad.
*   **`value (float | str)`**: The computed numeric concentration or string category (e.g., `'POSITIVE'`).
*   **`unit (str)`**: The unit of measurement (e.g., `'mg/dL'`).
*   **`confidence (float)`**: A 0.0 to 1.0 confidence score, derived from Euclidean Projection onto the 3D polynomial curve.

---

## 3. Clinical Diagnostic API

### `evaluate_diagnoses(results: dict[str, Any]) -> list[str]`

Takes the dictionary output directly from `analyze_strip()` and passes it through the Clinical Classifier rule engine to screen for pathological configurations.

**Parameters:**
*   `results`: The `dict[str, AnalysisResult]` output mapping returned by the `analyze_strip()` function.

**Returns:**
A `list` of strings containing the formal clinical diagnoses (e.g., `['Gram-Negative Bacterial UTI (e.g. E. coli or Klebsiella) - Indicated by Positive Leukocyte Esterase combined with nitrate reductase activity (Positive Nitrite).']`). If no pathology is matched, it returns `['Normal - No significant pathogenic biomarker combinations detected.']`.

---

### Example End-to-End Pipeline
```python
import json
from api import analyze_strip, build_model_from_colors, save_model, evaluate_diagnoses

# 1. Calibrate (only needs to be run once)
model = build_model_from_colors("config/chart_colors.json")
save_model(model, "models/model.json")

# 2. Analyze a new CV-cropped strip image
results = analyze_strip(
    image_path="test_image_123.jpg",
    model_path="models/model.json",
    strip_config_path="config/strip_config.json",
    pre_cropped=True,    # the image is already cropped tightly
    manual_pad_h=46,     # manually force the grid size
    manual_gap_h=18,
    manual_y_offset=21
)

# 3. Handle the results
glucose = results["glucose"]
print(f"Glucose: {glucose.value} {glucose.unit} (Confidence: {glucose.confidence:.0%})")
print(f"Pad Median Color (RGB): {glucose.color_rgb}")

# 4. Clinically Validate
diagnoses = evaluate_diagnoses(results)
for diagnosis in diagnoses:
    print(diagnosis)
```
