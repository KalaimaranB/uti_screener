# Urinalysis Strip Analyzer

A Python project for automated urinalysis strip reading using **3D Piecewise Polyline RGB Projection** and computer vision.
A live model can be accessed here at :https://uti-screener.streamlit.app/.

📄 **Documentation:**
- **[Algorithm Deep-Dive](docs/ALGORITHM.md)** — How the 95% accuracy model works.
- **[Clinical Diagnostics](docs/CLINICAL_DIAGNOSTICS.md)** — Medical rationale & scientific citations.
- **[API Reference](docs/API_REFERENCE.md)** — Python API for programmatic integration.
- **[Configuration Guide](docs/CONFIGURATION_GUIDE.md)** — Tuning the JSON settings.
- **[README.md](README.md)** — Quick-start guide (you are here).

---

## Setup

```bash
pip install -r requirements.txt
```

---

## At-Home User Interface (Streamlit)

A user-friendly web interface is available for easy at-home test strip scanning and clinical diagnosis.

```bash
# Launch the user interface
streamlit run user_interface.py
```
This interface handles image cropping automatically via trained YOLO models, runs the color calibration, and displays an annotated and print-friendly patient report!

---

## 🔬 Scientific Foundation

Our detection pipeline utilizes three primary biomarkers to improve accuracy and provide deeper insights:

1.  **Nitrite Presence**: Identifies bacteria with the **nitrate reductase** enzyme (e.g., Gram-negative *E. coli*), which converts nitrates to nitrites, turning the pad **pink**.
2.  **Leukocyte Levels**: Detects inflammation (pyuria). In a healthy patient, leukocytes are minimal; infection causes a dramatic increase, shifting the pad color from **beige to brown or purple**.
3.  **Alkaline pH**: Identifies bacteria with the **urease enzyme** (e.g., *Proteus*). These bacteria convert urea to ammonia, making urine more alkaline (**pH > 7.5**).

---

## Program 1 — Calibrate (run once)

Builds a colour→concentration model from your chart measurements.

```bash
# From RGB values you measured with Digital Color Meter:
python3 program1_calibrate.py \
  --colors config/chart_colors.json \
  --output models/model.json

# OR from the physical chart image + ROI coordinates:
python3 program1_calibrate.py \
  --chart  tests/fixtures/chart.png \
  --rois   config/chart_rois.json \
  --output models/model.json
```

---

## Program 2 — Analyze a strip

```bash
python3 program2_analyze.py \
  --image  tests/samples/Sample1.jpg \
  --model  models/model.json \
  --config config/strip_config.json \
  --output results.json           # optional JSON save

# Debug mode — saves an annotated image showing identified boxes:
python3 program2_analyze.py \
  --image  tests/samples/Sample1.jpg \
  --model  models/model.json \
  --config config/strip_config.json \
  --debug                         # writes debug_output.png alongside the result
```

---

---

## 🛠️ Advanced Usage

For deep technical details, clinical rationale, and programmatic integration, please refer to the documentation linked above.

- **Programmatic Integration**: See `docs/API_REFERENCE.md` for information on using the `analyze_strip(...)` function directly in Python.
- **Tuning & Troubleshooting**: See `docs/CONFIGURATION_GUIDE.md` for details on manual alignment and calibration parameters.
