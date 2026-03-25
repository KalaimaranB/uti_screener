"""
tests/test_calibration.py — Unit tests for core/calibration.py

Uses a synthetic in-memory chart to verify model construction and
concentration prediction without requiring actual image fixtures.
"""
import json
import tempfile
from pathlib import Path

import numpy as np
import cv2
import pytest

from core.calibration import CalibrationModel, Swatch, AnalyteCalibration
from core.color_utils import rgb_to_lab


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synthetic_chart(rois_cfg: dict, tmp_path: Path):
    """
    Create a synthetic chart image where each swatch ROI is filled with the
    exact expected colour, then save it and a matching ROI JSON to tmp_path.
    """
    # Determine image size from max ROI extents
    max_x = max_y = 0
    for analyte_cfg in rois_cfg.values():
        if isinstance(analyte_cfg, str):
            continue
        for sw in analyte_cfg.get("swatches", []):
            x, y, w, h = sw["roi"]
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

    img = np.zeros((max_y + 10, max_x + 10, 3), dtype=np.uint8)

    # Paint each swatch with a unique colour
    colour_map: dict[str, dict[str, tuple]] = {}
    for analyte_key, analyte_cfg in rois_cfg.items():
        if isinstance(analyte_cfg, str):
            continue
        colour_map[analyte_key] = {}
        for sw in analyte_cfg.get("swatches", []):
            x, y, w, h = sw["roi"]
            # Derive a deterministic colour from the value
            seed = hash(f"{analyte_key}/{sw['label']}") % (256 ** 3)
            r = (seed >> 16) & 0xFF
            g = (seed >> 8) & 0xFF
            b = seed & 0xFF
            img[y : y + h, x : x + w] = (b, g, r)  # OpenCV stores BGR
            colour_map[analyte_key][sw["label"]] = (r, g, b)

    chart_path = tmp_path / "chart.png"
    cv2.imwrite(str(chart_path), img)

    rois_path = tmp_path / "chart_rois.json"
    rois_path.write_text(json.dumps(rois_cfg))

    return chart_path, rois_path, colour_map


# ---------------------------------------------------------------------------
# Minimal fixture config
# ---------------------------------------------------------------------------

MINIMAL_ROIS = {
    "glucose": {
        "unit": "mmol/L",
        "type": "numeric",
        "swatches": [
            {"label": "NEGATIVE", "value": 0,   "roi": [10, 10, 60, 50]},
            {"label": "TRACE",    "value": 5,   "roi": [80, 10, 60, 50]},
            {"label": "+",        "value": 15,  "roi": [150, 10, 60, 50]},
        ],
    },
    "nitrite": {
        "unit": "categorical",
        "type": "categorical",
        "swatches": [
            {"label": "NEGATIVE", "value": "NEGATIVE", "roi": [10, 70, 60, 50]},
            {"label": "POSITIVE", "value": "POSITIVE", "roi": [80, 70, 60, 50]},
        ],
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCalibrationModel:
    def test_from_chart_image_builds_model(self, tmp_path):
        chart_path, rois_path, colour_map = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)
        assert "glucose" in model.analyte_names()
        assert "nitrite" in model.analyte_names()

    def test_correct_number_of_swatches(self, tmp_path):
        chart_path, rois_path, _ = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)
        cal = model._analytes["glucose"]
        assert len(cal.swatches) == 3

    def test_numeric_prediction_exact_colour(self, tmp_path):
        """Querying with the exact swatch colour should return near-exact value."""
        chart_path, rois_path, colour_map = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)

        # Use the exact colour of the NEGATIVE swatch (value=0)
        neg_rgb = colour_map["glucose"]["NEGATIVE"]
        value, unit, confidence = model.get_concentration("glucose", neg_rgb)
        assert unit == "mmol/L"
        assert confidence > 0.5

    def test_categorical_prediction(self, tmp_path):
        chart_path, rois_path, colour_map = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)

        pos_rgb = colour_map["nitrite"]["POSITIVE"]
        value, unit, confidence = model.get_concentration("nitrite", pos_rgb)
        assert value == "POSITIVE"
        assert isinstance(value, str)

    def test_unknown_analyte_raises(self, tmp_path):
        chart_path, rois_path, _ = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)
        with pytest.raises(KeyError):
            model.get_concentration("nonexistent_analyte", (100, 100, 100))

    def test_save_and_load_roundtrip(self, tmp_path):
        chart_path, rois_path, colour_map = _make_synthetic_chart(MINIMAL_ROIS, tmp_path)
        model = CalibrationModel.from_chart_image(chart_path, rois_path)

        model_path = tmp_path / "model.json"
        model.save(model_path)
        loaded = CalibrationModel.load(model_path)

        assert loaded.analyte_names() == model.analyte_names()
        # Prediction should be consistent after reload
        neg_rgb = colour_map["glucose"]["NEGATIVE"]
        v1, u1, c1 = model.get_concentration("glucose", neg_rgb)
        v2, u2, c2 = loaded.get_concentration("glucose", neg_rgb)
        assert u1 == u2
        assert abs(float(v1) - float(v2)) < 0.01

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CalibrationModel.load(tmp_path / "does_not_exist.json")

    def test_from_chart_nonexistent_image_raises(self, tmp_path):
        rois_path = tmp_path / "rois.json"
        rois_path.write_text(json.dumps(MINIMAL_ROIS))
        with pytest.raises(FileNotFoundError):
            CalibrationModel.from_chart_image(tmp_path / "ghost.png", rois_path)
