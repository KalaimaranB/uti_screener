import cv2
import numpy as np

def crop_strip(img_bgr: np.ndarray, detection_cfg: dict) -> np.ndarray:
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
