import numpy as np
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
