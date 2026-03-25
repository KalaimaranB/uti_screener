"""
core/calibration.py — Builds and stores the per-analyte colour→concentration model.

Design (SRP / OCP):
  CalibrationModel is the single source of truth for the calibration.
  It can be constructed from a chart image + ROI config, or loaded from JSON.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import cv2
import numpy as np

from .color_utils import rgb_to_lab, interpolate_concentration, LAB, RGB


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Swatch:
    """One reference colour swatch on the chart."""
    label: str
    value: Union[float, str]
    rgb: RGB
    lab: LAB


@dataclass
class AnalyteCalibration:
    """All swatches for a single analyte."""
    name: str
    unit: str
    analyte_type: str           # "numeric" | "categorical"
    swatches: list[Swatch] = field(default_factory=list)

    def predict(self, color_rgb: RGB) -> tuple[Union[float, str], float]:
        """Return (concentration, confidence) for a given RGB colour.

        Swatches that share the same ``value`` (e.g. NEGATIVE_1 / NEGATIVE_2)
        are collapsed into a single centroid LAB reference point before
        interpolation, so they jointly define a colour zone rather than
        competing as separate candidates.
        """
        color_lab = rgb_to_lab(color_rgb)

        # --- Group swatches by value → centroid LAB ---
        groups: dict[Union[float, str], list] = {}
        for s in self.swatches:
            groups.setdefault(s.value, []).append(s.lab)

        reference_points = [
            {
                "lab": tuple(
                    sum(ch) / len(labs) for ch in zip(*labs)
                ),
                "value": value,
            }
            for value, labs in groups.items()
        ]

        return interpolate_concentration(color_lab, reference_points)


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------

class CalibrationModel:
    """
    Encapsulates the full calibration for all analytes on a urinalysis strip.

    Build via ``CalibrationModel.from_chart_image()`` or
    ``CalibrationModel.load(path)``.
    """

    def __init__(self) -> None:
        self._analytes: dict[str, AnalyteCalibration] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_chart_image(
        cls,
        image_path: str | Path,
        chart_rois_path: str | Path,
    ) -> "CalibrationModel":
        """
        Build a CalibrationModel by sampling colour swatches from the chart
        image using the ROI definitions in *chart_rois_path*.

        Parameters
        ----------
        image_path:
            Path to the colour reference chart image (PNG/JPG).
        chart_rois_path:
            Path to ``chart_rois.json`` describing pixel ROIs per analyte.

        Returns
        -------
        CalibrationModel
        """
        image_path = Path(image_path)
        chart_rois_path = Path(chart_rois_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Chart image not found: {image_path}")
        if not chart_rois_path.exists():
            raise FileNotFoundError(f"ROI config not found: {chart_rois_path}")

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        with open(chart_rois_path, "r") as f:
            rois_cfg: dict = json.load(f)

        model = cls()

        for analyte_key, analyte_cfg in rois_cfg.items():
            if analyte_key.startswith("_"):
                continue  # skip comment keys

            analyte_cal = AnalyteCalibration(
                name=analyte_key,
                unit=analyte_cfg.get("unit", ""),
                analyte_type=analyte_cfg.get("type", "numeric"),
            )

            for swatch_cfg in analyte_cfg.get("swatches", []):
                x, y, w, h = swatch_cfg["roi"]
                roi_pixels = img_rgb[y : y + h, x : x + w]

                if roi_pixels.size == 0:
                    print(
                        f"[WARNING] Empty ROI for {analyte_key}/{swatch_cfg['label']} "
                        f"— check chart_rois.json coordinates."
                    )
                    continue

                # Use the median colour of a central 50% crop to avoid edge artefacts
                cy, cx = roi_pixels.shape[:2]
                y0, y1 = cy // 4, 3 * cy // 4
                x0, x1 = cx // 4, 3 * cx // 4
                core_pixels = roi_pixels[y0:y1, x0:x1].reshape(-1, 3)
                median_rgb: RGB = tuple(int(v) for v in np.median(core_pixels, axis=0))  # type: ignore

                swatch = Swatch(
                    label=swatch_cfg["label"],
                    value=swatch_cfg["value"],
                    rgb=median_rgb,
                    lab=rgb_to_lab(median_rgb),
                )
                analyte_cal.swatches.append(swatch)

            model._analytes[analyte_key] = analyte_cal
            print(
                f"[INFO] Calibrated '{analyte_key}' "
                f"with {len(analyte_cal.swatches)} swatches."
            )

        return model

    @classmethod
    def from_color_config(
        cls,
        chart_colors_path: str | Path,
    ) -> "CalibrationModel":
        """
        Build a CalibrationModel directly from RGB values in a JSON config.

        No image required — each swatch's colour is specified explicitly.
        Ideal when colours are read with a tool like macOS Digital Color Meter.

        Parameters
        ----------
        chart_colors_path:
            Path to ``chart_colors.json`` containing per-swatch RGB values.

        Returns
        -------
        CalibrationModel
        """
        chart_colors_path = Path(chart_colors_path)
        if not chart_colors_path.exists():
            raise FileNotFoundError(f"Color config not found: {chart_colors_path}")

        with open(chart_colors_path, "r") as f:
            cfg: dict = json.load(f)

        model = cls()

        for analyte_key, analyte_cfg in cfg.items():
            if analyte_key.startswith("_"):
                continue  # skip comment/instruction keys

            analyte_cal = AnalyteCalibration(
                name=analyte_key,
                unit=analyte_cfg.get("unit", ""),
                analyte_type=analyte_cfg.get("type", "numeric"),
            )

            for swatch_cfg in analyte_cfg.get("swatches", []):
                rgb: RGB = tuple(swatch_cfg["rgb"])  # type: ignore
                swatch = Swatch(
                    label=swatch_cfg["label"],
                    value=swatch_cfg["value"],
                    rgb=rgb,
                    lab=rgb_to_lab(rgb),
                )
                analyte_cal.swatches.append(swatch)

            model._analytes[analyte_key] = analyte_cal
            print(
                f"[INFO] Calibrated '{analyte_key}' "
                f"with {len(analyte_cal.swatches)} swatches (from RGB config)."
            )

        return model

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def get_concentration(
        self,
        analyte: str,
        color_rgb: RGB,
    ) -> tuple[Union[float, str], str, float]:
        """
        Predict concentration for a reagent pad colour.

        Parameters
        ----------
        analyte:
            Analyte key (e.g. ``"glucose"``).
        color_rgb:
            Measured RGB colour of the pad as an (R, G, B) tuple (0-255).

        Returns
        -------
        (value, unit, confidence)
        """
        if analyte not in self._analytes:
            raise KeyError(
                f"Analyte '{analyte}' not in model. "
                f"Available: {list(self._analytes.keys())}"
            )
        cal = self._analytes[analyte]
        value, confidence = cal.predict(color_rgb)
        return (value, cal.unit, confidence)

    def analyte_names(self) -> list[str]:
        """Return a list of all calibrated analyte keys."""
        return list(self._analytes.keys())

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Persist the model to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        for name, cal in self._analytes.items():
            data[name] = {
                "unit": cal.unit,
                "type": cal.analyte_type,
                "swatches": [
                    {
                        "label": s.label,
                        "value": s.value,
                        "rgb": list(s.rgb),
                        "lab": list(s.lab),
                    }
                    for s in cal.swatches
                ],
            }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] Model saved to {path}")

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationModel":
        """Load a previously saved model from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        with open(path, "r") as f:
            data: dict = json.load(f)

        model = cls()
        for name, cfg in data.items():
            cal = AnalyteCalibration(
                name=name,
                unit=cfg["unit"],
                analyte_type=cfg["type"],
            )
            for s in cfg["swatches"]:
                cal.swatches.append(
                    Swatch(
                        label=s["label"],
                        value=s["value"],
                        rgb=tuple(s["rgb"]),    # type: ignore
                        lab=tuple(s["lab"]),    # type: ignore
                    )
                )
            model._analytes[name] = cal
        print(f"[INFO] Model loaded from {path} ({len(model._analytes)} analytes)")
        return model
