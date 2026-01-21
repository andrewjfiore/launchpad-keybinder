#!/usr/bin/env python3
"""
Schema validation for profile imports and API payloads.
Provides security and data integrity for imported data.
"""

from typing import Any, Dict, List, Optional, Tuple

# Maximum sizes to prevent DoS attacks
MAX_PROFILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_MAPPINGS_PER_LAYER = 500
MAX_LAYERS = 50
MAX_MACRO_STEPS = 100
MAX_STRING_LENGTH = 1000
MAX_VELOCITY_MAPPINGS = 20


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(f"{field + ': ' if field else ''}{message}")


def validate_type(value: Any, expected_type: type, field: str) -> None:
    """Validate that a value is of the expected type."""
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"Expected {expected_type.__name__}, got {type(value).__name__}",
            field
        )


def validate_string(value: Any, field: str, max_length: int = MAX_STRING_LENGTH,
                    allow_empty: bool = True) -> str:
    """Validate a string value."""
    validate_type(value, str, field)
    if len(value) > max_length:
        raise ValidationError(f"String exceeds maximum length of {max_length}", field)
    if not allow_empty and not value:
        raise ValidationError("String cannot be empty", field)
    return value


def validate_int(value: Any, field: str, min_val: Optional[int] = None,
                 max_val: Optional[int] = None) -> int:
    """Validate an integer value."""
    if isinstance(value, bool):
        raise ValidationError("Expected integer, got boolean", field)
    if not isinstance(value, int):
        raise ValidationError(f"Expected integer, got {type(value).__name__}", field)
    if min_val is not None and value < min_val:
        raise ValidationError(f"Value must be >= {min_val}", field)
    if max_val is not None and value > max_val:
        raise ValidationError(f"Value must be <= {max_val}", field)
    return value


def validate_float(value: Any, field: str, min_val: Optional[float] = None,
                   max_val: Optional[float] = None) -> float:
    """Validate a float value."""
    if isinstance(value, bool):
        raise ValidationError("Expected number, got boolean", field)
    if not isinstance(value, (int, float)):
        raise ValidationError(f"Expected number, got {type(value).__name__}", field)
    if min_val is not None and value < min_val:
        raise ValidationError(f"Value must be >= {min_val}", field)
    if max_val is not None and value > max_val:
        raise ValidationError(f"Value must be <= {max_val}", field)
    return float(value)


def validate_bool(value: Any, field: str) -> bool:
    """Validate a boolean value."""
    validate_type(value, bool, field)
    return value


def validate_dict(value: Any, field: str) -> Dict:
    """Validate a dictionary value."""
    validate_type(value, dict, field)
    return value


def validate_list(value: Any, field: str, max_length: Optional[int] = None) -> List:
    """Validate a list value."""
    validate_type(value, list, field)
    if max_length is not None and len(value) > max_length:
        raise ValidationError(f"List exceeds maximum length of {max_length}", field)
    return value


def validate_optional(value: Any, validator, field: str, default: Any = None):
    """Validate an optional value."""
    if value is None:
        return default
    return validator(value, field)


# ===========================================================================
# PAD MAPPING VALIDATION
# ===========================================================================

VALID_ACTIONS = {"key", "layer", "layer_up", "macro"}
VALID_COLORS = {
    "off", "white", "red", "red_dim", "orange", "orange_dim", "yellow",
    "yellow_dim", "lime", "lime_dim", "green", "green_dim", "spring",
    "spring_dim", "cyan", "cyan_dim", "sky", "sky_dim", "blue", "blue_dim",
    "purple", "purple_dim", "magenta", "magenta_dim", "pink", "pink_dim",
    "coral", "coral_dim", "amber", "amber_dim"
}


def validate_color(value: Any, field: str) -> str:
    """Validate a color value (name or hex)."""
    validate_string(value, field)
    # Allow hex colors
    if value.startswith('#'):
        if len(value) not in (4, 7):  # #RGB or #RRGGBB
            raise ValidationError("Invalid hex color format", field)
        try:
            int(value[1:], 16)
        except ValueError:
            raise ValidationError("Invalid hex color", field)
        return value
    # Validate named color
    if value not in VALID_COLORS:
        raise ValidationError(
            f"Invalid color. Must be hex or one of: {', '.join(sorted(VALID_COLORS))}",
            field
        )
    return value


def validate_key_combo(value: Any, field: str) -> str:
    """Validate a key combination string."""
    validate_string(value, field, max_length=500, allow_empty=True)
    # Basic sanity checks - don't allow shell metacharacters
    dangerous_chars = ['`', '$', '|', '>', '<', ';', '&', '\n', '\r']
    for char in dangerous_chars:
        if char in value:
            raise ValidationError(f"Invalid character in key combo: {repr(char)}", field)
    return value


def validate_macro_step(step: Any, field: str) -> Dict[str, Any]:
    """Validate a single macro step."""
    validate_dict(step, field)

    result = {}
    if 'key_combo' in step:
        result['key_combo'] = validate_key_combo(step['key_combo'], f"{field}.key_combo")

    if 'delay_after' in step:
        result['delay_after'] = validate_float(
            step['delay_after'],
            f"{field}.delay_after",
            min_val=0.0,
            max_val=60.0  # Max 60 second delay
        )

    return result


def validate_velocity_mappings(value: Any, field: str) -> Dict[str, str]:
    """Validate velocity mappings dictionary."""
    validate_dict(value, field)

    if len(value) > MAX_VELOCITY_MAPPINGS:
        raise ValidationError(
            f"Too many velocity mappings (max {MAX_VELOCITY_MAPPINGS})",
            field
        )

    result = {}
    for range_str, key_combo in value.items():
        # Validate range format (e.g., "0-42")
        validate_string(range_str, f"{field}.key")
        parts = range_str.split('-')
        if len(parts) != 2:
            raise ValidationError(
                f"Invalid velocity range format: {range_str}. Use 'min-max'",
                field
            )
        try:
            low, high = int(parts[0]), int(parts[1])
            if not (0 <= low <= 127 and 0 <= high <= 127 and low <= high):
                raise ValueError()
        except ValueError:
            raise ValidationError(
                f"Invalid velocity range: {range_str}. Values must be 0-127",
                field
            )

        result[range_str] = validate_key_combo(key_combo, f"{field}.{range_str}")

    return result


def validate_pad_mapping(data: Any, field: str = "mapping") -> Dict[str, Any]:
    """Validate a complete pad mapping object."""
    validate_dict(data, field)

    result = {}

    # Required fields
    result['note'] = validate_int(data.get('note'), f"{field}.note", min_val=0, max_val=127)
    result['key_combo'] = validate_key_combo(
        data.get('key_combo', ''),
        f"{field}.key_combo"
    )
    result['color'] = validate_color(data.get('color', 'green'), f"{field}.color")

    # Optional fields with defaults
    result['label'] = validate_string(
        data.get('label', ''),
        f"{field}.label",
        max_length=100
    )
    result['enabled'] = validate_bool(data.get('enabled', True), f"{field}.enabled")

    action = data.get('action', 'key')
    if action not in VALID_ACTIONS:
        raise ValidationError(
            f"Invalid action. Must be one of: {', '.join(VALID_ACTIONS)}",
            f"{field}.action"
        )
    result['action'] = action

    if 'target_layer' in data and data['target_layer'] is not None:
        result['target_layer'] = validate_string(
            data['target_layer'],
            f"{field}.target_layer",
            max_length=100
        )

    # Repeat settings
    result['repeat_enabled'] = validate_bool(
        data.get('repeat_enabled', False),
        f"{field}.repeat_enabled"
    )
    result['repeat_delay'] = validate_float(
        data.get('repeat_delay', 0.5),
        f"{field}.repeat_delay",
        min_val=0.0,
        max_val=10.0
    )
    result['repeat_interval'] = validate_float(
        data.get('repeat_interval', 0.05),
        f"{field}.repeat_interval",
        min_val=0.01,
        max_val=10.0
    )

    # Macro steps
    if 'macro_steps' in data and data['macro_steps'] is not None:
        steps = validate_list(
            data['macro_steps'],
            f"{field}.macro_steps",
            max_length=MAX_MACRO_STEPS
        )
        result['macro_steps'] = [
            validate_macro_step(step, f"{field}.macro_steps[{i}]")
            for i, step in enumerate(steps)
        ]

    # Velocity mappings
    if 'velocity_mappings' in data and data['velocity_mappings'] is not None:
        result['velocity_mappings'] = validate_velocity_mappings(
            data['velocity_mappings'],
            f"{field}.velocity_mappings"
        )

    # Long press settings
    result['long_press_enabled'] = validate_bool(
        data.get('long_press_enabled', False),
        f"{field}.long_press_enabled"
    )
    result['long_press_action'] = validate_key_combo(
        data.get('long_press_action', ''),
        f"{field}.long_press_action"
    )
    result['long_press_threshold'] = validate_float(
        data.get('long_press_threshold', 0.5),
        f"{field}.long_press_threshold",
        min_val=0.1,
        max_val=10.0
    )

    return result


# ===========================================================================
# PROFILE VALIDATION
# ===========================================================================

def validate_profile(data: Any, field: str = "profile") -> Dict[str, Any]:
    """
    Validate a complete profile object.

    Returns the validated and sanitized profile data.
    """
    validate_dict(data, field)

    result = {}

    # Profile metadata
    result['name'] = validate_string(
        data.get('name', 'Imported'),
        f"{field}.name",
        max_length=100,
        allow_empty=False
    )
    result['description'] = validate_string(
        data.get('description', ''),
        f"{field}.description",
        max_length=1000
    )
    result['base_layer'] = validate_string(
        data.get('base_layer', 'Base'),
        f"{field}.base_layer",
        max_length=100,
        allow_empty=False
    )

    # Validate layers
    layers_data = data.get('layers')
    if layers_data is not None:
        validate_dict(layers_data, f"{field}.layers")

        if len(layers_data) > MAX_LAYERS:
            raise ValidationError(
                f"Too many layers (max {MAX_LAYERS})",
                f"{field}.layers"
            )

        result['layers'] = {}
        for layer_name, mappings in layers_data.items():
            layer_field = f"{field}.layers.{layer_name}"
            validate_string(layer_name, f"{layer_field} (key)", max_length=100)
            validate_dict(mappings, layer_field)

            if len(mappings) > MAX_MAPPINGS_PER_LAYER:
                raise ValidationError(
                    f"Too many mappings in layer (max {MAX_MAPPINGS_PER_LAYER})",
                    layer_field
                )

            result['layers'][layer_name] = {}
            for note_str, mapping_data in mappings.items():
                mapping_field = f"{layer_field}.{note_str}"
                # Ensure note key is valid
                try:
                    note_key = str(int(note_str))
                except ValueError:
                    raise ValidationError(
                        f"Invalid note key: {note_str}",
                        mapping_field
                    )

                validated_mapping = validate_pad_mapping(mapping_data, mapping_field)
                result['layers'][layer_name][note_key] = validated_mapping

    # Handle legacy 'mappings' format (flat, no layers)
    elif 'mappings' in data:
        mappings = data['mappings']
        validate_dict(mappings, f"{field}.mappings")

        if len(mappings) > MAX_MAPPINGS_PER_LAYER:
            raise ValidationError(
                f"Too many mappings (max {MAX_MAPPINGS_PER_LAYER})",
                f"{field}.mappings"
            )

        result['layers'] = {result['base_layer']: {}}
        for note_str, mapping_data in mappings.items():
            mapping_field = f"{field}.mappings.{note_str}"
            try:
                note_key = str(int(note_str))
            except ValueError:
                raise ValidationError(
                    f"Invalid note key: {note_str}",
                    mapping_field
                )

            validated_mapping = validate_pad_mapping(mapping_data, mapping_field)
            result['layers'][result['base_layer']][note_key] = validated_mapping

    else:
        # Empty profile
        result['layers'] = {result['base_layer']: {}}

    return result


def validate_profile_import(data: Any, raw_size: Optional[int] = None) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate a profile for import.

    Args:
        data: The profile data to validate
        raw_size: Optional size of the raw JSON in bytes

    Returns:
        Tuple of (validated_data, warnings)

    Raises:
        ValidationError: If validation fails
    """
    warnings = []

    # Check size limits
    if raw_size is not None and raw_size > MAX_PROFILE_SIZE_BYTES:
        raise ValidationError(
            f"Profile too large ({raw_size / 1024 / 1024:.1f}MB). "
            f"Maximum size is {MAX_PROFILE_SIZE_BYTES / 1024 / 1024:.0f}MB"
        )

    # Validate structure
    validated = validate_profile(data)

    # Count total mappings
    total_mappings = sum(
        len(mappings)
        for mappings in validated.get('layers', {}).values()
    )
    if total_mappings > 1000:
        warnings.append(f"Profile contains {total_mappings} mappings, which may impact performance")

    return validated, warnings
