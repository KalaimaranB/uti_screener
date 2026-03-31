import json
from pathlib import Path

def parse_strip_config(
    strip_config_path: str | Path,
    pre_cropped: bool | None = None,
    manual_pad_h: int | None = None,
    manual_gap_h: int | None = None,
    manual_y_offset: int | None = None,
) -> dict:
    """Load JSON config and apply any explicit kwargs as overrides."""
    with open(strip_config_path, "r") as f:
        cfg = json.load(f)

    if pre_cropped is not None:
        cfg["pre_cropped"] = pre_cropped

    if any(v is not None for v in (manual_pad_h, manual_gap_h, manual_y_offset)):
        if "template_mask" not in cfg:
            cfg["template_mask"] = {}
        if manual_pad_h is not None:
            cfg["template_mask"]["manual_pad_h"] = manual_pad_h
        if manual_gap_h is not None:
            cfg["template_mask"]["manual_gap_h"] = manual_gap_h
        if manual_y_offset is not None:
            cfg["template_mask"]["manual_y_offset"] = manual_y_offset

    return cfg
