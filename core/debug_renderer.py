import cv2
import numpy as np
from typing import List, Tuple, Dict
from core.models import BoxResult

def generate_debug_image(
    strip_img: np.ndarray,
    results: Dict[str, BoxResult],
    boundaries: List[Tuple[int, int]],
    calibration_mode: str = "Uncalibrated",
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

    # Calibration mode indicator
    mode_color = (40, 160, 40) if "Baseline" in calibration_mode else (80, 80, 200)
    cv2.putText(
        canvas,
        f"Calibration: {calibration_mode}",
        (w + 10, 36),
        font,
        0.4,
        mode_color,
        1,
        cv2.LINE_AA,
    )

    return canvas
