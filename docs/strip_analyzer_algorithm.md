# Urinalysis Strip Analyzer Algorithm (90% Accuracy Target)

The `StripAnalyzer` module is the core computer vision pipeline responsible for taking raw images of urinalysis dipped strips and mathematically isolating each of the 10 chemical reagent boxes. 

The system has been overhauled to move away from pure geometric grid search toward a **two-stage, color-aware segmentation pipeline** that enforces biological reality. This update helped the system achieve **90% accuracy** on the standard `true_samples` dataset.

---

## Stage 1: 1D Edge-Based Detection

The first stage attempts to find the pads by analyzing the "vertical signal" of the strip. Rather than finding boxes in 2D, we reduce the problem to a 1D brightness profile.

1.  **Column-Averaged Brightness**: We compute the average brightness of each row across the strip's width.
2.  **Gaussian Smoothing**: The 1D signal is smoothed using `gaussian_filter1d` (sigma=2.5) to eliminate printing noise and paper texture.
3.  **Brightness Run-Length Encoding (RLE)**: 
    - We classify each row as "Gap" (bright white plastic) or "Pad" (colored reagent) based on a floating brightness threshold (65th percentile).
    - We extract contiguous "runs" of Pad pixels.
4.  **Validation Gate**: 
    - We expect exactly 10 pad runs.
    - **Uniformity Check**: The system calculates the **Coefficient of Variation (CV)** for pad heights. If `CV > 0.3`, the detection is rejected as inconsistent.
    - **Physical Ratio Check**: The gap-to-pad ratio must fall between 0.15 and 1.2 during this early phase.

If Stage 1 finds a clean, periodic pattern, it returns immediately. If the patterns are messy (due to severe blur or matching colors), the system falls back to Stage 2.

---

## Stage 2: Constrained Grid Search Fallback

When simple edge detection fails, the system performs an exhaustive grid search over possible geometries, heavily constrained by physical manufacturing standards and known chemistry.

### 1. Hard Geometric Constraints
- **Pad Height (`pad_h`)**: Constrained to 45%–75% of the total strip period.
- **Gap Height (`gap_h`)**: Constrained to 30%–80% of the active pad height.
- **Search Range**: These constraints prevent the "slippage" errors common in simpler template matchers.

### 2. Multi-Term Objective Scoring
The "perfect fit" is the alignment that maximizes a holistic score composed of:

*   **A. Calibration Color Match (Primary - 8.0x Weight)**: 
    - This is the most critical logic update. The system uses the active `CalibrationModel` to ask: *"If this window is the Glucose pad, how well does its color match any of the known Glucose swatches?"*
    - By anchoring geometry to **biological reality**, the system can distinguish a pad from a gap even if they have identical brightness.
*   **B. Non-White Reward (Secondary - 3.0x Weight)**:
    - Reagent pads are typically colored (even if desaturated), while the strip backing is bright white plastic. We reward arrangements where "non-white" pixels fall inside the pad windows.
*   **C. Gap Brightness (Tertiary - 2.0x Weight)**:
    - We penalize any arrangement where the "gap" windows contain dark colors or heavy saturation.
*   **D. Soft Anchor (1.0x Weight)**:
    - We use the first derivative of the top of the strip to find the likely physical start of the plastic. We apply a soft quadratic penalty to any `y_offset` that deviates significantly from this anchor.

---

## 3. Simultaneous Orientation & Flip Detection

Previously, the system checked for upside-down strips as a post-processing step. Now, the **Grid Search evaluates both orientations in parallel**.

- It calculates a `score_normal` and a `score_flipped` for every possible geometry.
- If the "Flipped" reality yields a lower L2 color distance to the calibration swatches, the system declares `is_flipped = True`.
- This approach is significantly more robust than previous hue-based heuristics, as it uses the total evidence of all 10 pads to determine orientation.

---

## 4. Sampling & Border Mitigation

Once the boundaries are locked:
1.  The system samples the **central 50%** of the identified pad region.
2.  This "core sampling" avoids **Border Contamination** (where the chemical reagent meets the white plastic) and **Wick Effects** (where excess liquid pools at the edges of the pad).
3.  A median average is taken of these core pixels to produce the final RGB triplet sent to the interpolation engine.
