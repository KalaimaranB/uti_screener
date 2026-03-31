from dataclasses import dataclass, field
from typing import Union
import numpy as np
from core.color_utils import RGB

@dataclass
class BoxResult:
    """Analysis result for one reagent pad."""
    analyte: str
    color_rgb: RGB
    value: Union[float, str]
    unit: str
    confidence: float
    box_image: np.ndarray = field(repr=False, default=None)  # type: ignore
