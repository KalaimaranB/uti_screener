# Configuration Guide — Urinalysis Strip Analyzer

The Urinalysis Strip Analyzer is highly configurable, allowing for different strip types, lighting environments, and calibration swatches. All settings are stored in the `config/` directory.

---

## 🗒️ `config/strip_config.json`

This file controls the geometric search and analyte order.

```json
{
  "boxes_top_to_bottom": [
    "leukocytes",
    "nitrite",
    "urobilinogen",
    "protein",
    "ph",
    "blood",
    "specific_gravity",
    "ketone",
    "bilirubin",
    "glucose"
  ],
  "template_mask": {
    "manual_pad_h": null,
    "manual_gap_h": null,
    "manual_y_offset": null
  }
}
```

### Key Parameters:
- **`boxes_top_to_bottom`**: The exact physical sequence of the 10 pads on your strip.
- **`manual_pad_h`**: Height of each reagent pad in pixels (set to `null` for automatic detection).
- **`manual_gap_h`**: Height of the unprinted gap between pads (set to `null` for automatic detection).
- **`manual_y_offset`**: Pixel where the top of the first pad begins (set to `null` for automatic detection).

---

## 🎨 `config/chart_colors.json`

This file stores the laboratory-calibrated RGB values for every swatch on the bottle chart.

```json
{
  "glucose": [
    {"label": "NEG", "value": 0, "rgb": [120, 150, 200]},
    {"label": "100+", "value": 100, "rgb": [100, 130, 140]}
  ]
}
```

### How to Calibrate (Program 1):
1. Use **Digital Color Meter** (on macOS) set to **"Display in sRGB"**.
2. Measure the central RGB of each swatch from the bottle art.
3. Update `chart_colors.json` accordingly.
4. Run `python3 program1_calibrate.py` to bake these into `models/model.json`.

---

## 📏 `config/chart_rois.json` (Advanced)

If you prefer to calibrate from a **photograph of the chart**, use this file to define the (X, Y, W, H) pixel coordinates of every swatch on that image.

```json
{
    "glucose": [
        [100, 200, 50, 50],
        [160, 200, 50, 50]
    ]
}
```

---

## 🔦 Optimization Parameters

In `core/strip_segmenter.py` and `core/calibration.py`, you can fine-tune several hard-coded constants:

| Constant | Default | Purpose |
|----------|---------|---------|
| **`SIGMA`** | 2.5 | Gaussian blur level for the vertical signal. |
| **`DEADZONE`** | 25.0 | RGB threshold before forcing a result to "NEGATIVE". |
| **`PINKNESS_GAP`** | +4 | Sensitivity for subtle Nitrite pink-shifts. |
| **`SCORE_WEIGHTS`** | 8.0/3.0/2.0 | Relative importance of color-match vs. geometric-brightness. |

---

## 🔗 Related Documentation
- [Algorithm Design](ALGORITHM.md) — How these configurations affect the search.
- [API Reference](API_REFERENCE.md) — Passing paths to these JSON files.
