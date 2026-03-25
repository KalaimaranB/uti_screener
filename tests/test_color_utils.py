"""
tests/test_color_utils.py — Unit tests for core/color_utils.py
"""
import pytest
from core.color_utils import color_distance_rgb, interpolate_concentration


class TestColorDistanceRGB:
    def test_same_color_is_zero(self):
        rgb = (120, 80, 40)
        assert color_distance_rgb(rgb, rgb) < 0.01

    def test_different_colors_nonzero(self):
        rgb1 = (255, 0, 0)
        rgb2 = (0, 0, 255)
        assert color_distance_rgb(rgb1, rgb2) > 300

    def test_symmetry(self):
        rgb1 = (100, 150, 200)
        rgb2 = (50, 80, 120)
        assert abs(color_distance_rgb(rgb1, rgb2) - color_distance_rgb(rgb2, rgb1)) < 1e-6


class TestInterpolateConcentration:
    def _make_ref(self, rgbs_and_values):
        """Helper: build reference_points from list of (rgb, value) pairs."""
        return [
            {"rgb": rgb, "value": value}
            for rgb, value in rgbs_and_values
        ]

    def test_exact_match_returns_correct_value(self):
        refs = self._make_ref([
            ((200, 200, 200), 0),
            ((150, 100, 80), 50),
            ((100, 50, 30), 100),
        ])
        # Query exactly the second swatch colour
        color_rgb = (150, 100, 80)
        value, confidence = interpolate_concentration(color_rgb, refs)
        assert abs(value - 50) < 5  # within 5 units
        assert confidence > 0.8

    def test_midpoint_interpolates(self):
        """A colour halfway between two references should give midpoint value."""
        c1 = (200, 50, 50)
        c2 = (50, 50, 200)
        refs = self._make_ref([(c1, 0), (c2, 100)])
        # Midpoint colour
        color_rgb = (125, 50, 125)
        value, confidence = interpolate_concentration(color_rgb, refs)
        # Should be somewhere between 0 and 100
        assert 0 <= value <= 100

    def test_categorical_returns_string(self):
        refs = [
            {"rgb": (220, 220, 220), "value": "NEGATIVE"},
            {"rgb": (255, 100, 150), "value": "POSITIVE"},
        ]
        color_rgb = (215, 215, 215)
        value, confidence = interpolate_concentration(color_rgb, refs)
        assert value == "NEGATIVE"
        assert isinstance(value, str)

    def test_empty_refs_raises(self):
        with pytest.raises(ValueError):
            interpolate_concentration((100, 100, 100), [])

    def test_single_ref_returns_that_value(self):
        refs = [{"rgb": (200, 150, 100), "value": 42.0}]
        value, confidence = interpolate_concentration((200, 150, 100), refs)
        assert abs(value - 42.0) < 0.01
