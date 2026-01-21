#!/usr/bin/env python3
"""Tests for the persistence module."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from persistence import PersistenceManager, get_persistence_dir


class TestPersistenceDir:
    """Tests for get_persistence_dir function."""

    def test_returns_path(self):
        """Test that get_persistence_dir returns a Path."""
        result = get_persistence_dir()
        assert isinstance(result, Path)

    def test_creates_directory(self):
        """Test that directory is created if it doesn't exist."""
        result = get_persistence_dir()
        assert result.exists()
        assert result.is_dir()


class TestPersistenceManager:
    """Tests for PersistenceManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a PersistenceManager with temp directory."""
        return PersistenceManager(temp_dir)

    def test_initialization(self, temp_dir):
        """Test manager initializes correctly."""
        manager = PersistenceManager(temp_dir)
        assert manager.persistence_dir == temp_dir
        assert manager.profiles_path == temp_dir / 'profiles.json'
        assert manager.config_path == temp_dir / 'config.json'

    def test_save_profiles(self, manager, temp_dir):
        """Test saving profiles to disk."""
        profiles = {
            'Default': {
                'name': 'Default',
                'description': 'Test profile',
                'base_layer': 'Base',
                'layers': {'Base': {}}
            }
        }
        result = manager.save_profiles(profiles, 'Default')
        assert result is True
        assert (temp_dir / 'profiles.json').exists()

        # Verify content
        with open(temp_dir / 'profiles.json', 'r') as f:
            data = json.load(f)
        assert data['active_profile'] == 'Default'
        assert 'Default' in data['profiles']

    def test_load_profiles_not_found(self, manager):
        """Test loading profiles when file doesn't exist."""
        result = manager.load_profiles()
        assert result is None

    def test_load_profiles(self, manager, temp_dir):
        """Test loading profiles from disk."""
        # Save first
        profiles = {'Test': {'name': 'Test', 'layers': {}}}
        manager.save_profiles(profiles, 'Test')

        # Load
        result = manager.load_profiles()
        assert result is not None
        assert result['active_profile'] == 'Test'
        assert 'Test' in result['profiles']

    def test_save_config(self, manager, temp_dir):
        """Test saving config to disk."""
        config = {
            'last_input_port': 'Port A',
            'last_output_port': 'Port B',
            'auto_switch_enabled': True
        }
        result = manager.save_config(config)
        assert result is True
        assert (temp_dir / 'config.json').exists()

    def test_load_config(self, manager, temp_dir):
        """Test loading config from disk."""
        config = {'test_key': 'test_value'}
        manager.save_config(config)

        result = manager.load_config()
        assert result is not None
        assert result['test_key'] == 'test_value'

    def test_update_config(self, manager):
        """Test updating config values."""
        manager.save_config({'key1': 'value1'})
        manager.update_config({'key2': 'value2'})

        result = manager.load_config()
        assert result['key1'] == 'value1'
        assert result['key2'] == 'value2'

    def test_get_last_midi_ports(self, manager):
        """Test getting last MIDI ports."""
        manager.save_config({
            'last_input_port': 'Input',
            'last_output_port': 'Output'
        })

        result = manager.get_last_midi_ports()
        assert result['input_port'] == 'Input'
        assert result['output_port'] == 'Output'

    def test_save_last_midi_ports(self, manager):
        """Test saving last MIDI ports."""
        manager.save_last_midi_ports('New Input', 'New Output')

        result = manager.get_last_midi_ports()
        assert result['input_port'] == 'New Input'
        assert result['output_port'] == 'New Output'

    def test_auto_switch_rules(self, manager):
        """Test saving and loading auto-switch rules."""
        rules = [
            {'match': 'Lightroom', 'profile': 'LR Profile'},
            {'match': 'Photoshop', 'profile': 'PS Profile'}
        ]
        manager.save_auto_switch_rules(rules, True)

        result = manager.get_auto_switch_rules()
        assert result == rules

    def test_clear_all(self, manager, temp_dir):
        """Test clearing all persisted data."""
        manager.save_config({'test': 'data'})
        manager.save_profiles({}, 'Default')

        assert (temp_dir / 'config.json').exists()
        assert (temp_dir / 'profiles.json').exists()

        manager.clear_all()

        assert not (temp_dir / 'config.json').exists()
        assert not (temp_dir / 'profiles.json').exists()

    def test_callbacks(self, manager):
        """Test load and save callbacks."""
        load_calls = []
        save_calls = []

        manager.add_load_callback(lambda dt: load_calls.append(dt))
        manager.add_save_callback(lambda dt: save_calls.append(dt))

        manager.save_config({'test': 'data'})
        manager.load_config()

        assert 'config' in save_calls
        assert 'config' in load_calls


class TestScheduledSave:
    """Tests for debounced save functionality."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_schedule_save_debounces(self, temp_dir):
        """Test that scheduled saves are debounced."""
        manager = PersistenceManager(temp_dir)
        manager._save_delay = 0.1  # Short delay for testing

        # Schedule multiple saves rapidly
        for i in range(5):
            manager.schedule_save_profiles({'Profile': {}}, 'Profile')
            time.sleep(0.02)

        # Wait for debounce
        time.sleep(0.2)

        # File should exist
        assert (temp_dir / 'profiles.json').exists()

    def test_flush_pending_saves(self, temp_dir):
        """Test flushing pending saves."""
        manager = PersistenceManager(temp_dir)
        manager._save_delay = 10.0  # Long delay

        manager.schedule_save_profiles({'Profile': {}}, 'Profile')
        manager.flush_pending_saves()

        # Timer should be cancelled
        assert manager._save_timer is None
