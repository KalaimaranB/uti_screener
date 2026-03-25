# Computation Guide — Urinalysis Strip Analyzer

This document explains the algorithm that converts raw strip pixel colours into concentration values, and gives concrete advice for improving accuracy.

---

## Overview

```
Chart image / RGB values
        ↓
  [Program 1]  Build per-analyte colour→concentration model
        ↓
   model.json  (saved calibration)
        ↓
  [Program 2]  Load model → crop strip → segment boxes → sample colour → predict
        ↓
   Results JSON  (concentration + confidence per analyte)
```

---

## Step 1 — Colour Space: Chromaticity Normalization (Hue Ratios)

All colour comparisons are done directly in **Chromaticity Vector Space**.

If we simply used raw RGB distance, a dark shadow caused by poor camera lighting (which drops Red, Green, and Blue proportionally) would mathematically mimic the physical darkness of a dark-colour reagent pad (like Glucose ++++). 

To cleanly separate **Chemical Hue** from **Camera Lighting**, the model divides every RGB pixel by the sum of its channels to find its pure Hue Ratios:

```
R_chroma = (R / (R + G + B)) * 255
G_chroma = (G / (R + G + B)) * 255
B_chroma = (B / (R + G + B)) * 255
```

This enforces strict linear weightings (`a*R + b*G + c*B`) where differences in a specific dye colour (like a drop in Green for the pink Nitrite pad) are overwhelmingly punished, while generic lighting shadows are mathematically erased.

---

## Step 2 — Colour Distance: Euclidean Distance

The distance between two colours is the standard 3D Pythagorean distance between their purely normalized Chromaticity vectors:

```
Distance = √( (R₁−R₂)² + (G₁−G₂)² + (B₁−B₂)² )
```

Because Chromaticity space is smaller and tighter than raw RGB, a distance < 5 is considered a near-perfect match.

---

## Step 3 — Negative Swatch Segments (The Zero-Zone)

Some analytes (glucose, bilirubin) have two "negative" swatches on the chart — both correspond to a concentration value of `0`, but cover slightly different background colours.

The model preserves both of these separate colours as explicit `0` reference points in the continuous matrix.

---

## Step 4 — Concentration: 3D Piecewise Polyline Projection

The model uses a continuous **Piecewise 3D Polyline Projection**.

1. The set of calibrated reference swatches forms a connected, structural trajectory line bending through the 3D Chromaticity space (e.g. `Light Blue -> Green -> Brown`).
2. When the system reads a new pixel colour `C`, it calculates the shortest, perpendicular mathematically projected distance to every straight segment on that line.
3. The coordinate that drops strictly onto that line segment perfectly dictates the **interpolated concentration fraction**.
4. By forcing the prediction to snap strictly onto the structural timeline between known chemical states, it guarantees the prediction can never wildly jump far out-of-bounds due to camera noise or glare.

If the returned numerical concentration happens to evaluate exactly onto the flat segment connecting two zero-value nodes (like `NEGATIVE_1` to `NEGATIVE_2`), the algorithm intercepts the result and explicitly prints the **"NEGATIVE"** string literal instead of `0.0`.

---

## Step 5 — Confidence Score

```
confidence = max(0, 1 − Perpendicular_Distance / 100.0)
```

| Confidence | Meaning |
|-----------|---------|
| 1.0 (100%) | Strip colour exactly matches a chart swatch |
| 0.8–1.0 | Very close match, reliable result |
| 0.5–0.8 | Moderate match — result is plausible but lighting/camera may differ |
| < 0.5 | Poor match — treat result as approximate |

The denominator `100.0` is the normalisation constant in Chromaticity space. You can adjust this in `color_utils.py` if you want stricter or looser confidence thresholds.

---

## Step 6 — Strip Segmentation

The algorithm no longer uses simple peak-detection or blob-detection, as these fail when adjacent pads are identical in colour or when a pad perfectly matches the white strip background. 

Instead, it uses a **Geometric Template Match via Edge Gradients**:

1. Reagent strips have a known physical constraint: exactly 10 equally-sized pads separated by equally-sized structural gaps.
2. The algorithm computes a 1D signal of the strip's **vertical colour gradients** (edges). A high gradient marks the physical boundary between a gap and a pad.
3. It performs an exhaustive grid-search over possible template geometries: `pad_height`, `gap_height`, and `y_offset`.
4. The optimiser scores each possible template by summing the gradient values at exactly the 20 predicted row boundaries.
5. The template with the highest boundary-gradient score is picked. This perfectly locks onto the true physical edges of the pads, actively ignoring internal printing anomalies or dark vs. light colour saturations.
6. The central 50% of each identified pad is sampled using a median pixel average to avoid border contamination.

---

## How to Improve Confidence

### 1. Improve your swatch RGB measurements
- Use **Digital Color Meter set to "Display in sRGB"** (not native, not P3).
- Sample from the very **centre** of each swatch, away from any printed text.
- If your chart image is printed, colours will vary by printer — re-measure swatches on the printed chart you actually use.

### 2. Add intermediate reference swatches
For analytes with low confidence, add extra swatches between the existing ones. For example, pH only has 7 reference points (5.0 to 8.5). If your readings fall between them, accuracy drops. You can:
- Pick the approximate intermediate pH value (e.g. 5.75) from a test strip known to read that pH.
- Measure its RGB with Digital Color Meter.
- Add it to `chart_colors.json` with `"value": 5.75`.

### 3. Calibrate under consistent lighting
Real strip images are affected by ambient light colour temperature. For best accuracy:
- Photograph strips in **consistent, neutral (daylight-balanced) lighting**.
- Consider adding a **white balance reference patch** in the image to correct for lighting shifts computationally.

### 4. Manually align the template
If the edge-gradient search fails to correctly identify the pads (e.g. due to severe image blur or extreme shadows), you can lock the template directly to the physical pixels.

In `strip_config.json`:
```json
  "template_mask": {
    "manual_pad_h": 46,
    "manual_gap_h": 18,
    "manual_y_offset": 21
  }
```
Setting these integers entirely bypasses the algorithm's geometric search and locks the bounding boxes exactly to your specified layout. (Run with `--debug` to verify your manual numbers align correctly).

### 5. Consider a white-balance correction pre-step
If strip images vary in colour temperature (warm vs. cool), you can add a white balance normalisation step to `strip_analyzer.py`. The formula is:

```python
# Assuming a neutral grey patch is present in image at known (x,y,w,h)
grey = sample_box_color(grey_roi)
scale_r = 128 / grey[0]
scale_g = 128 / grey[1]
scale_b = 128 / grey[2]
corrected_rgb = (min(255, r * scale_r), ...)
```

### 6. Collect a training dataset and fit a proper model
The current approach is pure physical interpolation. If you collect many strip images with known ground-truth results, you can train a small regression model (e.g. k-NN or a 3-layer MLP) per analyte using RGB as input and concentration as output. This handles camera-specific colour shifts automatically.

---

## SOLID Design Reference

| Principle | Where |
|-----------|-------|
| **SRP** | `color_utils` handles colour math only; `calibration` handles model IO; `strip_analyzer` handles image processing only |
| **OCP** | Add new analytes by editing `chart_colors.json` — zero code changes |
| **LSP** | Numeric and categorical analytes share the same `predict()` interface |
| **ISP** | Callers use `api/` only — never import from `core/` directly |
| **DIP** | `StripAnalyzer` depends on `CalibrationModel` interface, not a specific interpolation strategy |
