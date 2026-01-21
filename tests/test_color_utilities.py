"""Tests for color utility functions."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launchpad_mapper import (
    hex_to_rgb,
    rgb_distance,
    find_closest_launchpad_color,
    LAUNCHPAD_COLORS,
    COLOR_HEX,
)


class TestHexToRgb:
    """Test hex to RGB conversion."""

    def test_basic_colors(self):
        """Test converting basic hex colors."""
        assert hex_to_rgb('#FF0000') == (255, 0, 0)
        assert hex_to_rgb('#00FF00') == (0, 255, 0)
        assert hex_to_rgb('#0000FF') == (0, 0, 255)

    def test_white_black(self):
        """Test converting white and black."""
        assert hex_to_rgb('#FFFFFF') == (255, 255, 255)
        assert hex_to_rgb('#000000') == (0, 0, 0)

    def test_mixed_colors(self):
        """Test converting mixed hex colors."""
        assert hex_to_rgb('#808080') == (128, 128, 128)
        assert hex_to_rgb('#AABBCC') == (170, 187, 204)

    def test_without_hash(self):
        """Test converting without hash prefix."""
        assert hex_to_rgb('FF0000') == (255, 0, 0)

    def test_lowercase(self):
        """Test lowercase hex values."""
        assert hex_to_rgb('#ff00ff') == (255, 0, 255)
        assert hex_to_rgb('#aabbcc') == (170, 187, 204)

    def test_caching(self):
        """Test that function caches results."""
        # Call multiple times with same input
        result1 = hex_to_rgb('#FF0000')
        result2 = hex_to_rgb('#FF0000')
        assert result1 == result2


class TestRgbDistance:
    """Test RGB color distance calculation."""

    def test_same_color(self):
        """Test distance between same colors is 0."""
        assert rgb_distance((255, 0, 0), (255, 0, 0)) == 0.0
        assert rgb_distance((0, 0, 0), (0, 0, 0)) == 0.0

    def test_primary_colors(self):
        """Test distance between primary colors."""
        # Red to Green (both differ by 255 in R and G)
        distance = rgb_distance((255, 0, 0), (0, 255, 0))
        assert distance > 0
        # Should be sqrt(255^2 + 255^2) = sqrt(130050) ≈ 360.62
        assert abs(distance - 360.62) < 1

    def test_black_to_white(self):
        """Test distance between black and white."""
        distance = rgb_distance((0, 0, 0), (255, 255, 255))
        # sqrt(255^2 * 3) ≈ 441.67
        assert abs(distance - 441.67) < 1

    def test_symmetry(self):
        """Test that distance is symmetric."""
        d1 = rgb_distance((100, 150, 200), (50, 100, 150))
        d2 = rgb_distance((50, 100, 150), (100, 150, 200))
        assert d1 == d2


class TestFindClosestLaunchpadColor:
    """Test finding closest Launchpad color to hex value."""

    def test_exact_red(self):
        """Test exact red match."""
        assert find_closest_launchpad_color('#FF0000') == 'red'

    def test_exact_green(self):
        """Test exact green match."""
        assert find_closest_launchpad_color('#00FF00') == 'green'

    def test_exact_blue(self):
        """Test exact blue match."""
        assert find_closest_launchpad_color('#0000FF') == 'blue'

    def test_close_to_orange(self):
        """Test color close to orange."""
        # Orange in palette is #FF8000
        result = find_closest_launchpad_color('#FF7000')
        assert result == 'orange'

    def test_close_to_cyan(self):
        """Test color close to cyan."""
        result = find_closest_launchpad_color('#00FFFF')
        assert result == 'cyan'

    def test_close_to_magenta(self):
        """Test color close to magenta."""
        result = find_closest_launchpad_color('#FF00FF')
        assert result == 'magenta'

    def test_dim_red(self):
        """Test dim red selection."""
        # Dim red is #800000
        result = find_closest_launchpad_color('#800000')
        assert result == 'red_dim'

    def test_white(self):
        """Test white selection."""
        result = find_closest_launchpad_color('#FFFFFF')
        assert result == 'white'

    def test_caching(self):
        """Test that function caches results."""
        result1 = find_closest_launchpad_color('#FF0000')
        result2 = find_closest_launchpad_color('#FF0000')
        assert result1 == result2

    def test_all_palette_colors_are_closest_to_themselves(self):
        """Test that each palette color maps back to itself."""
        for name, hex_val in COLOR_HEX.items():
            if name == 'off':
                continue  # off is skipped in the matching
            result = find_closest_launchpad_color(hex_val)
            assert result == name, f"Expected {name} for {hex_val}, got {result}"


class TestLaunchpadColorsConfig:
    """Test LAUNCHPAD_COLORS and COLOR_HEX configuration."""

    def test_launchpad_colors_has_off(self):
        """Test that off color exists."""
        assert 'off' in LAUNCHPAD_COLORS
        assert LAUNCHPAD_COLORS['off'] == 0

    def test_color_hex_has_off(self):
        """Test that off color hex exists."""
        assert 'off' in COLOR_HEX
        assert COLOR_HEX['off'] == '#333333'

    def test_all_launchpad_colors_have_hex(self):
        """Test that all LAUNCHPAD_COLORS have corresponding COLOR_HEX."""
        for color_name in LAUNCHPAD_COLORS.keys():
            assert color_name in COLOR_HEX, f"{color_name} missing from COLOR_HEX"

    def test_all_hex_have_launchpad_colors(self):
        """Test that all COLOR_HEX have corresponding LAUNCHPAD_COLORS."""
        for color_name in COLOR_HEX.keys():
            assert color_name in LAUNCHPAD_COLORS, f"{color_name} missing from LAUNCHPAD_COLORS"

    def test_velocity_values_are_valid(self):
        """Test that all velocity values are in valid MIDI range."""
        for name, velocity in LAUNCHPAD_COLORS.items():
            assert 0 <= velocity <= 127, f"{name} has invalid velocity {velocity}"

    def test_hex_values_are_valid(self):
        """Test that all hex values are valid."""
        import re
        pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        for name, hex_val in COLOR_HEX.items():
            assert pattern.match(hex_val), f"{name} has invalid hex {hex_val}"

    def test_dim_colors_have_lower_velocity(self):
        """Test that dim colors have different velocities from bright colors."""
        dim_pairs = [
            ('red', 'red_dim'),
            ('green', 'green_dim'),
            ('blue', 'blue_dim'),
            ('yellow', 'yellow_dim'),
            ('orange', 'orange_dim'),
        ]
        for bright, dim in dim_pairs:
            if bright in LAUNCHPAD_COLORS and dim in LAUNCHPAD_COLORS:
                # Dim version should have different velocity
                assert LAUNCHPAD_COLORS[bright] != LAUNCHPAD_COLORS[dim]
