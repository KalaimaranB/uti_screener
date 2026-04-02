import cv2
import numpy as np
from pathlib import Path
from typing import Optional

from .calibration import CalibrationModel
from .models import BoxResult
from .config_parser import parse_strip_config
from .strip_cropper import crop_strip
from .strip_segmenter import segment_boxes, refine_boundaries
from .color_sampler import sample_box_color, white_balance_from_plastic, apply_white_balance
from .debug_renderer import generate_debug_image

class StripAnalyzer:
    """
    Processes a CV-output image to extract per-box concentrations.
    This class acts as a coordinator (Facade) delegating to specialized modules.
    """

    def _calibrate_from_negative(
        self,
        negative_image_path: str | Path,
        model: CalibrationModel,
        strip_config_path: str | Path,
        pre_cropped: bool | None = None,
    ) -> None:
        """
        Process a negative reference strip image and set the per-analyte
        baseline correction on the calibration model.
        """
        negative_image_path = Path(negative_image_path)
        cfg = parse_strip_config(strip_config_path, pre_cropped=pre_cropped)

        neg_bgr = cv2.imread(str(negative_image_path))
        if neg_bgr is None:
            print(f"[WARNING] Could not read negative reference: {negative_image_path}")
            return

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        neg_strip = neg_bgr if is_pre_cropped else crop_strip(neg_bgr, detection_cfg)
        template_cfg = cfg.get("template_mask", {})

        boundaries = refine_boundaries(neg_strip, len(boxes_order), template_cfg, model, boxes_order)
        neg_boxes = [neg_strip[y0:y1, :] for y0, y1 in boundaries]

        # Sample colors from each pad of the negative strip
        measured_negatives = {}
        for analyte, box_img in zip(boxes_order, neg_boxes):
            rgb = sample_box_color(box_img)
            measured_negatives[analyte] = rgb

        model.set_negative_baseline(measured_negatives)
        print(f"[INFO] Negative calibration complete from: {negative_image_path.name}")

    def analyze(
        self,
        image_path: str | Path,
        model: CalibrationModel,
        strip_config_path: str | Path,
        pre_cropped: bool | None = None,
        manual_pad_h: int | None = None,
        manual_gap_h: int | None = None,
        manual_y_offset: int | None = None,
        negative_image_path: Optional[str | Path] = None,
    ) -> dict[str, BoxResult]:
        """Full pipeline: load image → crop strip → segment boxes → predict."""
        image_path = Path(image_path)
        cfg = parse_strip_config(
            strip_config_path,
            pre_cropped=pre_cropped,
            manual_pad_h=manual_pad_h,
            manual_gap_h=manual_gap_h,
            manual_y_offset=manual_y_offset,
        )

        # Apply negative baseline calibration if provided
        if negative_image_path is not None:
            self._calibrate_from_negative(
                negative_image_path, model, strip_config_path, pre_cropped=pre_cropped
            )

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        # Step 1: Crop
        strip_img = img_bgr if is_pre_cropped else crop_strip(img_bgr, detection_cfg)

        # Step 2: Segment
        template_cfg = cfg.get("template_mask", {})
        boundaries = refine_boundaries(strip_img, len(boxes_order), template_cfg, model, boxes_order)
        box_images = [strip_img[y0:y1, :] for y0, y1 in boundaries]

        # Step 2b: White balance fallback (if no negative baseline was provided)
        wb_gains = (1.0, 1.0, 1.0)

        wb_gains = white_balance_from_plastic(strip_img, boundaries)
        print(f"[INFO] Auto white balance gains (RGB): ({wb_gains[0]:.3f}, {wb_gains[1]:.3f}, {wb_gains[2]:.3f})")

        # Step 3: Sample + Predict
        results: dict[str, BoxResult] = {}
        for analyte, box_img in zip(boxes_order, box_images):
            rgb = sample_box_color(box_img)
            # Apply white balance if no baseline correction
            if not model.has_baseline():
                rgb = apply_white_balance(rgb, wb_gains)
            value, unit, confidence = model.get_concentration(analyte, rgb)
            results[analyte] = BoxResult(
                analyte=analyte,
                color_rgb=rgb,
                value=value,
                unit=unit,
                confidence=confidence,
                box_image=box_img,
            )
        return results

    def analyze_with_debug(
        self,
        image_path: str | Path,
        model: CalibrationModel,
        strip_config_path: str | Path,
        debug_output_path: str = "debug_output.png",
        pre_cropped: bool | None = None,
        manual_pad_h: int | None = None,
        manual_gap_h: int | None = None,
        manual_y_offset: int | None = None,
        negative_image_path: Optional[str | Path] = None,
    ) -> dict[str, BoxResult]:
        """Run analyze() and additionally save an annotated debug image."""
        image_path = Path(image_path)
        cfg = parse_strip_config(
            strip_config_path,
            pre_cropped=pre_cropped,
            manual_pad_h=manual_pad_h,
            manual_gap_h=manual_gap_h,
            manual_y_offset=manual_y_offset,
        )

        # Apply negative baseline calibration if provided
        if negative_image_path is not None:
            self._calibrate_from_negative(
                negative_image_path, model, strip_config_path, pre_cropped=pre_cropped
            )

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        strip_img = img_bgr if is_pre_cropped else crop_strip(img_bgr, detection_cfg)
        template_cfg = cfg.get("template_mask", {})
        
        # We need boundaries for debug drawing
        boundaries = refine_boundaries(strip_img, len(boxes_order), template_cfg, model, boxes_order)
        box_images = [strip_img[y0:y1, :] for y0, y1 in boundaries]

        # White balance fallback (if no negative baseline was provided)
        wb_gains = (1.0, 1.0, 1.0)
        wb_gains = white_balance_from_plastic(strip_img, boundaries)
        print(f"[INFO] Auto white balance gains (RGB): ({wb_gains[0]:.3f}, {wb_gains[1]:.3f}, {wb_gains[2]:.3f})")

        results: dict[str, BoxResult] = {}
        for analyte, box_img in zip(boxes_order, box_images):
            rgb = sample_box_color(box_img)
            # Apply white balance if no baseline correction
            if not model.has_baseline():
                rgb = apply_white_balance(rgb, wb_gains)
            value, unit, confidence = model.get_concentration(analyte, rgb)
            results[analyte] = BoxResult(
                analyte=analyte,
                color_rgb=rgb,
                value=value,
                unit=unit,
                confidence=confidence,
                box_image=box_img,
            )

        # Generate debug image showing calibration mode
        calibration_mode = "Negative Baseline" if model.has_baseline() else "Auto White Balance"
        debug_img = generate_debug_image(strip_img, results, boundaries, calibration_mode=calibration_mode)
        cv2.imwrite(debug_output_path, debug_img)
        print(f"[DEBUG] Annotated image saved to: {debug_output_path}")

        return results
