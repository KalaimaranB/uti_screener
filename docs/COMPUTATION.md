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

## Step 6 — Two-Stage Strip Segmentation

The algorithm no longer uses simple peak-detection, as these fail when adjacent pads are identical in colour or when a pad perfectly matches the white strip background. 

Instead, it uses a **Two-Stage Geometric Fit**:

1.  **Stage 1: Edge-Based Detection**: The system computes a 1D signal of the strip's vertical brightness. It uses a Gaussian-smoothed derivative to find "runs" of pixels that represent pads. If the detection passes a **Coefficient of Variation (CV < 0.3)** gate (meaning the pads look uniform and periodic), it returns immediately.
2.  **Stage 2: Color-Driven Grid Search Fallback**: If Stage 1 fails, the system performs an exhaustive grid search. The **primary scoring signal (8.0x weight)** is the L2 distance between the sampled pad color and the actual **Calibration Swatches**. This ensures the geometry is locked to biological reality rather than just pixel brightness.

---

## Step 7 — Negative Baseline Correction (The 90% Accuracy Key)

Light "Color Drift" is the single largest source of error in urinalysis. Depending on your room's light bulbs (warm vs. cool), a perfectly negative strip might look slightly yellow or blue to the camera, leading the system to predict false positives.

To solve this, the system implements a **Negative Baseline Correction**:

1.  **Reference Negatives**: The `CalibrationModel` knows what a "perfect" negative strip looks like under laboratory lighting.
2.  **User Negatives**: The user provides an image of a **dipped-but-negative strip** (or uses the built-in beige-centric baseline).
3.  **Additive Offset**: The system calculates the RGB difference (Delta) between the User's negative and the Reference negative.
4.  **Curve Shifting**: Every swatch in the calibration model is mathematically shifted by this Delta before prediction. This effectively "moves the goalposts" of the calibration curve into your specific room's lighting space.

**Result**: Implementing this correction improved the pipeline accuracy from **72% to 90%** across the `true_samples` validation set.

---

## How to Improve Accuracy

### 1. Supply a Negative Reference Image
The most impactful way to hit 90% accuracy is to provide a negative strip image during analysis.
- **CLI**: `python3 program2_analyze.py --image strip.jpg --negative Pure_negative.jpg`
- **API**: Pass `negative_image_path` to `analyze_strip()`.

### 2. Improve your swatch RGB measurements
- Use **Digital Color Meter set to "Display in sRGB"** (not native, not P3).
- Sample from the very **centre** of each swatch, away from any printed text.

### 3. Calibrate under consistent lighting
Real strip images are affected by ambient light colour temperature. For best accuracy, photograph strips in **consistent, neutral (daylight-balanced) lighting**.

### 4. Manually align the template (Last Resort)
If auto-segmentation fails (e.g. due to severe image blur), you can lock the template directly.
In `strip_config.json`:
```json
  "template_mask": {
    "manual_pad_h": 46,
    "manual_gap_h": 18,
    "manual_y_offset": 21
  }
```

---

## SOLID Design Reference

| Principle | Where |
|-----------|-------|
| **SRP** | `color_utils` handles colour math; `calibration` handles model IO; `strip_segmenter` handles geometric isolation. |
| **OCP** | Add new analytes by editing `chart_colors.json` — zero code changes required. |
| **LSP** | Numeric and categorical analytes share the same `predict()` interface. |
| **ISP** | Callers use `api/` only — never import from `core/` directly. |
| **DIP** | `StripAnalyzer` depends on `CalibrationModel` interface, not a specific interpolation strategy. |
