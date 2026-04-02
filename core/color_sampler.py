import numpy as np
from typing import List, Tuple, Optional
from core.color_utils import RGB

def sample_box_color(box_img: np.ndarray) -> RGB:
    """
    Return the median BGR→RGB colour of the central 75% of a box image.
    Sampling the centre avoids border contamination from adjacent pads.
    """
    h, w = box_img.shape[:2]
    # 12.5% padding on each side leaves the central 75%
    y0, y1 = int(h * 0.125), int(h * 0.875)
    x0, x1 = int(w * 0.125), int(w * 0.875)
    core = box_img[y0:y1, x0:x1]

    # Ensure we have some pixels
    if core.size == 0:
        core = box_img

    pixels = core.reshape(-1, 3)
    
    # Ignore black background pixels if the scan slightly overlapped the edge
    brightness = pixels.mean(axis=1)
    valid_pixels = pixels[brightness > 30]
    
    if len(valid_pixels) == 0:
        valid_pixels = pixels # fallback to all if entire box is < 30
        
    median_bgr = np.median(valid_pixels, axis=0).astype(int)
    # OpenCV uses BGR; convert to RGB
    return (int(median_bgr[2]), int(median_bgr[1]), int(median_bgr[0]))


def white_balance_from_plastic(
    strip_img: np.ndarray,
    boundaries: List[Tuple[int, int]],
) -> Tuple[float, float, float]:
    """
    Estimate per-channel white balance gains from the white plastic gaps
    between reagent pads. This provides a fallback color correction when
    no negative reference image is available.

    Parameters
    ----------
    strip_img : np.ndarray
        The BGR strip image (e.g. 100×800 standardized).
    boundaries : list of (y_start, y_end)
        Pad boundaries from the segmenter.

    Returns
    -------
    (gain_r, gain_g, gain_b) : per-channel multiplicative gains to apply
        to sampled RGB values. Gains normalize the strip's white plastic
        backing to a neutral reference white (235, 235, 235).
    """
    h, w = strip_img.shape[:2]
    gap_pixels = []

    # Collect pixels from the gaps between pads
    for i in range(len(boundaries) - 1):
        gap_top = boundaries[i][1]
        gap_bot = boundaries[i + 1][0]
        if gap_bot <= gap_top:
            continue
        # Sample central 60% of the gap width to avoid edge artifacts
        x0 = int(w * 0.2)
        x1 = int(w * 0.8)
        gap_region = strip_img[gap_top:gap_bot, x0:x1]
        if gap_region.size == 0:
            continue
        pixels = gap_region.reshape(-1, 3).astype(float)
        # Filter out very dark pixels (black background bleed)
        brightness = pixels.mean(axis=1)
        bright_pixels = pixels[brightness > 80]
        if len(bright_pixels) > 0:
            gap_pixels.append(bright_pixels)

    if not gap_pixels:
        # No usable gap pixels — return unity gains (no correction)
        return (1.0, 1.0, 1.0)

    all_gap_pixels = np.concatenate(gap_pixels, axis=0)
    # Median BGR of the white plastic backing
    median_bgr = np.median(all_gap_pixels, axis=0)

    # Target neutral white in BGR
    target = np.array([235.0, 235.0, 235.0])

    # Per-channel gain: target / measured (clamp to avoid division by zero)
    gains_bgr = np.where(median_bgr > 10, target / median_bgr, 1.0)

    # Clamp gains to a reasonable range to avoid extreme corrections
    gains_bgr = np.clip(gains_bgr, 0.5, 2.0)

    # Return as RGB gains
    return (float(gains_bgr[2]), float(gains_bgr[1]), float(gains_bgr[0]))


def apply_white_balance(color_rgb: RGB, gains_rgb: Tuple[float, float, float]) -> RGB:
    """
    Apply per-channel white balance gains to an RGB color.

    Parameters
    ----------
    color_rgb : (R, G, B) tuple
    gains_rgb : (gain_R, gain_G, gain_B) multiplicative gains

    Returns
    -------
    Corrected (R, G, B) tuple, clamped to [0, 255].
    """
    r = int(min(255, max(0, round(color_rgb[0] * gains_rgb[0]))))
    g = int(min(255, max(0, round(color_rgb[1] * gains_rgb[1]))))
    b = int(min(255, max(0, round(color_rgb[2] * gains_rgb[2]))))
    return (r, g, b)
