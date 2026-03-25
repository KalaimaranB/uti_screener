"""
core/color_utils.py — Color space utilities for urinalysis strip analysis.

Provides:
  - rgb_to_lab: Convert RGB to CIELAB (via scikit-image, NumPy 2.0 compatible)
  - delta_e:    Perceptual color distance (CIE76)
  - interpolate_concentration: Map a color to a concentration value via
                               nearest-neighbour linear interpolation in LAB space
"""
from __future__ import annotations

import math
import numpy as np
from typing import Union
from skimage import color as skcolor


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
RGB = tuple[int, int, int]          # 0-255 per channel
LAB = tuple[float, float, float]    # L* 0-100, a* -128..127, b* -128..127


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def rgb_to_lab(rgb: RGB) -> LAB:
    """Convert an (R, G, B) tuple (0-255) to a (L*, a*, b*) CIELAB tuple."""
    # skimage expects float64 in [0, 1] with shape (1,1,3)
    rgb_arr = np.array([[[rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0]]], dtype=np.float64)
    lab_arr = skcolor.rgb2lab(rgb_arr)
    L, a, b = float(lab_arr[0, 0, 0]), float(lab_arr[0, 0, 1]), float(lab_arr[0, 0, 2])
    return (L, a, b)


def delta_e(lab1: LAB, lab2: LAB) -> float:
    """Return CIE76 perceptual distance between two CIELAB colours."""
    return math.sqrt(
        (lab1[0] - lab2[0]) ** 2 +
        (lab1[1] - lab2[1]) ** 2 +
        (lab1[2] - lab2[2]) ** 2
    )


def interpolate_concentration(
    color_lab: LAB,
    reference_points: list[dict],
) -> tuple[Union[float, str], float]:
    """
    Interpolate the concentration for *color_lab* given a list of reference
    colour→concentration mappings.

    Parameters
    ----------
    color_lab:
        The CIELAB colour sampled from the strip box.
    reference_points:
        List of dicts, each with keys:
          - "lab":   LAB tuple
          - "value": numeric or categorical concentration value

    Returns
    -------
    (value, confidence)
        value:       interpolated (or nearest-match) concentration
        confidence:  0.0 – 1.0; 1.0 means exact match, lower is further away
    """
    if not reference_points:
        raise ValueError("reference_points must not be empty")

    # Compute distances to every reference
    distances: list[float] = [
        delta_e(color_lab, rp["lab"]) for rp in reference_points
    ]

    ranked = sorted(enumerate(distances), key=lambda x: x[1])
    best_idx, best_dist = ranked[0]

    # --- Categorical analytes: just return closest ---
    best_value = reference_points[best_idx]["value"]
    if isinstance(best_value, str):
        confidence = max(0.0, 1.0 - best_dist / 50.0)
        return (best_value, round(confidence, 4))

    # --- Numeric analytes: interpolate between two nearest ---
    if len(ranked) == 1:
        confidence = max(0.0, 1.0 - best_dist / 50.0)
        return (float(best_value), round(confidence, 4))

    second_idx, second_dist = ranked[1]
    second_value = reference_points[second_idx]["value"]

    total = best_dist + second_dist
    if total < 1e-6:           # virtually identical colour → exact match
        return (float(best_value), 1.0)

    # Weighted average (closer reference gets more weight)
    w1 = 1.0 - best_dist / total
    w2 = 1.0 - second_dist / total
    interpolated = (w1 * float(best_value) + w2 * float(second_value)) / (w1 + w2)
    confidence = max(0.0, 1.0 - best_dist / 50.0)

    return (round(interpolated, 4), round(confidence, 4))
