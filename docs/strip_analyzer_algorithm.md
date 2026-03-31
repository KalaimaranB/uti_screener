# Urinalysis Strip Analyzer Algorithm

The `StripAnalyzer` module is the core computer vision pipeline responsible for taking raw images of urinalysis dipped strips and mathematically isolating each of the 10 chemical reagent boxes. 

Rather than relying purely on static image cropping (which fails quickly on angled images, zoomed scans, and physical imperfections), the analyzer treats the system as a **1D geometric signal processing grid search** heavily constrained by the chemical's expected RGB hues.

## 1. Background Masking and Pre-computation

Instead of dealing with 2D bounds right away, the algorithm reduces the image problem into a 1-dimensional "row signal" array by reading the visual properties of the strip row by row from top to bottom.

1. **Non-Black Masking**: Dark canvas space surrounding the strip is excluded entirely by ignoring all pixels with a brightness under 30.
2. **Plastic Baseline Extraction (`strip_bgr`)**: We pull the median color hue of the remaining "valid" strip pixels to ascertain the color of the physical white plastic backing.
3. **Saturation Tracking**: We calculate a 1D array of the max variance across RGB channels for each row (`max_channel - min_channel`). Reagent chemicals typically exhibit very loud colors (high saturation), while plastic gaps, shadows, and glares are desaturated (grays / whites).
4. **Cumulative Sums (O(1) Sweeps)**: We wrap the raw BGR rows and the Saturation rows into `cumsum` vectors. This allows us to instantly calculate the average values for *any slice* of the strip by just taking the difference at the start and end of the sum arrays.

## 2. Parameter Grid Search

Because strips can vary wildly in zoom level and offset, the system iterates over a vast brute-force combination of:
- **`pad_h`**: The height of the reagent box (pixels).
- **`gap_h`**: The height of the plastic space between boxes (pixels).
- **`y_offset`**: The amount of blank top margin before the very first box.

For any combination, we generate exact bounding boxes. To determine if that combination is the "perfect fit," we calculate a holistic `score`.

## 3. The Objective Scoring Equation

The chosen arrangement is simply the combination that maximizes the combined heuristic rules below:

### *A. Geometric Resonance*
We strongly reward alignments that trap highly vivid saturation inside the `pad` windows while trapping dead grays inside the `gap` windows.
`score = (pad_signal_mean - gap_signal_mean * 2.0) * 50.0`

### *B. Inter-Pad Diversity Tie-Breaker*
We lightly reward combinations that pick up completely drastically different colors between the 10 boxes, slightly helping to push boxes away from accidentally snapping to a monochromatic stretch.

### *C. Gap Plastic Validation*
Since some reagent pads are whitish (like Leukocytes in a resting state), it's possible to confuse a gap for a pad based solely on geometry. The fix forces the gap intervals to be close to the *median white strip color*. 
We measure the Euclidean distance between our targeted background hue and the average pixel values inside the gap bounding boxes, penalizing the score heavily if the gap doesn't look like white plastic stock.

### *D. Theoretical Color Constraints*
We map the sampled color from every pad and measure its euclidean distance to the expected calibration swatch colors stored for those specific analytes. If a boundary match proposes that the red Blood pad is blue, we inject a massive score penalty. This constraint perfectly aligns the geometry mask to real biological reality.

## 4. Inverted Auto-Detection

When running the grid search, the system simulates two alternative realities for the color analysis component:
- **Normal Scoring (Top to bottom)**: Checks against the config (Leukocyte at bottom = index 0 through Glucose at top).
- **Flipped Scoring (Bottom to top)**: The reverse sequence checks mapping the config arrays backward.

If the *Flipped Scoring* yields a higher alignment with the physical chemistry model, the algorithm declares `is_flipped = True`.

### Output Inversion
When returning the bounding boxes for extraction, if the strip was flagged as upside-down, the algorithm physically reverses the returned tuple assignments. The rest of the application naturally unpacks index `0` thinking it's analyzing the Leukocytes bounding box, and thanks to the flip, the system feeds it the physical pad located at the bottom of the image natively without having to manually flip the raw image file in memory!
