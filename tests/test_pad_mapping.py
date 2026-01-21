"""Tests for PadMapping dataclass."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launchpad_mapper import PadMapping, LAUNCHPAD_COLORS, COLOR_HEX


class TestPadMappingCreation:
    """Test PadMapping creation and defaults."""

    def test_create_minimal_mapping(self):
        """Test creating a mapping with minimal required fields."""
        mapping = PadMapping(
            note=60,
            key_combo='space',
            color='green',
            label='Test',
        )
        assert mapping.note == 60
        assert mapping.key_combo == 'space'
        assert mapping.color == 'green'
        assert mapping.label == 'Test'
        assert mapping.enabled is True
        assert mapping.action == 'key'

    def test_create_full_mapping(self):
        """Test creating a mapping with all fields."""
        mapping = PadMapping(
            note=60,
            key_combo='ctrl+c',
            color='blue',
            label='Copy',
            enabled=True,
            action='key',
            target_layer=None,
            repeat_enabled=True,
            repeat_delay=0.3,
            repeat_interval=0.1,
            macro_steps=[{'key_combo': 'a', 'delay_after': 0.1}],
            velocity_mappings={'0-63': 'a', '64-127': 'b'},
            long_press_enabled=True,
            long_press_action='ctrl+shift+c',
            long_press_threshold=0.8,
        )
        assert mapping.repeat_enabled is True
        assert mapping.repeat_delay == 0.3
        assert mapping.repeat_interval == 0.1
        assert mapping.macro_steps == [{'key_combo': 'a', 'delay_after': 0.1}]
        assert mapping.velocity_mappings == {'0-63': 'a', '64-127': 'b'}
        assert mapping.long_press_enabled is True
        assert mapping.long_press_action == 'ctrl+shift+c'
        assert mapping.long_press_threshold == 0.8

    def test_defaults(self):
        """Test default values are set correctly."""
        mapping = PadMapping(
            note=60,
            key_combo='',
            color='green',
            label='',
        )
        assert mapping.enabled is True
        assert mapping.action == 'key'
        assert mapping.target_layer is None
        assert mapping.repeat_enabled is False
        assert mapping.repeat_delay == 0.5
        assert mapping.repeat_interval == 0.05
        assert mapping.macro_steps is None
        assert mapping.velocity_mappings is None
        assert mapping.long_press_enabled is False
        assert mapping.long_press_action == ''
        assert mapping.long_press_threshold == 0.5


class TestPadMappingSerialization:
    """Test PadMapping serialization to/from dict."""

    def test_to_dict(self):
        """Test converting mapping to dictionary."""
        mapping = PadMapping(
            note=60,
            key_combo='ctrl+c',
            color='green',
            label='Copy',
        )
        data = mapping.to_dict()
        assert data['note'] == 60
        assert data['key_combo'] == 'ctrl+c'
        assert data['color'] == 'green'
        assert data['label'] == 'Copy'
        assert data['enabled'] is True

    def test_from_dict_complete(self, sample_mapping_dict):
        """Test creating mapping from complete dictionary."""
        mapping = PadMapping.from_dict(sample_mapping_dict)
        assert mapping.note == 60
        assert mapping.key_combo == 'ctrl+c'
        assert mapping.color == 'green'
        assert mapping.label == 'Copy'

    def test_from_dict_minimal(self):
        """Test creating mapping from minimal dictionary."""
        data = {
            'note': 60,
            'key_combo': 'space',
            'color': 'red',
        }
        mapping = PadMapping.from_dict(data)
        assert mapping.note == 60
        assert mapping.key_combo == 'space'
        assert mapping.color == 'red'
        assert mapping.label == ''
        assert mapping.enabled is True

    def test_round_trip(self):
        """Test that to_dict -> from_dict preserves data."""
        original = PadMapping(
            note=60,
            key_combo='ctrl+shift+a',
            color='purple',
            label='Action',
            repeat_enabled=True,
            repeat_delay=0.2,
            long_press_enabled=True,
            long_press_action='alt+a',
        )
        data = original.to_dict()
        restored = PadMapping.from_dict(data)
        assert restored.note == original.note
        assert restored.key_combo == original.key_combo
        assert restored.color == original.color
        assert restored.label == original.label
        assert restored.repeat_enabled == original.repeat_enabled
        assert restored.repeat_delay == original.repeat_delay
        assert restored.long_press_enabled == original.long_press_enabled
        assert restored.long_press_action == original.long_press_action


class TestPadMappingColors:
    """Test PadMapping color handling."""

    def test_get_launchpad_color_by_name(self):
        """Test getting Launchpad color velocity by color name."""
        mapping = PadMapping(note=60, key_combo='', color='green', label='')
        assert mapping.get_launchpad_color() == LAUNCHPAD_COLORS['green']

    def test_get_launchpad_color_by_hex(self):
        """Test getting Launchpad color from hex value."""
        mapping = PadMapping(note=60, key_combo='', color='#FF0000', label='')
        # Should find closest color (red)
        velocity = mapping.get_launchpad_color()
        assert velocity == LAUNCHPAD_COLORS['red']

    def test_get_launchpad_color_unknown(self):
        """Test getting Launchpad color for unknown color name."""
        mapping = PadMapping(note=60, key_combo='', color='unknown_color', label='')
        # Should default to green (21)
        assert mapping.get_launchpad_color() == 21

    def test_get_display_hex_by_name(self):
        """Test getting display hex from color name."""
        mapping = PadMapping(note=60, key_combo='', color='red', label='')
        assert mapping.get_display_hex() == COLOR_HEX['red']

    def test_get_display_hex_already_hex(self):
        """Test getting display hex when color is already hex."""
        mapping = PadMapping(note=60, key_combo='', color='#AABBCC', label='')
        assert mapping.get_display_hex() == '#AABBCC'

    def test_get_display_hex_unknown(self):
        """Test getting display hex for unknown color."""
        mapping = PadMapping(note=60, key_combo='', color='nonexistent', label='')
        # Should default to green hex
        assert mapping.get_display_hex() == '#00FF00'


class TestPadMappingActions:
    """Test PadMapping action configurations."""

    def test_layer_action(self):
        """Test layer switch action."""
        mapping = PadMapping(
            note=60,
            key_combo='',
            color='cyan',
            label='Switch',
            action='layer',
            target_layer='Alt',
        )
        assert mapping.action == 'layer'
        assert mapping.target_layer == 'Alt'

    def test_layer_up_action(self):
        """Test layer up action."""
        mapping = PadMapping(
            note=60,
            key_combo='',
            color='yellow',
            label='Back',
            action='layer_up',
        )
        assert mapping.action == 'layer_up'

    def test_macro_action(self):
        """Test macro action."""
        steps = [
            {'key_combo': 'ctrl+a', 'delay_after': 0.1},
            {'key_combo': 'ctrl+c', 'delay_after': 0.0},
        ]
        mapping = PadMapping(
            note=60,
            key_combo='',
            color='orange',
            label='SelectCopy',
            macro_steps=steps,
        )
        assert mapping.macro_steps == steps
        assert len(mapping.macro_steps) == 2

    def test_velocity_mappings(self):
        """Test velocity-based action mappings."""
        velocity_map = {
            '0-42': 'ctrl+1',
            '43-84': 'ctrl+2',
            '85-127': 'ctrl+3',
        }
        mapping = PadMapping(
            note=60,
            key_combo='ctrl+0',
            color='purple',
            label='VelAction',
            velocity_mappings=velocity_map,
        )
        assert mapping.velocity_mappings == velocity_map
