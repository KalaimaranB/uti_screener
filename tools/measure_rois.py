#!/usr/bin/env python3
"""
tools/measure_rois.py — Interactive ROI coordinate picker.

Click the TOP-LEFT and BOTTOM-RIGHT corners of each colour swatch.
The script prints the [x, y, w, h] ROI for each click-pair.

Usage:
    python3 tools/measure_rois.py tests/fixtures/chart.png
"""
import sys
import cv2

clicks = []
roi_count = 0


def on_click(event, x, y, flags, param):
    global clicks, roi_count
    if event == cv2.EVENT_LBUTTONDOWN:
        clicks.append((x, y))
        print(f"  Point {len(clicks)}: ({x}, {y})")
        if len(clicks) == 2:
            x1, y1 = clicks[0]
            x2, y2 = clicks[1]
            rx, ry = min(x1, x2), min(y1, y2)
            rw, rh = abs(x2 - x1), abs(y2 - y1)
            roi_count += 1
            print(f"\n✅ ROI #{roi_count}: [{rx}, {ry}, {rw}, {rh}]  ← paste into chart_rois.json\n")
            clicks = []


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/measure_rois.py <chart_image>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"Could not open: {sys.argv[1]}")
        sys.exit(1)

    # Scale down large images so they fit on screen
    h, w = img.shape[:2]
    scale = min(1.0, 1200 / max(w, h))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        print(f"[INFO] Image scaled to {scale:.2f}x. Coordinates are already corrected.")
        # Override click handler to account for scale
        def on_click_scaled(event, x, y, flags, param):
            global clicks, roi_count
            if event == cv2.EVENT_LBUTTONDOWN:
                rx, ry = int(x / scale), int(y / scale)
                clicks.append((rx, ry))
                print(f"  Point {len(clicks)}: ({rx}, {ry})")
                if len(clicks) == 2:
                    x1, y1 = clicks[0]
                    x2, y2 = clicks[1]
                    ox, oy = min(x1, x2), min(y1, y2)
                    ow, oh = abs(x2 - x1), abs(y2 - y1)
                    roi_count += 1
                    print(f"\n✅ ROI #{roi_count}: [{ox}, {oy}, {ow}, {oh}]  ← paste into chart_rois.json\n")
                    clicks.clear()
        cv2.namedWindow("ROI Picker")
        cv2.setMouseCallback("ROI Picker", on_click_scaled)
    else:
        cv2.namedWindow("ROI Picker")
        cv2.setMouseCallback("ROI Picker", on_click)

    print("=" * 55)
    print("  ROI PICKER — Click TOP-LEFT then BOTTOM-RIGHT of each swatch")
    print("  Press Q to quit")
    print("=" * 55 + "\n")

    while True:
        cv2.imshow("ROI Picker", img)
        if cv2.waitKey(20) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
