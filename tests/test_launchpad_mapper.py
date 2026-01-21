"""Tests for LaunchpadMapper class."""
import pytest
import sys
import os
import threading
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launchpad_mapper import LaunchpadMapper, Profile, PadMapping


class TestLaunchpadMapperInitialization:
    """Test LaunchpadMapper initialization."""

    def test_default_initialization(self):
        """Test mapper initializes with defaults."""
        mapper = LaunchpadMapper()
        assert mapper.profile is not None
        assert mapper.input_port is None
        assert mapper.output_port is None
        assert mapper.running is False
        assert mapper.midi_thread is None
        assert mapper.callbacks == []
        assert mapper.layer_stack == [mapper.profile.base_layer]

    def test_auto_reconnect_defaults(self):
        """Test auto reconnect default values."""
        mapper = LaunchpadMapper()
        assert mapper.auto_reconnect_enabled is False
        # Interval increased from 2.0 to 5.0 to prevent race conditions
        assert mapper.auto_reconnect_interval == 5.0

    def test_repeat_and_long_press_tracking(self):
        """Test key repeat and long press tracking initialized."""
        mapper = LaunchpadMapper()
        assert mapper.active_repeats == {}
        assert mapper.repeat_stop_events == {}
        assert mapper.press_times == {}
        assert mapper.long_press_triggered == {}

    def test_animation_tracking(self):
        """Test animation tracking initialized."""
        mapper = LaunchpadMapper()
        assert mapper.active_animations == []

    def test_grid_notes_defined(self):
        """Test that grid notes are properly defined."""
        assert len(LaunchpadMapper.GRID_NOTES) == 8
        for row in LaunchpadMapper.GRID_NOTES:
            assert len(row) == 8

    def test_control_and_scene_notes_defined(self):
        """Test control and scene notes defined."""
        assert len(LaunchpadMapper.CONTROL_NOTES) == 8
        assert len(LaunchpadMapper.SCENE_NOTES) == 8


class TestLaunchpadMapperMidiBackend:
    """Test MIDI backend management."""

    def test_get_midi_backends(self):
        """Test getting available MIDI backends."""
        mapper = LaunchpadMapper()
        backends = mapper.get_midi_backends()
        assert isinstance(backends, list)
        # Should discover some backends
        assert len(backends) > 0

    def test_get_midi_backend(self):
        """Test getting current MIDI backend."""
        mapper = LaunchpadMapper()
        backend = mapper.get_midi_backend()
        assert isinstance(backend, str)

    def test_set_invalid_midi_backend(self):
        """Test setting invalid MIDI backend."""
        mapper = LaunchpadMapper()
        result = mapper.set_midi_backend('mido.backends.nonexistent')
        assert result.get('success') is False
        assert 'error' in result


class TestLaunchpadMapperLayerManagement:
    """Test layer stack management."""

    def test_current_layer_default(self):
        """Test current layer is base layer initially."""
        mapper = LaunchpadMapper()
        assert mapper.current_layer == mapper.profile.base_layer

    def test_push_layer(self):
        """Test pushing a layer onto the stack."""
        mapper = LaunchpadMapper()
        mapper.push_layer('Alt')
        assert mapper.current_layer == 'Alt'
        assert len(mapper.layer_stack) == 2

    def test_push_multiple_layers(self):
        """Test pushing multiple layers."""
        mapper = LaunchpadMapper()
        mapper.push_layer('Alt')
        mapper.push_layer('Shift')
        assert mapper.current_layer == 'Shift'
        assert len(mapper.layer_stack) == 3

    def test_pop_layer(self):
        """Test popping a layer from the stack."""
        mapper = LaunchpadMapper()
        mapper.push_layer('Alt')
        mapper.pop_layer()
        assert mapper.current_layer == mapper.profile.base_layer
        assert len(mapper.layer_stack) == 1

    def test_pop_layer_at_base(self):
        """Test popping layer when only base layer exists."""
        mapper = LaunchpadMapper()
        mapper.pop_layer()
        # Should not go below base layer
        assert len(mapper.layer_stack) == 1
        assert mapper.current_layer == mapper.profile.base_layer

    def test_set_layer(self):
        """Test setting layer directly."""
        mapper = LaunchpadMapper()
        mapper.push_layer('Alt')
        mapper.push_layer('Shift')
        mapper.set_layer('Custom')
        # set_layer replaces the entire stack
        assert mapper.current_layer == 'Custom'
        assert len(mapper.layer_stack) == 1

    def test_layer_change_callback(self):
        """Test that layer changes trigger callbacks."""
        mapper = LaunchpadMapper()
        events = []
        mapper.add_callback(lambda e: events.append(e))

        mapper.push_layer('Alt')
        assert any(e.get('type') == 'layer_change' for e in events)


class TestLaunchpadMapperProfileManagement:
    """Test profile management."""

    def test_set_profile(self):
        """Test setting a new profile."""
        mapper = LaunchpadMapper()
        new_profile = Profile(name='New', base_layer='Main')
        mapper.set_profile(new_profile)
        assert mapper.profile == new_profile
        assert mapper.layer_stack == ['Main']

    def test_set_profile_triggers_callback(self):
        """Test that setting profile triggers callback."""
        mapper = LaunchpadMapper()
        events = []
        mapper.add_callback(lambda e: events.append(e))

        new_profile = Profile(name='New')
        mapper.set_profile(new_profile)
        assert any(e.get('type') == 'layer_change' for e in events)


class TestLaunchpadMapperCallbacks:
    """Test callback management."""

    def test_add_callback(self):
        """Test adding a callback."""
        mapper = LaunchpadMapper()
        callback = MagicMock()
        mapper.add_callback(callback)
        assert callback in mapper.callbacks

    def test_remove_callback(self):
        """Test removing a callback."""
        mapper = LaunchpadMapper()
        callback = MagicMock()
        mapper.add_callback(callback)
        mapper.remove_callback(callback)
        assert callback not in mapper.callbacks

    def test_remove_nonexistent_callback(self):
        """Test removing callback that doesn't exist."""
        mapper = LaunchpadMapper()
        callback = MagicMock()
        # Should not raise
        mapper.remove_callback(callback)

    def test_notify_layer_change(self):
        """Test layer change notification."""
        mapper = LaunchpadMapper()
        events = []
        mapper.add_callback(lambda e: events.append(e))
        mapper.notify_layer_change()
        assert len(events) == 1
        assert events[0]['type'] == 'layer_change'
        assert events[0]['current_layer'] == mapper.current_layer


class TestLaunchpadMapperVelocityActions:
    """Test velocity-based action handling."""

    def test_get_velocity_action_no_mappings(self):
        """Test velocity action when no velocity mappings defined."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='space', color='green', label='Test'
        )
        action = mapper.get_velocity_action(mapping, 100)
        assert action == 'space'

    def test_get_velocity_action_with_mappings(self):
        """Test velocity action with velocity mappings."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60,
            key_combo='default',
            color='green',
            label='Test',
            velocity_mappings={
                '0-42': 'soft',
                '43-84': 'medium',
                '85-127': 'hard',
            }
        )
        assert mapper.get_velocity_action(mapping, 30) == 'soft'
        assert mapper.get_velocity_action(mapping, 60) == 'medium'
        assert mapper.get_velocity_action(mapping, 100) == 'hard'

    def test_get_velocity_action_boundary_values(self):
        """Test velocity action at boundary values."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60,
            key_combo='default',
            color='green',
            label='Test',
            velocity_mappings={
                '0-63': 'low',
                '64-127': 'high',
            }
        )
        assert mapper.get_velocity_action(mapping, 0) == 'low'
        assert mapper.get_velocity_action(mapping, 63) == 'low'
        assert mapper.get_velocity_action(mapping, 64) == 'high'
        assert mapper.get_velocity_action(mapping, 127) == 'high'

    def test_get_velocity_action_fallback(self):
        """Test velocity action fallback to default."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60,
            key_combo='default',
            color='green',
            label='Test',
            velocity_mappings={
                '50-60': 'narrow',  # Doesn't cover all ranges
            }
        )
        # Velocity outside defined ranges should use default
        assert mapper.get_velocity_action(mapping, 30) == 'default'


class TestLaunchpadMapperEmulation:
    """Test pad press emulation."""

    def test_emulate_pad_press_no_mapping(self):
        """Test emulating press with no mapping."""
        mapper = LaunchpadMapper()
        result = mapper.emulate_pad_press(60)
        assert result.get('success') is False
        assert 'error' in result

    def test_emulate_pad_press_disabled_mapping(self):
        """Test emulating press with disabled mapping."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='space', color='green', label='Test',
            enabled=False
        )
        mapper.profile.add_mapping(mapping)
        result = mapper.emulate_pad_press(60)
        assert result.get('success') is False

    def test_emulate_pad_press_layer_up(self):
        """Test emulating layer up action."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='', color='green', label='Up',
            action='layer_up'
        )
        # Push to Alt layer first, then add mapping to Alt layer
        mapper.push_layer('Alt')
        mapper.profile.add_mapping(mapping, layer='Alt')
        result = mapper.emulate_pad_press(60)
        assert result.get('success') is True
        assert result.get('action') == 'layer_up'
        assert mapper.current_layer == mapper.profile.base_layer
        # Check mapping info is included
        assert result.get('label') == 'Up'
        assert result.get('color') == 'green'

    def test_emulate_pad_press_layer_switch(self):
        """Test emulating layer switch action."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='', color='green', label='Switch',
            action='layer', target_layer='Alt'
        )
        mapper.profile.add_mapping(mapping)
        result = mapper.emulate_pad_press(60)
        assert result.get('success') is True
        assert result.get('action') == 'layer'
        assert mapper.current_layer == 'Alt'
        # Check mapping info is included
        assert result.get('label') == 'Switch'
        assert result.get('target_layer') == 'Alt'

    def test_emulate_pad_press_key_action(self):
        """Test emulating key action (with mocked execute)."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='ctrl+c', color='green', label='Copy'
        )
        mapper.profile.add_mapping(mapping)
        executed = []
        mapper.execute_key_combo = lambda combo: executed.append(combo)
        result = mapper.emulate_pad_press(60)
        assert result.get('success') is True
        assert result.get('action') == 'key'
        assert 'ctrl+c' in executed
        # Check mapping info is included
        assert result.get('label') == 'Copy'
        assert result.get('key_combo') == 'ctrl+c'
        assert result.get('executed_combo') == 'ctrl+c'
        assert result.get('color') == 'green'

    def test_emulate_pad_press_skip_pulse(self):
        """Test emulating with skip_pulse option."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(
            note=60, key_combo='ctrl+c', color='green', label='Copy'
        )
        mapper.profile.add_mapping(mapping)
        executed = []
        mapper.execute_key_combo = lambda combo: executed.append(combo)
        pulsed = []
        mapper.pulse = lambda note, color, duration: pulsed.append(note)

        # With skip_pulse=True (default in API), no pulse
        result = mapper.emulate_pad_press(60, skip_pulse=True)
        assert result.get('success') is True
        assert len(pulsed) == 0

        # With skip_pulse=False, pulse is called
        result = mapper.emulate_pad_press(60, skip_pulse=False)
        assert result.get('success') is True
        assert len(pulsed) == 1


class TestLaunchpadMapperStartStop:
    """Test mapper start/stop functionality."""

    def test_start_without_input_port(self):
        """Test starting mapper without input port."""
        mapper = LaunchpadMapper()
        result = mapper.start()
        assert result is False
        assert mapper.running is False

    def test_start_already_running(self):
        """Test starting when already running."""
        mapper = LaunchpadMapper()
        mapper.running = True
        result = mapper.start()
        assert result is True  # Returns True but doesn't restart

    def test_stop(self):
        """Test stopping the mapper."""
        mapper = LaunchpadMapper()
        mapper.running = True
        mapper.stop()
        assert mapper.running is False


class TestLaunchpadMapperAutoReconnect:
    """Test auto-reconnect functionality."""

    def test_set_auto_reconnect_enable(self):
        """Test enabling auto reconnect."""
        mapper = LaunchpadMapper()
        mapper.set_auto_reconnect(True, 3.0)
        assert mapper.auto_reconnect_enabled is True
        assert mapper.auto_reconnect_interval == 3.0
        # Clean up thread
        mapper.auto_reconnect_stop.set()

    def test_set_auto_reconnect_disable(self):
        """Test disabling auto reconnect."""
        mapper = LaunchpadMapper()
        mapper.set_auto_reconnect(True, 2.0)
        mapper.set_auto_reconnect(False)
        assert mapper.auto_reconnect_enabled is False

    def test_set_auto_reconnect_minimum_interval(self):
        """Test that interval has minimum of 0.5."""
        mapper = LaunchpadMapper()
        mapper.set_auto_reconnect(True, 0.1)  # Below minimum
        assert mapper.auto_reconnect_interval == 0.5
        mapper.auto_reconnect_stop.set()


class TestLaunchpadMapperKeyRepeat:
    """Test key repeat functionality."""

    def test_stop_key_repeat_not_repeating(self):
        """Test stopping repeat when not repeating."""
        mapper = LaunchpadMapper()
        # Should not raise
        mapper.stop_key_repeat(60)

    def test_stop_all_repeats_empty(self):
        """Test stopping all repeats when none active."""
        mapper = LaunchpadMapper()
        # Should not raise
        mapper.stop_all_repeats()


class TestLaunchpadMapperAnimations:
    """Test animation management."""

    def test_stop_all_animations_empty(self):
        """Test stopping animations when none active."""
        mapper = LaunchpadMapper()
        # Should not raise
        mapper.stop_all_animations()
        assert mapper.active_animations == []


class TestLaunchpadMapperGridHelpers:
    """Test grid coordinate helpers."""

    def test_grid_note(self):
        """Test _grid_note helper."""
        mapper = LaunchpadMapper()
        # Top left should be 81
        assert mapper._grid_note(0, 0) == 81
        # Top right should be 88
        assert mapper._grid_note(0, 7) == 88
        # Bottom left should be 11
        assert mapper._grid_note(7, 0) == 11

    def test_has_active_mappings_empty(self):
        """Test _has_active_mappings with empty profile."""
        mapper = LaunchpadMapper()
        assert mapper._has_active_mappings() is False

    def test_has_active_mappings_with_mapping(self):
        """Test _has_active_mappings with mapping."""
        mapper = LaunchpadMapper()
        mapping = PadMapping(note=60, key_combo='a', color='red', label='Test')
        mapper.profile.add_mapping(mapping)
        assert mapper._has_active_mappings() is True


class TestLaunchpadMapperSmileyAnimations:
    """Test smiley animation functionality."""

    def test_get_smiley_faces(self):
        """Test getting smiley face patterns."""
        mapper = LaunchpadMapper()
        faces = mapper._get_smiley_faces()
        assert isinstance(faces, dict)
        assert len(faces) > 0
        # Check expected faces exist
        expected = ['happy', 'wink', 'blink', 'heart_eyes', 'cool',
                   'surprised', 'tongue', 'blush', 'neutral', 'sleepy']
        for face in expected:
            assert face in faces, f"Missing face: {face}"

    def test_get_smiley_face_patterns_have_colors(self):
        """Test that face patterns contain color values."""
        mapper = LaunchpadMapper()
        faces = mapper._get_smiley_faces()
        for name, frame in faces.items():
            assert isinstance(frame, dict), f"{name} should be a dict"
            for note, color in frame.items():
                assert isinstance(note, int), f"{name} note should be int"
                assert isinstance(color, str), f"{name} color should be str"

    def test_get_available_smiley_faces(self):
        """Test getting list of available face names."""
        mapper = LaunchpadMapper()
        faces = mapper.get_available_smiley_faces()
        assert isinstance(faces, list)
        assert 'happy' in faces
        assert 'cool' in faces
        assert 'heart_eyes' in faces

    def test_get_smiley_animation_sequence(self):
        """Test animation sequence format."""
        mapper = LaunchpadMapper()
        sequence = mapper._get_smiley_animation_sequence()
        assert isinstance(sequence, list)
        assert len(sequence) > 0
        for item in sequence:
            assert isinstance(item, tuple)
            assert len(item) == 2
            face_name, duration = item
            assert isinstance(face_name, str)
            assert isinstance(duration, (int, float))
            assert duration > 0

    def test_show_smiley_face_no_output(self):
        """Test showing face without output port."""
        mapper = LaunchpadMapper()
        result = mapper.show_smiley_face('happy')
        assert result.get('success') is False
        assert 'error' in result

    def test_show_smiley_face_invalid(self):
        """Test showing invalid face name."""
        mapper = LaunchpadMapper()
        # Without output port, returns connection error
        result = mapper.show_smiley_face('nonexistent_face')
        assert result.get('success') is False
        # Error could be connection or invalid face depending on check order
        assert 'error' in result

    def test_play_smiley_animation_no_output(self):
        """Test playing animation without output port."""
        mapper = LaunchpadMapper()
        result = mapper.play_smiley_animation()
        assert result.get('success') is False
        assert 'error' in result

    def test_reset_activity(self):
        """Test resetting activity timer."""
        mapper = LaunchpadMapper()
        import time
        old_time = mapper.last_activity_time
        time.sleep(0.01)
        mapper.reset_activity()
        assert mapper.last_activity_time > old_time

    def test_idle_timeout_initialization(self):
        """Test idle timeout is properly initialized."""
        mapper = LaunchpadMapper()
        assert mapper.idle_timeout == 120  # 2 minutes
        assert mapper.last_activity_time > 0
        assert mapper.idle_timeout_thread is None
        assert mapper.idle_timeout_stop is not None
