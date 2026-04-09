# Strip Analysis Algorithm (Technical & Mathematical Reference)

This document provides a comprehensive mathematical and architectural teardown of the computer vision pipeline. It details exactly how the system maps raw pixels to biochemical concentrations, ensuring transparency for the 95% accuracy benchmark.

---

## 🏗️ 1. Pipeline Architecture Map

```mermaid
graph TD
    A[Raw Image] --> B[Crop & Alignment (External)]
    B --> C[Stage 1: 1D Edge Segmentation]
    C -- "Fail (CV > 0.3)" --> D[Stage 2: Grid Search Engine]
    C -- "Success" --> E[Pad Bounding Boxes]
    D --> E
    E --> F[Central 75% Sampling]
    F --> G[Negative Baseline Shift]
    G --> H[3D Piecewise Polyline Projection]
    H --> I[Categorical/Numeric Heuristics]
    I --> J[Final Concentration & Confidence]
```

---

## 📏 2. Stage 1: Geometric Segmentation (1D Edge)

The objective is to isolate $N=10$ reagent pads from a continuous plastic strip. Stage 1 treats this as a 1D signal processing problem.

### The Mathematics of the 1D Profile
We first mask out dark background pixels ($BGR_{mean} < 30$). For every row $y$ in the image, we compute the mean color of valid pixels to get a 1D brightness profile $\bar{B}(y)$:

$$ \bar{B}(y) = \frac{1}{|X|} \sum_{x \in X_{valid}} \frac{R_{x,y} + G_{x,y} + B_{x,y}}{3} $$

Because raw images contain noise, we apply a Gaussian filter with standard deviation $\sigma = 2.5$ to smooth the signal:

$$ S(y) = (G_{\sigma=2.5} * \bar{B})(y) $$

### Derivative and Zero-Crossings
The algorithm calculates the first derivative $S'(y)$. Peaks in $S(y)$ represent the bright white plastic gaps, while valleys represent dark reagent pads. We segment by finding regions where $S(y) > \tau_{bright}$ (where $\tau_{bright}$ is the 65th percentile of the smoothed signal). 

**Validation:** We require exactly $N$ distinct pad runs. If found, we evaluate the Coefficient of Variation ($CV$) of their heights $H_{pad}$:

$$ CV = \frac{\sigma(H_{pad})}{\mu(H_{pad})} $$

If $CV < 0.30$ and the gap-to-pad ratio is physiologically plausible ($0.15 \le \text{ratio} \le 1.2$), the fast edge detection succeeds.

---

## 🎯 3. Stage 2: Geometric Segmentation (Grid Search)

If Stage 1 fails (e.g., due to washed-out colors or severe blur), we fall back to a computationally intensive **Grid Search**. We evaluate every possible physical combination of pad height $P$, gap height $G$, vertical offset $y_{off}$, and Orientation $dir \in \{Normal, Flipped\}$.

The "perfect fit" maximizes a holistic scoring function composed of five mathematical terms:

$$ \text{Score}_{total} = S_{color} + S_{nonwhite} + S_{gapbright} - S_{gapwhite} - S_{anchor} - S_{size} $$

### Primary: Calibration Color Match ($S_{color}$)
Matches the mean color $\bar{C}_i$ of a proposed pad window $i$ to its nearest expected calibration swatch $s \in ExpectedSwatches_i$. This heavily rewards templates that land exactly on the expected sequence of chemical colors.

$$ S_{color} = -8.0 \times \frac{1}{N} \sum_{i=1}^N \left( \min_{s} || \bar{C}_i - s ||_2 \right) $$

### Secondary: Non-White Reward ($S_{nonwhite}$)
Pads should look like chemicals, not white plastic. Let $W$ be the median BGR color of the entire strip background.

$$ S_{nonwhite} = +3.0 \times \frac{1}{N} \sum_{i=1}^N || \bar{C}_i - W ||_2 $$

### Tertiary: Gap Constraints ($S_{gapbright}, S_{gapwhite}$)
Gap regions should be brightly colored and chromatically similar to the plastic backbone $W$. Let $\bar{G}_{bright}$ be the mean brightness of all gap pixels.

$$ S_{gapbright} = +2.0 \times \max(0, \min(50, \bar{G}_{bright} - \tau_{gap})) $$

$$ S_{gapwhite} = -1.5 \times \frac{1}{N-1} \sum_{i=1}^{N-1} || \bar{C}_{gap, i} - W ||_2 $$

### Structural Penalties ($S_{anchor}, S_{size}$)
Quadratic penalties to enforce physical reality. $y_0$ is the estimated first-pad drop from the top of the image.

$$ S_{anchor} = -80.0 \times \left( \frac{|y_{off} - y_0|}{P+G} \right)^2 $$

$$ S_{size} = -4.0 \times \left( \frac{P}{P+G} - 0.60 \right)^2 \times (P+G) $$

---

## 🎨 4. Sampling & Chromaticity Normalization

### Central 75% Sampling
To prevent "Wick Effects" (where liquid bleeds into the plastic edges) from ruining the color reading, the algorithm extracts only the geometric center of the bounding box:
$x \in [0.25w, 0.75w]$, $y \in [0.25h, 0.75h]$
The final color $C$ is the element-wise median of this core region.

### Chromaticity Space Transformation
Urinalysis is highly sensitive to shadowing. We convert raw $[R,G,B]$ into Chromaticity Space, which perfectly preserves hue ratios while destroying total-illumination variance:

$$ C_{chroma} = \begin{bmatrix} \frac{R}{R+G+B} \\ \frac{G}{R+G+B} \\ \frac{B}{R+G+B} \end{bmatrix} \times 255 $$

---

## 📐 5. 3D Piecewise Polyline Interpolation

Linear regression fails for chemical pads because color shifts are non-linear trajectories through 3D space (e.g., Yellow $\to$ Green $\to$ Blue-Brown).

We model each analyte as a connected polyline composed of vertices $V_0, V_1, ..., V_k$ established during calibration. 

### Continuous Vector Projection
For an unknown measured continuous color $Q$, we project it onto every line segment $A \to B$ in the polyline model to find the closest physical fit. 

Let $\vec{v} = B - A$ and $\vec{w} = Q - A$.

1. **Calculate Fractional Position ($b$):**
   $$ b = \frac{\vec{w} \cdot \vec{v}}{\vec{v} \cdot \vec{v}} $$
   We clamp $b$ to $[0, 1]$ so it stays within the line segment.

2. **Calculate Distance to Projection:**
   $$ P_{proj} = A + b\vec{v} $$
   $$ \text{Distance} = || Q - P_{proj} ||_2 $$

We select the segment that minimizes the Distance.

3. **Interpolate Concentration:**
   Using the winning segment's known concentrations $C_A$ and $C_B$:
   $$ \text{Value}(Q) = C_A + b(C_B - C_A) $$

---

## 🛡️ 6. Adaptive Heuristics & The 95% Benchmark

To achieve clinical-grade accuracy across different devices, we employ two hard heuristics layered on top of the mathematical projection.

### A. Dynamic Curve Shifting (Negative Baseline)
Different room lighting environments warp the calibration curve. If a user provides a negative strip, we calculate an additive translation vector $\vec{\Delta}$ for each analyte:
$$ \vec{\Delta} = N_{measured} - N_{baseline} $$

The *entire* 3D polyline curve is structurally shifted by this vector prior to projection:
$$ V'_{i} = V_i + \vec{\Delta_{i}} $$
This forces evaluation directly in the user's specific environmental color space.

### B. The Hard Deadzone
Sensors produce microscopic noise. To prevent trace readouts on perfectly healthy patients, we enforce a strict RGB-space distance cutoff around the lowest node ($V_0$). If the Euclidean distance is less than 25 units:
$$ \text{If } || Q - V_{0,shifted} ||_2 < 25.0 \implies \text{Value} = 0.0 $$

### C. Nitrite Pinkness Index
The Nitrite test does not act as a smooth gradient; it is a binary shift where the Red channel outpaces the Green channel, creating a physical pink hue.

$$ \text{Pinkness}(C) = R_{C} - G_{C} $$
$$ \text{If } \text{Pinkness}(Q) > \text{Pinkness}(V_{0,shifted}) + 4 \implies \text{POSITIVE} $$

This ensures that only chemical activation (not arbitrary darkening) triggers the Nitrite diagnosis.
