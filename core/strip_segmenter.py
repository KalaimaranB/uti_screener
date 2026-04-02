"""
core/strip_segmenter.py — Geometric detection of reagent pad boundaries.

Assumptions (stated explicitly):
  A1: The strip has exactly `num_boxes` pads (typically 10).
  A2: All pads have approximately equal height.
  A3: All gaps have approximately equal height.
  A4: Gap-to-pad ratio is between 0.30 and 0.80 (physical strip design).
  A5: Gap regions are significantly brighter than pad regions.
  A6: The pad+gap period ≈ strip_height / num_pads.

Algorithm:
  1. Compute column-averaged brightness profile (1D signal).
  2. Use derivative-based edge detection to find pad-gap transitions.
  3. If edge detection finds a clean periodic pattern, use it directly.
  4. Otherwise fall back to constrained grid search with enforced gap ratio.
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from typing import Optional, List, Tuple
from core.calibration import CalibrationModel


# ═══════════════════════════════════════════════════════════════════════
# Edge-based pad detection
# ═══════════════════════════════════════════════════════════════════════

def _detect_edges_1d(brightness: np.ndarray, num_pads: int) -> Optional[List[Tuple[int, int]]]:
    """
    Detect pad boundaries from a 1D brightness profile using edges.

    The brightness profile has peaks at gap regions (bright white plastic)
    and valleys at pad regions (colored reagent). We look for the periodic
    pattern of bright→dark→bright transitions.

    Returns list of (y_start, y_end) for each pad, or None if detection fails.
    """
    h = len(brightness)
    avg_period = h / num_pads

    # Smooth to suppress noise (sigma ~ 2-3 pixels)
    smooth = gaussian_filter1d(brightness.astype(float), sigma=2.5)

    # Compute derivative — positive = getting brighter, negative = getting darker
    deriv = np.gradient(smooth)

    # Expected pad height and gap height
    expected_pad = avg_period * 0.60
    expected_gap = avg_period * 0.40

    # Find peaks in brightness profile — these are gap centers
    # A gap center is where smooth brightness is locally maximal
    # We need num_pads - 1 internal gaps + optionally top/bottom margins

    # Strategy: threshold the brightness to classify each row as "gap" or "pad"
    # Gap pixels are brighter than the median + some offset
    median_bright = np.median(smooth)

    # Find the upper mode (gap brightness) — use 80th percentile of bright rows
    bright_threshold = np.percentile(smooth, 65)

    is_gap = smooth > bright_threshold

    # Find connected runs of gap=True
    gap_runs = _find_runs(is_gap, True)
    pad_runs = _find_runs(is_gap, False)

    # We expect at least num_pads pad runs and num_pads-1 gap runs
    # Filter out very tiny runs (noise)
    min_run = max(3, int(avg_period * 0.05))
    gap_runs = [(s, e) for s, e in gap_runs if (e - s) >= min_run]
    pad_runs = [(s, e) for s, e in pad_runs if (e - s) >= min_run]

    # If we have exactly num_pads pad runs, use them directly
    if len(pad_runs) == num_pads:
        # Validate: check that pad heights are reasonably uniform
        pad_heights = [e - s for s, e in pad_runs]
        mean_ph = np.mean(pad_heights)
        std_ph = np.std(pad_heights)
        cv = std_ph / mean_ph if mean_ph > 0 else 999

        if cv < 0.30:  # coefficient of variation < 30%
            # Also validate gap-to-pad ratio
            if len(gap_runs) >= num_pads - 1:
                gap_heights = [e - s for s, e in gap_runs[:num_pads]]
                mean_gh = np.mean(gap_heights)
                ratio = mean_gh / mean_ph if mean_ph > 0 else 0
                if 0.15 <= ratio <= 1.2:  # relaxed for edge detection
                    return pad_runs

    # If we have close to the right number, try to merge/split
    if num_pads - 2 <= len(pad_runs) <= num_pads + 2:
        # Try adjusting threshold
        for pct in [60, 70, 55, 75, 50]:
            threshold = np.percentile(smooth, pct)
            is_gap_adj = smooth > threshold
            pad_runs_adj = _find_runs(is_gap_adj, False)
            pad_runs_adj = [(s, e) for s, e in pad_runs_adj if (e - s) >= min_run]

            if len(pad_runs_adj) == num_pads:
                pad_heights = [e - s for s, e in pad_runs_adj]
                mean_ph = np.mean(pad_heights)
                std_ph = np.std(pad_heights)
                cv = std_ph / mean_ph if mean_ph > 0 else 999
                if cv < 0.35:
                    return pad_runs_adj

    return None  # Edge detection failed — fall back to grid search


def _find_runs(mask: np.ndarray, value: bool) -> List[Tuple[int, int]]:
    """Find contiguous runs of `value` in a boolean array. Returns [(start, end), ...]."""
    runs = []
    in_run = False
    start = 0
    for i in range(len(mask)):
        if mask[i] == value:
            if not in_run:
                start = i
                in_run = True
        else:
            if in_run:
                runs.append((start, i))
                in_run = False
    if in_run:
        runs.append((start, len(mask)))
    return runs


# ═══════════════════════════════════════════════════════════════════════
# Constrained grid search (fallback)
# ═══════════════════════════════════════════════════════════════════════

def _grid_search_constrained(
    strip_img: np.ndarray,
    num_boxes: int,
    cs_signal: np.ndarray,
    cs_bgr: np.ndarray,
    row_mean: np.ndarray,
    strip_bgr: np.ndarray,
    bright_thresh: float,
    first_bright_y: int,
    expected_colors_np: Optional[list],
) -> Tuple[int, int, int, bool]:
    """
    Constrained grid search over (pad_h, gap_h, y_offset).

    Scoring philosophy (in order of weight):
      1. PRIMARY: Calibration color match — how well does each candidate pad
         window's mean color match the expected calibration swatches for that
         analyte? This is the strongest signal because we know exactly what
         color each pad should be. Pads that are pastel/muted still have a
         specific expected color; white plastic gaps do not match any swatch.
      2. SECONDARY: Non-white reward — pads should be meaningfully different
         from the strip's white plastic. Reward pad windows that are colorful
         (far from white), penalize windows that look like white plastic.
      3. TERTIARY: Gap brightness — gap windows should be close to white plastic.
      4. SOFT ANCHOR: Quadratic penalty for offsets far from the detected
         first-pad position. Soft — color evidence can override it.
    """
    h = strip_img.shape[0]
    avg_period = h // num_boxes

    # --- Pad range: 45-75% of period ---
    pad_min = max(4, int(avg_period * 0.45))
    pad_max = int(avg_period * 0.75)

    # --- Gap range: 20-50% of period ---
    gap_min_floor = max(3, int(avg_period * 0.20))
    gap_max_ceil = int(avg_period * 0.50)

    expected_pad_ratio = 0.60

    # ── SOFT ANCHOR: find first brightness drop from top ──
    # Used only as a soft penalty — color evidence can override it.
    profile = row_mean.mean(axis=1)
    smooth_profile = gaussian_filter1d(profile, sigma=3.0)
    deriv = np.gradient(smooth_profile)
    neg_deriv = -deriv
    top_search = min(150, h)
    top_drops = neg_deriv[:top_search]
    drop_threshold = np.percentile(top_drops[top_drops > 0], 80) if np.any(top_drops > 0) else 1.0
    strong_drops = np.where(top_drops > drop_threshold)[0]
    first_pad_start_est = int(strong_drops[0]) if len(strong_drops) > 0 else 0

    best_score = -np.inf
    best_params = (pad_min, gap_min_floor, 0, False)

    pad_step = max(1, h // 800)
    gap_step = max(1, h // 800)

    for pad_h in range(pad_min, pad_max + 1, pad_step):
        gap_min_eff = max(gap_min_floor, int(pad_h * 0.30))
        gap_max_eff = min(gap_max_ceil, int(pad_h * 0.80))
        if gap_min_eff > gap_max_eff:
            continue

        for gap_h in range(gap_min_eff, gap_max_eff + 1, gap_step):
            period = pad_h + gap_h
            total_h = num_boxes * pad_h + (num_boxes - 1) * gap_h
            max_off = h - total_h
            if max_off < 0:
                continue

            offsets = np.arange(0, max_off + 1)

            # ── Precompute per-pad mean BGR colors for all offsets at once ──
            # pad_colors shape: (num_boxes, num_offsets, 3)
            all_starts = offsets[None, :] + np.arange(num_boxes)[:, None] * period  # (N, O)
            all_ends = np.minimum(all_starts + pad_h, h)                            # (N, O)
            pad_colors = (cs_bgr[all_ends] - cs_bgr[all_starts]) / max(pad_h, 1)   # (N, O, 3)

            # ── Gap colors ──
            gap_starts = all_ends[:-1]                                               # (N-1, O)
            gap_ends = np.minimum(gap_starts + gap_h, h)
            gap_lens = np.maximum(gap_ends - gap_starts, 1)
            gap_colors = (cs_bgr[gap_ends] - cs_bgr[gap_starts]) / gap_lens[..., None]  # (N-1, O, 3)

            # ══════════════════════════════════════════════════════════════
            # SCORE TERM 1 (PRIMARY): Calibration color match
            # For each pad i, compute minimum L2 distance from its mean color
            # to ANY of its calibration swatches (normal and flipped).
            # Lower total distance = better alignment.
            # Weight: 8.0 per unit of mean distance across all pads.
            # ══════════════════════════════════════════════════════════════
            color_score_normal = np.zeros(len(offsets), dtype=float)
            color_score_flipped = np.zeros(len(offsets), dtype=float)

            if expected_colors_np is not None:
                for i in range(num_boxes):
                    exp_colors = expected_colors_np[i]             # (S, 3) swatches for analyte i
                    exp_colors_f = expected_colors_np[num_boxes - 1 - i]

                    # pad_colors[i] shape: (O, 3)
                    # Broadcast: (O, 1, 3) - (1, S, 3) -> (O, S, 3) -> min over S
                    pc_n = pad_colors[i]                            # (O, 3)
                    dists_n = np.linalg.norm(
                        pc_n[:, None, :] - exp_colors[None, :, :], axis=2
                    ).min(axis=1)                                    # (O,)
                    color_score_normal += dists_n

                    pc_f = pad_colors[num_boxes - 1 - i]
                    dists_f = np.linalg.norm(
                        pc_f[:, None, :] - exp_colors_f[None, :, :], axis=2
                    ).min(axis=1)
                    color_score_flipped += dists_f

                color_score_normal /= num_boxes   # mean dist per pad
                color_score_flipped /= num_boxes

                # Convert distance to reward: lower dist = higher score
                score_normal  = -color_score_normal  * 8.0
                score_flipped = -color_score_flipped * 8.0
            else:
                # No calibration data — start at zero, rely on other terms
                score_normal  = np.zeros(len(offsets), dtype=float)
                score_flipped = np.zeros(len(offsets), dtype=float)

            # ══════════════════════════════════════════════════════════════
            # SCORE TERM 2 (SECONDARY): Non-white reward per pad
            # Pads should look like reagent pads, not white plastic.
            # Compute distance of each pad's color from strip_bgr (white plastic).
            # Mean across all pads, then reward.
            # ══════════════════════════════════════════════════════════════
            pad_dist_from_white = np.linalg.norm(
                pad_colors - strip_bgr[None, None, :], axis=2
            )  # (N, O)
            mean_pad_dist_from_white = pad_dist_from_white.mean(axis=0)  # (O,)

            # Reward pads that are colorful (far from white)
            score_normal  += mean_pad_dist_from_white * 3.0
            score_flipped += mean_pad_dist_from_white * 3.0

            # ══════════════════════════════════════════════════════════════
            # SCORE TERM 3 (TERTIARY): Gap brightness / proximity to white
            # Gaps should be bright white plastic.
            # ══════════════════════════════════════════════════════════════
            gap_brightness = gap_colors.mean(axis=2).mean(axis=0)  # (O,)
            score_normal  += np.clip(gap_brightness - bright_thresh, 0, 50) * 2.0
            score_flipped += np.clip(gap_brightness - bright_thresh, 0, 50) * 2.0

            gap_dist_to_white = np.linalg.norm(
                gap_colors - strip_bgr[None, None, :], axis=2
            ).mean(axis=0)  # (O,)
            score_normal  -= gap_dist_to_white * 1.5
            score_flipped -= gap_dist_to_white * 1.5

            # ══════════════════════════════════════════════════════════════
            # SCORE TERM 4 (SOFT ANCHOR): Offset proximity penalty
            # Soft quadratic penalty — color evidence can dominate over this.
            # ══════════════════════════════════════════════════════════════
            off_dist_ratio = np.abs(offsets - first_pad_start_est) / max(avg_period, 1)
            score_normal  -= (off_dist_ratio ** 2) * 80.0
            score_flipped -= (off_dist_ratio ** 2) * 80.0

            # ── Hard reject: template starts before first visible strip row ──
            invalid_start = offsets < (first_bright_y - 5)
            score_normal  = np.where(invalid_start, -1e9, score_normal)
            score_flipped = np.where(invalid_start, -1e9, score_flipped)

            # ── Hard reject: any pad window is pure black (off the strip) ──
            pad_brightness_check = pad_colors.mean(axis=2)  # (N, O)
            any_dark_pad = (pad_brightness_check < 20).any(axis=0)  # (O,)
            score_normal  = np.where(any_dark_pad, -1e9, score_normal)
            score_flipped = np.where(any_dark_pad, -1e9, score_flipped)

            # ── Pad size regularization (mild) ──
            pad_ratio = pad_h / period if period > 0 else 0.5
            pad_size_penalty = 4.0 * ((pad_ratio - expected_pad_ratio) ** 2) * avg_period
            score_normal  -= pad_size_penalty
            score_flipped -= pad_size_penalty

            best_n_i = int(score_normal.argmax())
            best_f_i = int(score_flipped.argmax())

            if score_normal[best_n_i] > best_score:
                best_score = float(score_normal[best_n_i])
                best_params = (pad_h, gap_h, int(offsets[best_n_i]), False)

            if score_flipped[best_f_i] > best_score:
                best_score = float(score_flipped[best_f_i])
                best_params = (pad_h, gap_h, int(offsets[best_f_i]), True)

    return best_params


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def refine_boundaries(
    strip_img: np.ndarray,
    num_boxes: int,
    template_cfg: Optional[dict] = None,
    model: Optional[CalibrationModel] = None,
    boxes_order: Optional[List[str]] = None,
) -> List[Tuple[int, int]]:
    """
    Fit a regular [pad, gap] × N mask to the strip image.

    Uses a two-stage approach:
      1. Edge-based detection from the 1D brightness profile
      2. Constrained grid search fallback with enforced gap ratios

    Returns list of (y_start, y_end) tuples for each pad.
    """
    h, w = strip_img.shape[:2]
    bgr = strip_img.astype(float)

    # ── 0. Dark background masking ──
    pixel_brightness = bgr.mean(axis=2)
    non_black_mask = pixel_brightness > 30

    row_sum = (bgr * non_black_mask[:, :, None]).sum(axis=1)
    row_count = non_black_mask.sum(axis=1)[:, None]

    row_mean = np.zeros((h, 3))
    valid_rows = row_count[:, 0] > 0
    row_mean[valid_rows] = row_sum[valid_rows] / row_count[valid_rows]
    row_mean[~valid_rows] = np.zeros(3)

    # ── Plastic baseline color (median of all valid pixels) ──
    valid_pixels = bgr[non_black_mask]
    if len(valid_pixels) > 0:
        strip_bgr = np.median(valid_pixels, axis=0)
    else:
        strip_bgr = np.array([240.0, 240.0, 240.0])

    # First non-black row
    row_brightness = row_mean.mean(axis=1)
    bright_rows = np.where(row_brightness > 40)[0]
    first_bright_y = bright_rows[0] if len(bright_rows) > 0 else 0

    # ── Check for manual overrides ──
    if template_cfg is not None:
        m_pad = template_cfg.get("manual_pad_h")
        m_gap = template_cfg.get("manual_gap_h")
        m_off = template_cfg.get("manual_y_offset")
        if all(v is not None for v in (m_pad, m_gap, m_off)):
            pad_h, gap_h, y_off = int(m_pad), int(m_gap), int(m_off)
            print(f"[INFO] Using MANUAL template match: pad_h={pad_h}px, "
                  f"gap_h={gap_h}px, y_offset={y_off}px")
            boundaries = []
            period = pad_h + gap_h
            for i in range(num_boxes):
                y0 = y_off + i * period
                y1 = min(y0 + pad_h, h)
                boundaries.append((y0, y1))
            return boundaries

    # ── Stage 1: Edge-based detection ──
    brightness_profile = row_mean.mean(axis=1)  # column-averaged brightness
    edge_result = _detect_edges_1d(brightness_profile, num_boxes)

    if edge_result is not None:
        pad_heights = [e - s for s, e in edge_result]
        mean_pad_h = int(np.mean(pad_heights))

        is_flipped = False
        dist_normal = 0.0
        dist_flipped = 0.0
        pad_colors_normal = []

        if model is not None and boxes_order is not None and len(boxes_order) == num_boxes:
            for i, (ys, ye) in enumerate(edge_result):
                pad_region = bgr[ys:ye, :, :]
                pad_rgb_mean = pad_region.mean(axis=(0, 1))
                pad_colors_normal.append(pad_rgb_mean)

            for i, analyte in enumerate(boxes_order):
                cal = model._analytes.get(analyte)
                if cal and cal.swatches:
                    exp_bgrs = np.array([[s.rgb[2], s.rgb[1], s.rgb[0]] for s in cal.swatches], dtype=float)
                    pc_n = np.array(pad_colors_normal[i])
                    dist_normal += np.linalg.norm(pc_n[None, :] - exp_bgrs, axis=1).min()
                    pc_f = np.array(pad_colors_normal[num_boxes - 1 - i])
                    dist_flipped += np.linalg.norm(pc_f[None, :] - exp_bgrs, axis=1).min()

            if dist_flipped < dist_normal:
                is_flipped = True

            # ── Quality gate: reject if color match is too poor ──
            # If mean per-pad distance to calibration swatches is large,
            # the template is probably sitting on gaps instead of pads.
            mean_dist = min(dist_normal, dist_flipped) / max(num_boxes, 1)
            if mean_dist > 60.0:
                print(
                    f"[INFO] Edge result rejected (mean color dist={mean_dist:.1f} > 60) "
                    f"— falling back to grid search."
                )
                edge_result = None

    if edge_result is not None:
        gaps = []
        for i in range(len(edge_result) - 1):
            gaps.append(edge_result[i + 1][0] - edge_result[i][1])
        mean_gap_h = int(np.mean(gaps)) if gaps else 0
        y_off = edge_result[0][0]
        orientation_str = "Flipped" if is_flipped else "Normal"
        print(
            f"[INFO] Edge detection: pad_h≈{mean_pad_h}px, gap_h≈{mean_gap_h}px, "
            f"y_offset={y_off}px, orientation={orientation_str}"
        )
        if is_flipped:
            edge_result = edge_result[::-1]
        return edge_result

    # ── Stage 2: Constrained grid search fallback ──
    print("[INFO] Edge detection inconclusive — falling back to constrained grid search.")

    # Build cumulative sums for grid search
    row_signal = row_mean.max(axis=1) - row_mean.min(axis=1)
    row_signal[~valid_rows] = 0.0
    cs_signal = np.concatenate([[0], np.cumsum(row_signal)])
    cs_bgr = np.concatenate([np.zeros((1, 3)), np.cumsum(row_mean, axis=0)])

    # Bright threshold for gap brightness reward
    bright_thresh = np.percentile(brightness_profile[brightness_profile > 40], 60) if np.sum(brightness_profile > 40) > 10 else 150.0

    # Expected colors for orientation detection
    expected_colors_np = None
    if model is not None and boxes_order is not None and len(boxes_order) == num_boxes:
        expected_colors_list = []
        for analyte in boxes_order:
            analyte_cal = model._analytes.get(analyte)
            if analyte_cal and analyte_cal.swatches:
                bgrs = [[s.rgb[2], s.rgb[1], s.rgb[0]] for s in analyte_cal.swatches]
            else:
                bgrs = [[200, 200, 200]]
            expected_colors_list.append(np.array(bgrs, dtype=float))
        expected_colors_np = expected_colors_list

    pad_h, gap_h, y_off, is_flipped = _grid_search_constrained(
        strip_img, num_boxes,
        cs_signal, cs_bgr, row_mean, strip_bgr, bright_thresh,
        first_bright_y, expected_colors_np,
    )

    period = pad_h + gap_h
    orientation_str = "Flipped" if is_flipped else "Normal"
    print(
        f"[INFO] Template match: pad_h={pad_h}px, gap_h={gap_h}px, "
        f"y_offset={y_off}px, orientation={orientation_str}"
    )

    boundaries: list[tuple[int, int]] = []
    for i in range(num_boxes):
        y0 = y_off + i * period
        y1 = min(y0 + pad_h, h)
        boundaries.append((y0, y1))

    if is_flipped:
        boundaries = boundaries[::-1]

    return boundaries


def segment_boxes(
    strip_img: np.ndarray,
    num_boxes: int,
    template_cfg: Optional[dict] = None,
    model: Optional[CalibrationModel] = None,
    boxes_order: Optional[List[str]] = None,
) -> Tuple[List[np.ndarray], List[Tuple[int, int]]]:
    """
    Divide the strip image into *num_boxes* using refined geometric detection.
    Returns:
        (box_images, boundaries)
    """
    h, w = strip_img.shape[:2]
    refined = refine_boundaries(strip_img, num_boxes, template_cfg, model, boxes_order)

    boxes: List[np.ndarray] = []
    for y_start, y_end in refined:
        boxes.append(strip_img[y_start:y_end, :])
    return boxes, refined