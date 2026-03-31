import numpy as np
from typing import Optional, List, Tuple
from core.calibration import CalibrationModel

def refine_boundaries(
    strip_img: np.ndarray,
    num_boxes: int,
    template_cfg: Optional[dict] = None,
    model: Optional[CalibrationModel] = None,
    boxes_order: Optional[List[str]] = None,
) -> List[Tuple[int, int]]:
    """
    Fit a regular [pad, gap] × N mask to the row-wise colour signal.

    Physical constraints encoded
    ----------------------------
    * All pads are the **same height** (pad_h).
    * All gaps between pads are the **same height** (gap_h ≥ 0).
    * There may be an arbitrary top margin (y_offset) before the first pad.
    * Bottom margin = whatever is left over — no assumption needed.

    Algorithm
    ---------
    1.  Compute per-row BGR deviation from the estimated strip background.
    2.  Grid-search over (pad_h, gap_h) with y_offset vectorised via a
        pre-computed cumulative sum for O(1) window scoring.
    3.  Pick the (pad_h, gap_h, y_offset) triple that maximises the mean
        deviation inside the 10 pad windows.
    4.  Return the 10 pad (y_start, y_end) tuples directly.
    """
    h, w = strip_img.shape[:2]
    bgr  = strip_img.astype(float)
    
    # ── 0. Dark Background Masking ──────────────────────────────
    # Ignore black background pixels (e.g. brightness < 30) across each row, 
    # so tilted strips don't get diluted by black canvas edges.
    pixel_brightness = bgr.mean(axis=2) # (h, w)
    non_black_mask = pixel_brightness > 30 # (h, w)
    
    row_sum = (bgr * non_black_mask[:, :, None]).sum(axis=1) # (h, 3)
    row_count = non_black_mask.sum(axis=1)[:, None] # (h, 1)
    
    row_mean = np.zeros((h, 3))
    valid_rows = row_count[:, 0] > 0
    row_mean[valid_rows] = row_sum[valid_rows] / row_count[valid_rows]

    # ── NEW: Plastic Baseline Color ─────────────────────────────
    # Identify the most common background color (the physical white plastic backing)
    valid_pixels = bgr[non_black_mask]
    if len(valid_pixels) > 0:
        strip_bgr = np.median(valid_pixels, axis=0) # (3,)
    else:
        strip_bgr = np.array([240.0, 240.0, 240.0]) # fallback to dirty white
        
    # Keep invalid rows physically black so they trigger the "Fell-Off-Strip" penalty!
    row_mean[~valid_rows] = np.zeros(3)

    # ── 0. Dark Background Rejection Heuristics ─────────────────────
    # Identify the first non-black row of the strip body (e.g. threshold > 40 on average RGB)
    row_brightness = row_mean.mean(axis=1)
    bright_rows = np.where(row_brightness > 40)[0]
    first_bright_y = bright_rows[0] if len(bright_rows) > 0 else 0

    # ── 2. Cumulative sum of BGR for fast colour-diversity queries ──
    # cs_bgr[y] is the sum of all rows before y. Shape: (h+1, 3)
    cs_bgr = np.concatenate([np.zeros((1, 3)), np.cumsum(row_mean, axis=0)])

    # ── 2a. Saturation Signal (The Ultimate Classifier) ──
    # Reagent pads contain industrial chemical dyes (high saturation / RGB channel variance).
    # Backgrounds, zippers, and shadows are all achromatic greys/blacks/whites.
    # By defining the "Signal" purely as saturation, the geometry mathematically goes blind to 
    # all shadows and zippers!
    row_signal = row_mean.max(axis=1) - row_mean.min(axis=1) # (h,)
    row_signal[~valid_rows] = 0.0 # Force pure void to 0 saturation
    
    # Cumulative signal allows O(1) integral sweeps
    cs_signal = np.concatenate([[0], np.cumsum(row_signal)])

    # ── 3. Chemical Swatch Baseline Expectations ──────────────────────
    expected_colors_np = None
    if model is not None and boxes_order is not None and len(boxes_order) == num_boxes:
        expected_colors_list = []
        for analyte in boxes_order:
            analyte_cal = model._analytes.get(analyte)
            if analyte_cal and analyte_cal.swatches:
                # model.json holds RGB, cv2 works in BGR natively
                bgrs = [[s.rgb[2], s.rgb[1], s.rgb[0]] for s in analyte_cal.swatches]
            else:
                bgrs = [[200, 200, 200]]  # generic fallback
            expected_colors_list.append(np.array(bgrs, dtype=float))
        expected_colors_np = expected_colors_list # length 10 array list

    # ── 4. Check for manual overrides ───────────────────────────────────
    if template_cfg is not None:
        m_pad = template_cfg.get("manual_pad_h")
        m_gap = template_cfg.get("manual_gap_h")
        m_off = template_cfg.get("manual_y_offset")
        if all(v is not None for v in (m_pad, m_gap, m_off)):
            pad_h, gap_h, y_off = int(m_pad), int(m_gap), int(m_off)
            print(f"[INFO] Using MANUAL template match: pad_h={pad_h}px, "
                  f"gap_h={gap_h}px, y_offset={y_off}px")
            boundaries: list[tuple[int, int]] = []
            period = pad_h + gap_h
            for i in range(num_boxes):
                y0 = y_off + i * period
                y1 = min(y0 + pad_h, h)
                boundaries.append((y0, y1))
            return boundaries

    # ── 4. Grid search over (pad_h, gap_h) ───────────────────────────
    # Pad height: typically takes up about 60-80% of the period.
    # So period = h / num_boxes roughly.
    avg_period = h // num_boxes
    pad_min    = int(avg_period * 0.15)
    pad_max    = int(avg_period * 0.90)
    
    gap_min    = int(avg_period * 0.05)
    gap_max    = int(avg_period * 0.85)

    best_score  = -np.inf
    best_params = (pad_min, gap_min, 0, False)

    # Step sizes: search fully for small images, stride for large ones
    pad_step = max(1, h // 800)
    gap_step = max(1, h // 800)

    for pad_h in range(pad_min, pad_max + 1, pad_step):
        for gap_h in range(gap_min, gap_max + 1, gap_step):
            period   = pad_h + gap_h
            total_h  = num_boxes * pad_h + (num_boxes - 1) * gap_h
            max_off  = h - total_h
            if max_off < 0:
                continue

            # Vectorise over all valid offsets
            offsets  = np.arange(0, max_off + 1)           # (n_off,)
            score    = np.zeros(len(offsets), dtype=float)

            # pre-calculate dimensions
            all_starts = offsets[None, :] + np.arange(num_boxes)[:, None] * period # (10, n_off)
            all_ends = np.minimum(all_starts + pad_h, h)

            # ── 1. Saturation Geometric Resonance ──
            # Accurately slice the image into bounding boxes based ONLY on Dye locations!
            pad_signal_sum = cs_signal[all_ends] - cs_signal[all_starts] # (num_boxes, len(offsets))
            pad_signal_mean = pad_signal_sum.mean(axis=0) / pad_h # (len(offsets),)
            
            if gap_h > 0:
                gap_starts = all_ends[:-1]
                gap_ends = np.minimum(gap_starts + gap_h, h)
                
                gap_signal_sum = cs_signal[gap_ends] - cs_signal[gap_starts] 
                gap_lens = np.maximum(gap_ends - gap_starts, 1) 
                gap_signal_mean = (gap_signal_sum / gap_lens).mean(axis=0)
            else:
                gap_signal_mean = np.zeros_like(pad_signal_mean)
            
            # The Golden Law: Maximize Pad Dye, strictly minimize Gap Dye!
            geo_score = (pad_signal_mean - gap_signal_mean * 2.0)
            score = geo_score * 50.0  # Safe geometry baseline score

            # pad_colors shape: (num_boxes, len(offsets), 3) BGR
            pad_colors = (cs_bgr[all_ends] - cs_bgr[all_starts]) / pad_h
            
            # ── 2. Inter-Pad Diversity Tie-Breaker ──
            # Gently reward templates that hit totally different colors overall
            diversity = pad_colors.std(axis=0).mean(axis=1) # (len(offsets),)
            score += diversity * 5.0
            
            score_normal = score.copy()
            score_flipped = score.copy()

            # ── 3. Gap White Plastic Matching ──
            if gap_h > 0:
                # gap_colors shape: (num_boxes - 1, len(offsets), 3)
                gap_colors = (cs_bgr[gap_ends] - cs_bgr[gap_starts]) / gap_lens[..., None]
                # average euclidean distance across the num_boxes-1 gaps for each offset
                gap_dist_to_white = np.linalg.norm(gap_colors - strip_bgr, axis=2).mean(axis=0)
                # Penalize based on distance to background plastic
                score_normal -= gap_dist_to_white * 1.5
                score_flipped -= gap_dist_to_white * 1.5

            # ── 4. Expected Color Constraints & Inverted Detection ──
            if expected_colors_np is not None:
                color_dist_normal = np.zeros(len(offsets), dtype=float)
                color_dist_flipped = np.zeros(len(offsets), dtype=float)
                
                for i in range(num_boxes):
                    exp_colors = expected_colors_np[i] # shape (N_swatches, 3) BGR
                    
                    # Pad i (Normal) mapped to expected box i
                    p_colors_i = pad_colors[i] # shape (len(offsets), 3) BGR
                    dists_n = np.linalg.norm(p_colors_i[:, None, :] - exp_colors[None, :, :], axis=2)
                    color_dist_normal += dists_n.min(axis=1)
                    
                    # Pad (num_boxes - 1 - i) (Flipped) mapped to expected box i
                    p_colors_flipped_i = pad_colors[num_boxes - 1 - i]
                    dists_f = np.linalg.norm(p_colors_flipped_i[:, None, :] - exp_colors[None, :, :], axis=2)
                    color_dist_flipped += dists_f.min(axis=1)
                    
                color_dist_normal /= num_boxes
                color_dist_flipped /= num_boxes
                
                score_normal -= color_dist_normal * 2.0
                score_flipped -= color_dist_flipped * 2.0

            # ── 5. Mask Overrides ──
            # If ANY pad drops into the total void, kill it entirely.
            pad_brightness = pad_colors.mean(axis=2)
            any_dark_pad = (pad_brightness < 20).any(axis=0)
            score_normal -= np.where(any_dark_pad, 10000.0, 0.0)
            score_flipped -= np.where(any_dark_pad, 10000.0, 0.0)
            
            invalid_start = offsets < (first_bright_y - 5)
            score_normal -= np.where(invalid_start, 10000.0, 0.0)
            score_flipped -= np.where(invalid_start, 10000.0, 0.0)

            best_n_i = int(score_normal.argmax())
            best_f_i = int(score_flipped.argmax())
            
            if score_normal[best_n_i] > best_score:
                best_score = float(score_normal[best_n_i])
                best_params = (pad_h, gap_h, int(offsets[best_n_i]), False)
                
            if score_flipped[best_f_i] > best_score:
                best_score = float(score_flipped[best_f_i])
                best_params = (pad_h, gap_h, int(offsets[best_f_i]), True)

    pad_h, gap_h, y_off, is_flipped = best_params
    period = pad_h + gap_h
    orientation_str = "Flipped" if is_flipped else "Normal"
    print(
        f"[INFO] Template match: pad_h={pad_h}px, gap_h={gap_h}px, "
        f"y_offset={y_off}px, edge_score={best_score:.2f}, orientation={orientation_str}"
    )

    # ── 6. Build boundary list ────────────────────────────────────────
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
