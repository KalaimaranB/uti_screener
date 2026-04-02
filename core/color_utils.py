"""
core/color_utils.py — Color space utilities for urinalysis strip analysis.

Provides:
  - color_distance_rgb: Euclidean distance in RGB space
  - interpolate_concentration: Map a color to a concentration value via
                               nearest-neighbour linear interpolation in RGB space
"""
from __future__ import annotations

import math
from typing import Union


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
RGB = tuple[int, int, int]          # 0-255 per channel


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def color_distance_rgb(rgb1: RGB, rgb2: tuple[float, float, float]) -> float:
    """Return Euclidean distance between two RGB colours."""
    return math.sqrt(
        (rgb1[0] - rgb2[0]) ** 2 +
        (rgb1[1] - rgb2[1]) ** 2 +
        (rgb1[2] - rgb2[2]) ** 2
    )


def interpolate_concentration(
    color_rgb: RGB,
    reference_points: list[dict],
    negative_threshold: float = 0.0,
    use_hue: bool = False,  
) -> tuple[Union[float, str], float]:

    """
    Interpolate the concentration for *color_rgb* given a list of reference
    colour→concentration mappings.

    Parameters
    ----------
    color_rgb:
        The RGB colour sampled from the strip box.
    reference_points:
        List of dicts, each with keys:
          - "rgb":   RGB tuple (or centroid float tuple)
          - "value": numeric or categorical concentration value

    Returns
    -------
    (value, confidence)
        value:       interpolated (or nearest-match) concentration
        confidence:  0.0 – 1.0; 1.0 means exact match, lower is further away
    """
    if not reference_points:
        raise ValueError("reference_points must not be empty")

    confidence_scale = 100.0

    if use_hue:
        query_hue = _rgb_to_hue(color_rgb)
        sorted_refs = sorted(reference_points, key=_sort_key)
        ref_hues = [_rgb_to_hue(rp["rgb"]) for rp in sorted_refs]

        # Find which segment the query hue falls in
        best_fraction = 0.0
        best_segment_idx = 0
        min_dist = float('inf')

        for i in range(len(sorted_refs) - 1):
            ha, hb = ref_hues[i], ref_hues[i + 1]
            span = hb - ha
            if abs(span) < 1e-6:
                continue
            frac = (query_hue - ha) / span
            frac_clamped = max(0.0, min(1.0, frac))
            proj_hue = ha + frac_clamped * span
            dist = abs(query_hue - proj_hue)
            if dist < min_dist:
                min_dist = dist
                best_fraction = frac_clamped
                best_segment_idx = i

        # Confidence: how far (in hue degrees) from the nearest reference
        confidence = max(0.0, 1.0 - min_dist / 30.0)

        val_a = sorted_refs[best_segment_idx]["value"]
        val_b = sorted_refs[best_segment_idx + 1]["value"]
        interpolated = float(val_a) + best_fraction * (float(val_b) - float(val_a))

        if abs(interpolated) < 1e-6 or interpolated <= negative_threshold:
            return ("NEGATIVE", round(confidence, 4))
        return (round(interpolated, 4), round(confidence, 4))

    # Convert all RGBs to Chromaticity Vector Space (R/sum, G/sum, B/sum) * 255
    # This precisely enforces "a*R + c*B" hue weighting and completely ignores shadows
    def _chroma(c: RGB) -> tuple[float, float, float]:
        s = sum(c)
        if s == 0:
            return (0.0, 0.0, 0.0)
        return (c[0] * 255.0 / s, c[1] * 255.0 / s, c[2] * 255.0 / s)

    query_chroma = _chroma(color_rgb)

    # Sort reference points numerically (fall back to label string sort for Categorical)
    def _sort_key(rp: dict) -> float:
        val = rp["value"]
        if isinstance(val, str):
            # For Nitrite: NEGATIVE (0), POSITIVE (1)
            return 0.0 if "NEG" in val.upper() else 1.0
        return float(val)

    sorted_refs = sorted(reference_points, key=_sort_key)

    if len(sorted_refs) == 1:
        dist = color_distance_rgb(query_chroma, _chroma(sorted_refs[0]["rgb"]))
        confidence = max(0.0, 1.0 - dist / confidence_scale)
        val = sorted_refs[0]["value"]
        if isinstance(val, str):
            return (val, round(confidence, 4))
        num_val = float(val)
        if abs(num_val) < 1e-6:
            return ("NEGATIVE", round(confidence, 4))
        return (num_val, round(confidence, 4))

    def _closest_point_on_segment(Q: tuple[float, float, float], P_a: tuple[float, float, float], P_b: tuple[float, float, float]) -> tuple[float, float]:
        """
        Projects point Q onto the line segment connecting P_a and P_b.
        Returns (fraction_along_segment, perpendicular_distance).
        """
        v = (P_b[0] - P_a[0], P_b[1] - P_a[1], P_b[2] - P_a[2])
        w = (Q[0] - P_a[0], Q[1] - P_a[1], Q[2] - P_a[2])
        
        c1 = sum(w_i * v_i for w_i, v_i in zip(w, v))
        if c1 <= 0:
            return 0.0, color_distance_rgb(Q, P_a)
            
        c2 = sum(v_i * v_i for v_i in v)
        if c2 <= c1:
            return 1.0, color_distance_rgb(Q, P_b)
            
        b = c1 / c2
        proj = (P_a[0] + b * v[0], P_a[1] + b * v[1], P_a[2] + b * v[2])
        return b, color_distance_rgb(Q, proj)

    min_dist = float('inf')
    best_fraction = 0.0
    best_segment_idx = 0

    # Find the single line segment perfectly closest to the query colour
    for i in range(len(sorted_refs) - 1):
        P_a = _chroma(sorted_refs[i]["rgb"])
        P_b = _chroma(sorted_refs[i+1]["rgb"])

        # Project colour onto this segment
        fraction, dist = _closest_point_on_segment(query_chroma, P_a, P_b)
        
        if dist < min_dist:
            min_dist = dist
            best_fraction = fraction
            best_segment_idx = i

    confidence = max(0.0, 1.0 - min_dist / confidence_scale)

    val_a = sorted_refs[best_segment_idx]["value"]
    val_b = sorted_refs[best_segment_idx + 1]["value"]

    # --- Categorical: Return closest label along segment ---
    if isinstance(val_a, str):
        best_value = val_a if best_fraction < 0.5 else val_b
        return (best_value, round(confidence, 4))

    # --- Numeric: Continuous Interpolation ---
    interpolated = float(val_a) + best_fraction * (float(val_b) - float(val_a))
    
    # If the reading falls in the 0.0 zone (like NEGATIVE_1 to NEGATIVE_2), output "NEGATIVE"
    if abs(interpolated) < 1e-6 or interpolated <= negative_threshold:
        return ("NEGATIVE", round(confidence, 4))
        
    return (round(interpolated, 4), round(confidence, 4))

# ---------------------------------------------------------------------------
# Calibration Curve Shift (Negative Baseline)
# ---------------------------------------------------------------------------

def compute_curve_shift(
    reference_negatives: dict[str, RGB],
    measured_negatives: dict[str, RGB],
) -> dict[str, tuple[int, int, int]]:
    """
    Compute per-analyte additive offsets by comparing reference chart negatives
    against measured negative strip colors.

    The offset is:  measured_negative - reference_negative

    This offset is then applied to ALL swatches in the calibration curve,
    shifting the entire curve into the user's actual color space.

    Parameters
    ----------
    reference_negatives:
        Analyte → reference RGB of the baseline swatch from chart_colors.json.
    measured_negatives:
        Analyte → RGB sampled from the user's negative strip image.

    Returns
    -------
    dict[analyte → (delta_R, delta_G, delta_B)] additive offsets.
    """
    offsets: dict[str, tuple[int, int, int]] = {}
    for analyte in reference_negatives:
        if analyte not in measured_negatives:
            offsets[analyte] = (0, 0, 0)
            continue

        ref = reference_negatives[analyte]
        meas = measured_negatives[analyte]

        delta = (
            meas[0] - ref[0],
            meas[1] - ref[1],
            meas[2] - ref[2],
        )
        offsets[analyte] = delta

    return offsets


def apply_curve_shift_to_swatches(
    swatches_rgb: list[RGB],
    offset: tuple[int, int, int],
) -> list[RGB]:
    """
    Shift all reference swatch RGB values by the additive offset.

    This moves the calibration curve into the user's color space so that
    color matching happens directly against measured values without
    transforming the input.

    Parameters
    ----------
    swatches_rgb : List of (R, G, B) reference colors.
    offset : (delta_R, delta_G, delta_B) from compute_curve_shift.

    Returns
    -------
    List of shifted (R, G, B) tuples, clamped to [0, 255].
    """
    shifted = []
    for rgb in swatches_rgb:
        r = int(min(255, max(0, rgb[0] + offset[0])))
        g = int(min(255, max(0, rgb[1] + offset[1])))
        b = int(min(255, max(0, rgb[2] + offset[2])))
        shifted.append((r, g, b))
    return shifted

def _rgb_to_hue(rgb: tuple) -> float:
    """Return hue angle in degrees (0-360) from an RGB tuple."""
    r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin
    if delta < 1e-6:
        return 0.0
    if cmax == r:
        h = 60.0 * (((g - b) / delta) % 6)
    elif cmax == g:
        h = 60.0 * (((b - r) / delta) + 2)
    else:
        h = 60.0 * (((r - g) / delta) + 4)
    return h % 360.0