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

## Step 1 — Colour Space: Why CIELAB?

All colour comparisons are done in **CIELAB** colour space, not RGB.

| Space | Problem |
|-------|---------|
| RGB | Euclidean distance does *not* correspond to perceptual difference. Two colours that *look* identical can be far apart in RGB (e.g. due to gamma). |
| CIELAB | Designed so that equal Euclidean distances correspond to equal perceived differences. A delta-E of ~2.3 is typically the "just noticeable difference" threshold. |

Conversion pipeline:
```
RGB (0–255)  →  linear RGB (0–1)  →  CIE XYZ  →  CIELAB (L*, a*, b*)
```
Implemented via `skimage.color.rgb2lab` with the D65 standard illuminant.

---

## Step 2 — Colour Distance: CIE76 Delta-E

The distance between two colours in the model is:

```
ΔE = √( (L₁−L₂)² + (a₁−a₂)² + (b₁−b₂)² )
```

This is CIE76. ΔE < 5 is considered a good match. ΔE > 25 means the colours are very different.

---

## Step 3 — Swatch Grouping (handling NEGATIVE ranges)

Some analytes (glucose, bilirubin) have two "negative" swatches on the chart — both map to value 0, but cover a range of colours.

Before interpolation, all swatches sharing the same concentration value are **collapsed to their LAB centroid**:

```
centroid_L = mean(L₁, L₂, ...)
centroid_a = mean(a₁, a₂, ...)
centroid_b = mean(b₁, b₂, ...)
```

This means NEGATIVE_1 and NEGATIVE_2 together define the "zero zone", and anything closer to that centroid than to the next swatch maps to 0.

---

## Step 4 — Concentration Interpolation

For **numeric analytes** (glucose, pH, etc.):

1. Compute ΔE from the strip colour to every reference swatch centroid.
2. Take the two closest reference points `(v₁, ΔE₁)` and `(v₂, ΔE₂)`.
3. Compute weights inversely proportional to distance:
   ```
   w₁ = 1 − ΔE₁ / (ΔE₁ + ΔE₂)
   w₂ = 1 − ΔE₂ / (ΔE₁ + ΔE₂)
   interpolated = (w₁·v₁ + w₂·v₂) / (w₁ + w₂)
   ```
4. This is **inverse-distance weighting** — the closer colour dominates.

For **categorical analytes** (nitrite):

- Simply return the label of the nearest swatch (no interpolation).

---

## Step 5 — Confidence Score

```
confidence = max(0, 1 − ΔE_best / 50)
```

| Confidence | Meaning |
|-----------|---------|
| 1.0 (100%) | Strip colour exactly matches a chart swatch |
| 0.8–1.0 | Very close match, reliable result |
| 0.5–0.8 | Moderate match — result is plausible but lighting/camera may differ |
| < 0.5 | Poor match — treat result as approximate |

The denominator `50` is the normalisation constant — a ΔE of 50 is a very large perceptual difference (e.g. red vs. teal). You can adjust this in `color_utils.py` if you want stricter or looser confidence thresholds.

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

### 6. Upgrade to CIE2000 delta-E (future work)
CIE76 (current) is fast and simple, but CIE2000 is more perceptually accurate, especially for low-chroma (pale/washed-out) colours like many strip swatches. Switching would improve confidence on analytes like nitrite and protein.

Replace in `core/color_utils.py`:
```python
# Current — CIE76:
return math.sqrt((L1-L2)**2 + (a1-a2)**2 + (b1-b2)**2)

# Improved — would require implementing CIEDE2000 formula:
return ciede2000(lab1, lab2)
```

### 7. Collect a training dataset and fit a proper model
The current approach is pure physical interpolation. If you collect many strip images with known ground-truth results, you can train a small regression model (e.g. k-NN or a 3-layer MLP) per analyte using LAB as input and concentration as output. This handles camera-specific colour shifts automatically.

---

## SOLID Design Reference

| Principle | Where |
|-----------|-------|
| **SRP** | `color_utils` handles colour math only; `calibration` handles model IO; `strip_analyzer` handles image processing only |
| **OCP** | Add new analytes by editing `chart_colors.json` — zero code changes |
| **LSP** | Numeric and categorical analytes share the same `predict()` interface |
| **ISP** | Callers use `api/` only — never import from `core/` directly |
| **DIP** | `StripAnalyzer` depends on `CalibrationModel` interface, not a specific interpolation strategy |
