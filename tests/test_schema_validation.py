#!/usr/bin/env python3
"""Tests for the schema validation module."""

import pytest

from schema_validation import (
    ValidationError,
    validate_string,
    validate_int,
    validate_float,
    validate_bool,
    validate_color,
    validate_key_combo,
    validate_pad_mapping,
    validate_profile,
    validate_profile_import,
    MAX_PROFILE_SIZE_BYTES,
    MAX_MAPPINGS_PER_LAYER,
    MAX_LAYERS,
)


class TestBasicValidators:
    """Tests for basic validation functions."""

    def test_validate_string_valid(self):
        """Test string validation with valid input."""
        result = validate_string("test", "field")
        assert result == "test"

    def test_validate_string_too_long(self):
        """Test string validation with too long input."""
        with pytest.raises(ValidationError) as exc:
            validate_string("x" * 2000, "field", max_length=100)
        assert "maximum length" in str(exc.value)

    def test_validate_string_empty_not_allowed(self):
        """Test string validation with empty when not allowed."""
        with pytest.raises(ValidationError):
            validate_string("", "field", allow_empty=False)

    def test_validate_string_wrong_type(self):
        """Test string validation with wrong type."""
        with pytest.raises(ValidationError) as exc:
            validate_string(123, "field")
        assert "Expected str" in str(exc.value)

    def test_validate_int_valid(self):
        """Test integer validation with valid input."""
        assert validate_int(42, "field") == 42

    def test_validate_int_min_max(self):
        """Test integer validation with min/max."""
        assert validate_int(50, "field", min_val=0, max_val=100) == 50

    def test_validate_int_below_min(self):
        """Test integer validation below minimum."""
        with pytest.raises(ValidationError):
            validate_int(-1, "field", min_val=0)

    def test_validate_int_above_max(self):
        """Test integer validation above maximum."""
        with pytest.raises(ValidationError):
            validate_int(150, "field", max_val=100)

    def test_validate_int_rejects_bool(self):
        """Test that boolean is rejected as integer."""
        with pytest.raises(ValidationError):
            validate_int(True, "field")

    def test_validate_float_valid(self):
        """Test float validation with valid input."""
        assert validate_float(3.14, "field") == 3.14

    def test_validate_float_accepts_int(self):
        """Test float validation accepts integers."""
        assert validate_float(42, "field") == 42.0

    def test_validate_bool_valid(self):
        """Test boolean validation."""
        assert validate_bool(True, "field") is True
        assert validate_bool(False, "field") is False

    def test_validate_bool_rejects_int(self):
        """Test that integer is rejected as boolean."""
        with pytest.raises(ValidationError):
            validate_bool(1, "field")


class TestColorValidation:
    """Tests for color validation."""

    def test_valid_named_color(self):
        """Test valid named color."""
        assert validate_color("green", "color") == "green"

    def test_valid_hex_color_6(self):
        """Test valid 6-digit hex color."""
        assert validate_color("#FF0000", "color") == "#FF0000"

    def test_valid_hex_color_3(self):
        """Test valid 3-digit hex color."""
        assert validate_color("#F00", "color") == "#F00"

    def test_invalid_hex_length(self):
        """Test invalid hex color length."""
        with pytest.raises(ValidationError):
            validate_color("#FF00", "color")

    def test_invalid_hex_chars(self):
        """Test invalid hex color characters."""
        with pytest.raises(ValidationError):
            validate_color("#GGGGGG", "color")

    def test_invalid_color_name(self):
        """Test invalid color name."""
        with pytest.raises(ValidationError):
            validate_color("neon_purple", "color")


class TestKeyComboValidation:
    """Tests for key combo validation."""

    def test_valid_key_combo(self):
        """Test valid key combo."""
        assert validate_key_combo("ctrl+c", "combo") == "ctrl+c"

    def test_empty_key_combo(self):
        """Test empty key combo is allowed."""
        assert validate_key_combo("", "combo") == ""

    def test_dangerous_chars_rejected(self):
        """Test dangerous shell characters are rejected."""
        dangerous = ["`ls`", "$(rm -rf)", "cmd | other", "cmd; rm", "cmd && rm"]
        for combo in dangerous:
            with pytest.raises(ValidationError):
                validate_key_combo(combo, "combo")


class TestPadMappingValidation:
    """Tests for pad mapping validation."""

    def test_minimal_mapping(self):
        """Test validation of minimal mapping."""
        data = {
            'note': 42,
            'key_combo': 'ctrl+c',
            'color': 'green'
        }
        result = validate_pad_mapping(data)
        assert result['note'] == 42
        assert result['key_combo'] == 'ctrl+c'
        assert result['color'] == 'green'

    def test_full_mapping(self):
        """Test validation of full mapping."""
        data = {
            'note': 42,
            'key_combo': 'ctrl+c',
            'color': '#FF0000',
            'label': 'Copy',
            'enabled': True,
            'action': 'key',
            'repeat_enabled': True,
            'repeat_delay': 0.5,
            'repeat_interval': 0.1,
            'long_press_enabled': True,
            'long_press_action': 'ctrl+v',
            'long_press_threshold': 0.8
        }
        result = validate_pad_mapping(data)
        assert result['label'] == 'Copy'
        assert result['repeat_enabled'] is True

    def test_invalid_note_range(self):
        """Test invalid note range."""
        with pytest.raises(ValidationError):
            validate_pad_mapping({'note': 200, 'key_combo': '', 'color': 'green'})

    def test_invalid_action(self):
        """Test invalid action type."""
        with pytest.raises(ValidationError):
            validate_pad_mapping({
                'note': 42,
                'key_combo': '',
                'color': 'green',
                'action': 'invalid_action'
            })

    def test_macro_steps_validation(self):
        """Test macro steps validation."""
        data = {
            'note': 42,
            'key_combo': '',
            'color': 'green',
            'macro_steps': [
                {'key_combo': 'ctrl+a', 'delay_after': 0.5},
                {'key_combo': 'ctrl+c', 'delay_after': 0.1}
            ]
        }
        result = validate_pad_mapping(data)
        assert len(result['macro_steps']) == 2

    def test_velocity_mappings_validation(self):
        """Test velocity mappings validation."""
        data = {
            'note': 42,
            'key_combo': '',
            'color': 'green',
            'velocity_mappings': {
                '0-42': 'ctrl+1',
                '43-84': 'ctrl+2',
                '85-127': 'ctrl+3'
            }
        }
        result = validate_pad_mapping(data)
        assert len(result['velocity_mappings']) == 3

    def test_invalid_velocity_range(self):
        """Test invalid velocity range format."""
        with pytest.raises(ValidationError):
            validate_pad_mapping({
                'note': 42,
                'key_combo': '',
                'color': 'green',
                'velocity_mappings': {'invalid': 'ctrl+c'}
            })


class TestProfileValidation:
    """Tests for profile validation."""

    def test_minimal_profile(self):
        """Test validation of minimal profile."""
        data = {'name': 'Test'}
        result = validate_profile(data)
        assert result['name'] == 'Test'
        assert result['base_layer'] == 'Base'

    def test_profile_with_layers(self):
        """Test profile with multiple layers."""
        data = {
            'name': 'Test',
            'layers': {
                'Base': {
                    '42': {'note': 42, 'key_combo': 'ctrl+c', 'color': 'green'}
                },
                'Layer2': {}
            }
        }
        result = validate_profile(data)
        assert 'Base' in result['layers']
        assert 'Layer2' in result['layers']

    def test_profile_legacy_format(self):
        """Test profile with legacy mappings format."""
        data = {
            'name': 'Test',
            'mappings': {
                '42': {'note': 42, 'key_combo': 'ctrl+c', 'color': 'green'}
            }
        }
        result = validate_profile(data)
        assert 'Base' in result['layers']
        assert '42' in result['layers']['Base']

    def test_too_many_layers(self):
        """Test rejection of too many layers."""
        data = {
            'name': 'Test',
            'layers': {f'Layer{i}': {} for i in range(MAX_LAYERS + 1)}
        }
        with pytest.raises(ValidationError):
            validate_profile(data)

    def test_too_many_mappings(self):
        """Test rejection of too many mappings in a layer."""
        data = {
            'name': 'Test',
            'layers': {
                'Base': {
                    str(i): {'note': i % 128, 'key_combo': '', 'color': 'green'}
                    for i in range(MAX_MAPPINGS_PER_LAYER + 1)
                }
            }
        }
        with pytest.raises(ValidationError):
            validate_profile(data)


class TestProfileImport:
    """Tests for profile import validation."""

    def test_valid_import(self):
        """Test valid profile import."""
        data = {
            'name': 'Imported',
            'layers': {'Base': {}}
        }
        result, warnings = validate_profile_import(data)
        assert result['name'] == 'Imported'
        assert warnings == []

    def test_size_limit(self):
        """Test profile size limit."""
        with pytest.raises(ValidationError) as exc:
            validate_profile_import({}, raw_size=MAX_PROFILE_SIZE_BYTES + 1)
        assert "too large" in str(exc.value)

    def test_warning_for_many_mappings(self):
        """Test warning for many mappings."""
        # Create profile with many mappings
        layers = {}
        for layer_num in range(10):
            layers[f'Layer{layer_num}'] = {
                str(i): {'note': i % 128, 'key_combo': '', 'color': 'green'}
                for i in range(200)
            }
        data = {'name': 'Big', 'layers': layers}

        result, warnings = validate_profile_import(data)
        # Should have warning about many mappings
        assert any('mappings' in w for w in warnings)
