"""
tests/test_color_utils.py — Unit tests for core/color_utils.py
"""
import pytest
from core.color_utils import rgb_to_lab, delta_e, interpolate_concentration


class TestRgbToLab:
    def test_black(self):
        L, a, b = rgb_to_lab((0, 0, 0))
        assert abs(L) < 1.0

    def test_white(self):
        L, a, b = rgb_to_lab((255, 255, 255))
        assert L > 99.0

    def test_red(self):
        L, a, b = rgb_to_lab((255, 0, 0))
        # Red should have high positive a*
        assert a > 30

    def test_pure_green(self):
        L, a, b = rgb_to_lab((0, 255, 0))
        # Green should have negative a*
        assert a < -30

    def test_returns_three_floats(self):
        result = rgb_to_lab((128, 64, 200))
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)


class TestDeltaE:
    def test_same_color_is_zero(self):
        lab = rgb_to_lab((120, 80, 40))
        assert delta_e(lab, lab) < 0.01

    def test_different_colors_nonzero(self):
        lab1 = rgb_to_lab((255, 0, 0))
        lab2 = rgb_to_lab((0, 0, 255))
        assert delta_e(lab1, lab2) > 10

    def test_symmetry(self):
        lab1 = rgb_to_lab((100, 150, 200))
        lab2 = rgb_to_lab((50, 80, 120))
        assert abs(delta_e(lab1, lab2) - delta_e(lab2, lab1)) < 1e-6


class TestInterpolateConcentration:
    def _make_ref(self, rgbs_and_values):
        """Helper: build reference_points from list of (rgb, value) pairs."""
        return [
            {"lab": rgb_to_lab(rgb), "value": value}
            for rgb, value in rgbs_and_values
        ]

    def test_exact_match_returns_correct_value(self):
        refs = self._make_ref([
            ((200, 200, 200), 0),
            ((150, 100, 80), 50),
            ((100, 50, 30), 100),
        ])
        # Query exactly the second swatch colour
        color_lab = rgb_to_lab((150, 100, 80))
        value, confidence = interpolate_concentration(color_lab, refs)
        assert abs(value - 50) < 5  # within 5 units
        assert confidence > 0.8

    def test_midpoint_interpolates(self):
        """A colour halfway between two references should give midpoint value."""
        c1 = (200, 200, 200)
        c2 = (50, 50, 50)
        refs = self._make_ref([(c1, 0), (c2, 100)])
        # Midpoint colour
        mid = (125, 125, 125)
        color_lab = rgb_to_lab(mid)
        value, confidence = interpolate_concentration(color_lab, refs)
        # Should be somewhere between 0 and 100
        assert 0 <= value <= 100

    def test_categorical_returns_string(self):
        refs = [
            {"lab": rgb_to_lab((220, 220, 220)), "value": "NEGATIVE"},
            {"lab": rgb_to_lab((255, 100, 150)), "value": "POSITIVE"},
        ]
        color_lab = rgb_to_lab((215, 215, 215))
        value, confidence = interpolate_concentration(color_lab, refs)
        assert value == "NEGATIVE"
        assert isinstance(value, str)

    def test_empty_refs_raises(self):
        with pytest.raises(ValueError):
            interpolate_concentration(rgb_to_lab((100, 100, 100)), [])

    def test_single_ref_returns_that_value(self):
        refs = [{"lab": rgb_to_lab((200, 150, 100)), "value": 42.0}]
        value, confidence = interpolate_concentration(rgb_to_lab((200, 150, 100)), refs)
        assert abs(value - 42.0) < 0.01
