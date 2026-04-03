# API Reference — Urinalysis Programmatic Usage

The Urinalysis Strip Analyzer provides a stable Python API for programmatic integration into custom UI pipelines or batch processing systems.

---

## 🛠️ Importing the API

All public-facing functions are exposed through the `api/` directory.

```python
from api import analyze_strip, build_model_from_colors, save_model, evaluate_diagnoses
```

---

## 1. 🎛️ Calibration API

Calibration must be performed **once** per chart type.

### `build_model_from_colors(chart_colors_path: str)`
Constructs a `CalibrationModel` using measured RGB swatches.
- **Param**: Path to `config/chart_colors.json`.
- **Logic**: Calculates 3D piecewise polylines in Chromaticity space for all 10 analytes.

### `save_model(model: CalibrationModel, output_path: str)`
Serializes the interpolation model to disk (typically `models/model.json`).

---

## 2. 🔍 Analysis API

The core workhorse for analyzing single strip images.

### `analyze_strip(...) -> dict[str, AnalysisResult]`
Takes a cropped strip and returns a dictionary of concentration results.

**Parameters:**
- `image_path (str)`: Path to the cropped strip image.
- `model_path (str)`: Path to the saved `model.json`.
- `strip_config_path (str)`: Path to `config/strip_config.json`.
- `negative_image_path (Optional[str])`: **CRITICAL for 95% accuracy**. A dipped-but-negative strip in the same lighting.
- `pre_cropped (bool)`: If True, skips internal bounding box search.

**Returns:**
A dictionary mapping the analyte (e.g., `"glucose"`) to an `AnalysisResult` dataclass.

### `AnalysisResult` (Dataclass)
- `analyte (str)`: The pad type (e.g., "protein").
- `color_rgb (tuple)`: Median (R, G, B) sampled from the central 50% of the pad.
- `value (float|str)`: The numeric concentration or categorical label.
- `unit (str)`: Units (e.g., "mg/dL").
- `confidence (float)`: Score (0.0–1.0) derived from 3D projection distance.

---

## 3. 🏥 Clinical Validator API

### `evaluate_diagnoses(results: dict[str, AnalysisResult]) -> list[str]`
Passes the raw results dictionary through the clinical heuristic engine.
- **Returns**: A list of string warnings (e.g., "UTI: Gram-Negative Bacterial Infection Suspected").

---

## 🚀 End-to-End Example (95% Accuracy Mode)

```python
import json
from api import analyze_strip, build_model_from_colors, save_model, evaluate_diagnoses

# 1. Setup Models
model = build_model_from_colors("config/chart_colors.json")
save_model(model, "models/model.json")

# 2. Run Analysis (with Negative Baseline for high accuracy)
results = analyze_strip(
    image_path="test_strip.jpg",
    model_path="models/model.json",
    strip_config_path="config/strip_config.json",
    negative_image_path="negative_ref.jpg"
)

# 3. Print Results
glucose = results["glucose"]
print(f"Glucose: {glucose.value} {glucose.unit} (Confidence: {glucose.confidence:.0%})")

# 4. Clinically Validate
diagnoses = evaluate_diagnoses(results)
for diagnosis in diagnoses:
    print(f"DIAGNOSIS WARNING: {diagnosis}")
```

---

## 🔗 Related Documentation
- [Algorithm Design](ALGORITHM.md) — How the analysis works under the hood.
- [Clinical Diagnostics](CLINICAL_DIAGNOSTICS.md) — The rationale behind the warnings.
- [Configuration Guide](CONFIGURATION_GUIDE.md) — Tuning the `analyze_strip` parameters.
