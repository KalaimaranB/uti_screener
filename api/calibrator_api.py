"""
api/calibrator_api.py — Public API for Program 1: Calibration.

This module is the stable external interface. Internal implementation details
live in core/. Follow the Open/Closed Principle: extend by adding new
analyte configs, not by modifying this API.
"""
from __future__ import annotations

from pathlib import Path

from core.calibration import CalibrationModel


def build_model(
    chart_image_path: str,
    chart_rois_path: str,
) -> CalibrationModel:
    """
    Build a CalibrationModel from a reference chart image + ROI config.

    Parameters
    ----------
    chart_image_path:
        Filesystem path to the colour reference chart image (PNG/JPG).
    chart_rois_path:
        Filesystem path to ``chart_rois.json`` describing swatch pixel ROIs.
    """
    return CalibrationModel.from_chart_image(chart_image_path, chart_rois_path)


def build_model_from_colors(chart_colors_path: str) -> CalibrationModel:
    """
    Build a CalibrationModel directly from RGB values — no image required.

    Use this when you have measured swatch colours with a tool like
    macOS Digital Color Meter and entered them into ``chart_colors.json``.

    Parameters
    ----------
    chart_colors_path:
        Filesystem path to ``chart_colors.json``.

    Example
    -------
    >>> model = build_model_from_colors("config/chart_colors.json")
    """
    return CalibrationModel.from_color_config(chart_colors_path)


def save_model(model: CalibrationModel, output_path: str) -> None:
    """
    Persist a CalibrationModel to a JSON file.

    Parameters
    ----------
    model:
        The model returned by :func:`build_model`.
    output_path:
        Destination path (e.g. ``"models/model.json"``).
        Parent directories are created automatically.
    """
    model.save(output_path)


def load_model(model_path: str) -> CalibrationModel:
    """
    Load a previously saved CalibrationModel from JSON.

    Parameters
    ----------
    model_path:
        Path to the saved ``model.json`` file.

    Returns
    -------
    CalibrationModel
    """
    return CalibrationModel.load(model_path)
