"""
core/strip_analyzer.py — Detects the strip ROI, segments boxes, and reads colours.

Design (SRP):
  StripAnalyzer is responsible only for image processing steps:
    1. Crop the strip from the full CV-output image.
    2. Segment the strip into individual reagent-pad boxes.
    3. Sample colour from each box.
  It delegates concentration lookup to CalibrationModel.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import cv2
import numpy as np

from .calibration import CalibrationModel
from .color_utils import RGB


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class BoxResult:
    """Analysis result for one reagent pad."""
    analyte: str
    color_rgb: RGB
    value: Union[float, str]
    unit: str
    confidence: float
    box_image: np.ndarray = field(repr=False, default=None)  # type: ignore


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class StripAnalyzer:
    """
    Processes a CV-output image to extract per-box concentrations.

    Usage::

        analyzer = StripAnalyzer()
        results  = analyzer.analyze(image_path, model, strip_config_path)
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(
        self,
        image_path: str | Path,
        model: CalibrationModel,
        strip_config_path: str | Path,
        pre_cropped: bool | None = None,
        manual_pad_h: int | None = None,
        manual_gap_h: int | None = None,
        manual_y_offset: int | None = None,
    ) -> dict[str, BoxResult]:
        """
        Full pipeline: load image → crop strip → segment boxes → predict.

        Parameters
        ----------
        image_path:
            Path to the CV-system output image.
        model:
            A loaded/built CalibrationModel.
        strip_config_path:
            Path to ``strip_config.json``.

        Returns
        -------
        dict mapping analyte key → BoxResult
        """
        image_path = Path(image_path)
        cfg = self._parse_config(
            strip_config_path,
            pre_cropped=pre_cropped,
            manual_pad_h=manual_pad_h,
            manual_gap_h=manual_gap_h,
            manual_y_offset=manual_y_offset,
        )

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        # Step 1: Crop the detected strip (skip if already cropped)
        if is_pre_cropped:
            strip_img = img_bgr
            print("[INFO] pre_cropped=true — using full image as strip.")
        else:
            strip_img = self.crop_strip(img_bgr, detection_cfg)

        # Step 2: Segment into boxes
        template_cfg = cfg.get("template_mask", {})
        box_images = self.segment_boxes(strip_img, len(boxes_order), template_cfg, model, boxes_order)

        # Step 3: Sample colour + predict concentration
        results: dict[str, BoxResult] = {}
        for analyte, box_img in zip(boxes_order, box_images):
            color_rgb = self.sample_box_color(box_img)
            value, unit, confidence = model.get_concentration(analyte, color_rgb)
            results[analyte] = BoxResult(
                analyte=analyte,
                color_rgb=color_rgb,
                value=value,
                unit=unit,
                confidence=confidence,
                box_image=box_img,
            )
        return results

    # ------------------------------------------------------------------
    # Config parser
    # ------------------------------------------------------------------

    def _parse_config(
        self,
        strip_config_path: str | Path,
        pre_cropped: bool | None = None,
        manual_pad_h: int | None = None,
        manual_gap_h: int | None = None,
        manual_y_offset: int | None = None,
    ) -> dict:
        """Load JSON config and apply any explicit kwargs as overrides."""
        with open(strip_config_path, "r") as f:
            cfg = json.load(f)

        if pre_cropped is not None:
            cfg["pre_cropped"] = pre_cropped

        if any(v is not None for v in (manual_pad_h, manual_gap_h, manual_y_offset)):
            if "template_mask" not in cfg:
                cfg["template_mask"] = {}
            if manual_pad_h is not None:
                cfg["template_mask"]["manual_pad_h"] = manual_pad_h
            if manual_gap_h is not None:
                cfg["template_mask"]["manual_gap_h"] = manual_gap_h
            if manual_y_offset is not None:
                cfg["template_mask"]["manual_y_offset"] = manual_y_offset

        return cfg

    # ------------------------------------------------------------------
    # Step 1 — Strip cropping
    # ------------------------------------------------------------------

    def crop_strip(
        self,
        img_bgr: np.ndarray,
        detection_cfg: dict,
    ) -> np.ndarray:
        """
        Detect and crop the bounding box of the strip.

        Strategy
        --------
        Convert to HSV, threshold on the border colour (default: magenta),
        find the largest contour, return its bounding-rect crop.

        If no border is found, falls back to returning the full image
        (useful for pre-cropped inputs).
        """
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

        lower = np.array(detection_cfg.get("hsv_lower", [130, 80, 80]), dtype=np.uint8)
        upper = np.array(detection_cfg.get("hsv_upper", [170, 255, 255]), dtype=np.uint8)

        mask = cv2.inRange(hsv, lower, upper)

        # Morphological clean-up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print(
                "[WARNING] No border contour detected — using full image as strip. "
                "Check strip_config.json hsv_lower/hsv_upper values."
            )
            return img_bgr

        # Pick the tallest (most vertical) contour as the strip
        best = max(contours, key=lambda c: cv2.boundingRect(c)[3])
        x, y, w, h = cv2.boundingRect(best)

        # Add a small inset to avoid the border pixels themselves
        inset = 4
        x, y = x + inset, y + inset
        w, h = w - 2 * inset, h - 2 * inset

        cropped = img_bgr[y : y + h, x : x + w]
        print(f"[INFO] Strip cropped to ({w}×{h}) at ({x},{y})")
        return cropped

    # ------------------------------------------------------------------
    # Step 2 — Box segmentation
    # ------------------------------------------------------------------

    def segment_boxes(
        self,
        strip_img: np.ndarray,
        num_boxes: int,
        template_cfg: dict | None = None,
        model: CalibrationModel | None = None,
        boxes_order: list[str] | None = None,
    ) -> list[np.ndarray]:
        """
        Divide the strip image into *num_boxes* equal-height horizontal slices.

        Also attempts to refine using detected colour-change boundaries if they
        produce a more consistent segmentation. Falls back to uniform split.
        """
        h, w = strip_img.shape[:2]
        refined = self._refine_boundaries(strip_img, num_boxes, template_cfg, model, boxes_order)

        boxes: list[np.ndarray] = []
        for y_start, y_end in refined:
            boxes.append(strip_img[y_start:y_end, :])
        return boxes

    def _refine_boundaries(
        self,
        strip_img: np.ndarray,
        num_boxes: int,
        template_cfg: dict | None = None,
        model: CalibrationModel | None = None,
        boxes_order: list[str] | None = None,
    ) -> list[tuple[int, int]]:
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
        from scipy.signal import savgol_filter

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

        # ── 2a. Signal Divergence Math (Distance from Baseline Plastic) ──
        # Calculate how much each row physically diverges from the mathematical plain plastic.
        # This acts as our ultimate geometric boundary engine.
        row_signal = np.linalg.norm(row_mean - strip_bgr, axis=1) # (h,)
        
        # Absolute void spaces should NOT trigger high divergence (as if they were colorful pads).
        row_signal[~valid_rows] = 0.0
        
        # Cumulative signal allows O(1) integral sweeps across any bounding variation
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
        best_params = (pad_min, gap_min, 0)

        # Step sizes: search fully for small images, stride for large ones
        pad_step = 1
        gap_step = 1

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

                # ── 1. Geometric Signal Resonance (NEW) ──
                # sum of signal exactly inside the predicted pads
                pad_signal_sum = cs_signal[all_ends] - cs_signal[all_starts] # (num_boxes, len(offsets))
                pad_signal_mean = pad_signal_sum.mean(axis=0) / pad_h # (len(offsets),)
                
                # sum of signal exactly inside the predicted gaps
                if gap_h > 0:
                    gap_starts = all_ends[:-1] # First 9 boxes gap starts (num_boxes-1, len(offsets))
                    gap_ends = np.minimum(gap_starts + gap_h, h)
                    
                    gap_signal_sum = cs_signal[gap_ends] - cs_signal[gap_starts]
                    # By maintaining a strict minimum length, we guarantee we aren't dividing by zero
                    gap_lens = np.maximum(gap_ends - gap_starts, 1) 
                    gap_signal_mean = (gap_signal_sum / gap_lens).mean(axis=0)
                else:
                    gap_signal_mean = np.zeros_like(pad_signal_mean)
                
                # The Physical Wall: Maximize average divergence inside pads (Colorful), 
                # strictly subtract average divergence inside gaps (Masking Plastic).
                geo_score = (pad_signal_mean - gap_signal_mean * 2.0)
                score += geo_score * 50.0  # Massive scaling factor overriding tiny ghost edges

                # ── 2. Vectorised Inter-Pad Colour Diversity ──
                # pad_colors shape: (num_boxes, len(offsets), 3) BGR
                pad_colors = (cs_bgr[all_ends] - cs_bgr[all_starts]) / pad_h
                
                # std over the 10 boxes, then average the 3 RGB channels -> shape: (len(offsets),)
                diversity = pad_colors.std(axis=0).mean(axis=1)

                # Add diversity bonus to ensure boxes physically hit 10 different colored pads
                score += diversity * 5.0
                
                # ── 6. Bi-Directional Chemical Swatch Alignment ──
                if expected_colors_np is not None:
                    penalty_norm = 0.0
                    penalty_flip = 0.0
                    n_analyte = len(expected_colors_np)
                    for i in range(n_analyte):
                        # Norm direction (pad i -> expected i)
                        diff_norm = pad_colors[i][:, None, :] - expected_colors_np[i][None, :, :]
                        penalty_norm += np.linalg.norm(diff_norm, axis=2).min(axis=1)
                        
                        # Flipped inverse direction (pad i -> expected n-1-i)
                        flip_idx = n_analyte - 1 - i
                        diff_flip = pad_colors[i][:, None, :] - expected_colors_np[flip_idx][None, :, :]
                        penalty_flip += np.linalg.norm(diff_flip, axis=2).min(axis=1)
                    
                    # Accept whichever configuration returns the lowest mapping penalty
                    chemical_penalty = np.minimum(penalty_norm, penalty_flip) / num_boxes
                    # Subtract heavily to intensely penalise iterations aligning inside generic textures
                    score -= chemical_penalty * 3.0

                # ── 7. Black Background Penalty & White Alignment Reward ──
                # pad_colors shape: (num_boxes, len(offsets), 3) -> average across rgb -> (num_boxes, len(offsets))
                pad_brightness = pad_colors.mean(axis=2)
                
                # Rows purely in the black background average to exactly 0.0 due to the `> 30` ignore mask.
                # If ANY pad is exactly 0 (or < 5 to account for floating point), it fell off the strip. Severely penalize!
                any_dark_pad = (pad_brightness < 5).any(axis=0)
                score += np.where(any_dark_pad, -10000.0, 0.0)
                
                # Further penalize configurations where the first box starts before the defined white strip
                # giving it a small margin (e.g., 5px) to account for thresholding noise
                invalid_start = offsets < (first_bright_y - 5)
                score += np.where(invalid_start, -10000.0, 0.0)
                
                # Add a gentle reward for templates that naturally originate near the first bright (white strip) pixel
                # to anchor the template against drifting into the background.
                alignment_reward = -0.5 * np.abs(offsets - first_bright_y)
                score += alignment_reward

                best_i = int(score.argmax())
                if score[best_i] > best_score:
                    best_score  = float(score[best_i])
                    best_params = (pad_h, gap_h, int(offsets[best_i]))

        pad_h, gap_h, y_off = best_params
        period = pad_h + gap_h
        print(
            f"[INFO] Template match: pad_h={pad_h}px, gap_h={gap_h}px, "
            f"y_offset={y_off}px, edge_score={best_score:.2f}"
        )

        # ── 4. Build boundary list ────────────────────────────────────────
        boundaries: list[tuple[int, int]] = []
        for i in range(num_boxes):
            y0 = y_off + i * period
            y1 = min(y0 + pad_h, h)
            boundaries.append((y0, y1))

        return boundaries

    # ------------------------------------------------------------------
    # Step 3 — Colour sampling
    # ------------------------------------------------------------------

    def sample_box_color(self, box_img: np.ndarray) -> RGB:
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

    # ------------------------------------------------------------------
    # Debug visualisation
    # ------------------------------------------------------------------

    def generate_debug_image(
        self,
        strip_img: np.ndarray,
        results: dict,                       # dict[str, BoxResult]
        boundaries: list[tuple[int, int]],
    ) -> np.ndarray:
        """
        Draw annotated box boundaries, sampled colours, analyte names, values,
        and confidence scores onto a copy of the strip image.

        Parameters
        ----------
        strip_img:
            The (possibly pre-cropped) BGR strip image.
        results:
            The dict[analyte → BoxResult] returned by ``analyze()``.
        boundaries:
            List of (y_start, y_end) tuples for each box — one per analyte.

        Returns
        -------
        Annotated BGR image (same dimensions as strip_img).
        """
        out = strip_img.copy()
        h, w = out.shape[:2]

        # Expand strip horizontally to make room for text annotation
        annotation_w = max(400, w + 320)
        canvas = np.full((h, annotation_w, 3), 245, dtype=np.uint8)  # off-white
        canvas[:, :w] = out

        font = cv2.FONT_HERSHEY_SIMPLEX
        analytes = list(results.keys())

        for idx, ((y0, y1), analyte) in enumerate(zip(boundaries, analytes)):
            res = results[analyte]

            # --- Draw box outline on strip ---
            color_line = (30, 200, 30)  # green
            cv2.rectangle(canvas, (0, y0), (w - 1, y1 - 1), color_line, 2)

            # --- Draw 75% internal sampling region outline ---
            box_h = y1 - y0
            s_y0 = y0 + int(box_h * 0.125)
            s_y1 = y0 + int(box_h * 0.875)
            s_x0 = int(w * 0.125)
            s_x1 = int(w * 0.875)
            cv2.rectangle(canvas, (s_x0, s_y0), (s_x1, s_y1), (0, 0, 255), 1)  # red

            # --- Sampled colour swatch (small filled rectangle) ---
            swatch_x0 = w + 10
            swatch_x1 = w + 40
            swatch_y0 = y0 + 4
            swatch_y1 = max(swatch_y0 + 4, y1 - 4)
            r, g, b = res.color_rgb
            cv2.rectangle(
                canvas,
                (swatch_x0, swatch_y0),
                (swatch_x1, swatch_y1),
                (int(b), int(g), int(r)),    # OpenCV is BGR
                -1,
            )
            cv2.rectangle(
                canvas,
                (swatch_x0, swatch_y0),
                (swatch_x1, swatch_y1),
                (80, 80, 80),
                1,
            )

            # --- Text label ---
            conf_pct = f"{res.confidence * 100:.0f}%"
            val_str = (
                f"{res.value:.3g}" if isinstance(res.value, float) else str(res.value)
            )
            label = f"{analyte}: {val_str} {res.unit}  ({conf_pct})"
            text_y = (y0 + y1) // 2 + 5
            font_scale = max(0.35, min(0.5, (y1 - y0) / 60))
            cv2.putText(
                canvas,
                label,
                (swatch_x1 + 8, text_y),
                font,
                font_scale,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )

            # --- Row index tag inside the strip ---
            cv2.putText(
                canvas,
                str(idx + 1),
                (4, y0 + 16),
                font,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Title bar
        cv2.putText(
            canvas,
            "Urinalysis Strip - Debug View",
            (w + 10, 18),
            font,
            0.55,
            (50, 50, 200),
            1,
            cv2.LINE_AA,
        )

        return canvas

    def analyze_with_debug(
        self,
        image_path,
        model,
        strip_config_path,
        debug_output_path: str = "debug_output.png",
        pre_cropped: bool | None = None,
        manual_pad_h: int | None = None,
        manual_gap_h: int | None = None,
        manual_y_offset: int | None = None,
    ) -> dict:
        """
        Run ``analyze()`` and additionally save an annotated debug image.

        Parameters
        ----------
        image_path, model, strip_config_path:
            Same as ``analyze()``.
        debug_output_path:
            Where to save the debug PNG.

        Returns
        -------
        Same dict[str, BoxResult] as ``analyze()``.
        """
        import json as _json
        from pathlib import Path as _Path

        image_path = _Path(image_path)
        cfg = self._parse_config(
            strip_config_path,
            pre_cropped=pre_cropped,
            manual_pad_h=manual_pad_h,
            manual_gap_h=manual_gap_h,
            manual_y_offset=manual_y_offset,
        )

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        strip_img = img_bgr if is_pre_cropped else self.crop_strip(img_bgr, detection_cfg)
        template_cfg = cfg.get("template_mask", {})
        boundaries = self._refine_boundaries(strip_img, len(boxes_order), template_cfg, model, boxes_order)
        box_images = [strip_img[y0:y1, :] for y0, y1 in boundaries]

        results: dict = {}
        for analyte, box_img in zip(boxes_order, box_images):
            color_rgb = self.sample_box_color(box_img)
            value, unit, confidence = model.get_concentration(analyte, color_rgb)
            results[analyte] = BoxResult(
                analyte=analyte,
                color_rgb=color_rgb,
                value=value,
                unit=unit,
                confidence=confidence,
                box_image=box_img,
            )

        debug_img = self.generate_debug_image(strip_img, results, boundaries)
        cv2.imwrite(debug_output_path, debug_img)
        print(f"[DEBUG] Annotated image saved to: {debug_output_path}")

        return results

