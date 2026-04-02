"""
api/analyzer_api.py — Public API for Program 2: Strip Analysis.

Exposes a single stable entry-point ``analyze_strip()`` and the
``AnalysisResult`` dataclass that callers consume.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Union

from core.calibration import CalibrationModel
from core.strip_analyzer import StripAnalyzer
from core.models import BoxResult


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """
    Result for a single reagent pad on the strip.

    Attributes
    ----------
    analyte:
        Name of the analyte (e.g. ``"glucose"``).
    color_rgb:
        Sampled RGB colour as a (R, G, B) tuple (0-255 each).
    value:
        Concentration or categorical label (e.g. ``30.0`` or ``"POSITIVE"``).
    unit:
        Unit string (e.g. ``"mmol/L"``).
    confidence:
        Match confidence in [0.0, 1.0]. 1.0 = exact colour match.
    """
    analyte: str
    color_rgb: tuple[int, int, int]
    value: Union[float, str]
    unit: str
    confidence: float

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Main API function
# ---------------------------------------------------------------------------

def analyze_strip(
    image_path: str,
    model_path: str,
    strip_config_path: str,
    pre_cropped: bool | None = None,
    manual_pad_h: int | None = None,
    manual_gap_h: int | None = None,
    manual_y_offset: int | None = None,
    negative_image_path: str | None = None,
) -> dict[str, AnalysisResult]:
    """
    Analyse a urinalysis strip image and return per-analyte concentrations.

    Parameters
    ----------
    image_path:
        Path to the CV-system output image (strip bordered with a solid colour).
    model_path:
        Path to the calibration model JSON (produced by Program 1).
    strip_config_path:
        Path to ``strip_config.json`` specifying box order and border colour.
    pre_cropped:
        (Optional) Override the JSON config's pre_cropped flag.
    manual_pad_h, manual_gap_h, manual_y_offset:
        (Optional) Override the default auto-geometric template search with explicit pixel parameters.

    Returns
    -------
    dict[str, AnalysisResult]
        Mapping from analyte name to its :class:`AnalysisResult`.

    Example
    -------
    >>> results = analyze_strip("strip.png", "models/model.json", "config/strip_config.json")
    >>> print(results["glucose"].value, results["glucose"].unit)
    30.0 mmol/L
    """
    model = CalibrationModel.load(model_path)
    analyzer = StripAnalyzer()
    raw = analyzer.analyze(
        image_path,
        model,
        strip_config_path,
        pre_cropped=pre_cropped,
        manual_pad_h=manual_pad_h,
        manual_gap_h=manual_gap_h,
        manual_y_offset=manual_y_offset,
        negative_image_path=negative_image_path,
    )

    return {
        analyte: AnalysisResult(
            analyte=br.analyte,
            color_rgb=br.color_rgb,
            value=br.value,
            unit=br.unit,
            confidence=br.confidence,
        )
        for analyte, br in raw.items()
    }


def results_to_json(results: dict[str, AnalysisResult], indent: int = 2) -> str:
    """Serialise analysis results to a JSON string."""
    return json.dumps(
        {k: v.to_dict() for k, v in results.items()},
        indent=indent,
    )
