import cv2
import numpy as np
from pathlib import Path

from .calibration import CalibrationModel
from .models import BoxResult
from .config_parser import parse_strip_config
from .strip_cropper import crop_strip
from .strip_segmenter import segment_boxes
from .color_sampler import sample_box_color
from .debug_renderer import generate_debug_image

class StripAnalyzer:
    """
    Processes a CV-output image to extract per-box concentrations.
    This class acts as a coordinator (Facade) delegating to specialized modules.
    """

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
        """Full pipeline: load image → crop strip → segment boxes → predict."""
        image_path = Path(image_path)
        cfg = parse_strip_config(
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

        # Step 1: Crop
        strip_img = img_bgr if is_pre_cropped else crop_strip(img_bgr, detection_cfg)

        # Step 2: Segment
        template_cfg = cfg.get("template_mask", {})
        box_images, _ = segment_boxes(strip_img, len(boxes_order), template_cfg, model, boxes_order)

        # Step 3: Sample + Predict
        results: dict[str, BoxResult] = {}
        for analyte, box_img in zip(boxes_order, box_images):
            rgb = sample_box_color(box_img)
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

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")

        boxes_order: list[str] = cfg["boxes_top_to_bottom"]
        detection_cfg: dict = cfg.get("strip_detection", {})
        is_pre_cropped: bool = cfg.get("pre_cropped", False)

        strip_img = img_bgr if is_pre_cropped else crop_strip(img_bgr, detection_cfg)
        template_cfg = cfg.get("template_mask", {})
        
        # We need boundaries for debug drawing
        from .strip_segmenter import refine_boundaries
        boundaries = refine_boundaries(strip_img, len(boxes_order), template_cfg, model, boxes_order)
        
        box_images = [strip_img[y0:y1, :] for y0, y1 in boundaries]

        results: dict[str, BoxResult] = {}
        for analyte, box_img in zip(boxes_order, box_images):
            rgb = sample_box_color(box_img)
            value, unit, confidence = model.get_concentration(analyte, rgb)
            results[analyte] = BoxResult(
                analyte=analyte,
                color_rgb=rgb,
                value=value,
                unit=unit,
                confidence=confidence,
                box_image=box_img,
            )

        debug_img = generate_debug_image(strip_img, results, boundaries)
        cv2.imwrite(debug_output_path, debug_img)
        print(f"[DEBUG] Annotated image saved to: {debug_output_path}")

        return results
