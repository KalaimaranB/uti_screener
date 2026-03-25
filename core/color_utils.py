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
    if abs(interpolated) < 1e-6:
        return ("NEGATIVE", round(confidence, 4))
        
    return (round(interpolated, 4), round(confidence, 4))
