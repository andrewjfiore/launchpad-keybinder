"""Shared pytest fixtures for launchpad-keybinder tests."""
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Use a dedicated temp dir for persistence during tests (avoids APPDATA / sandbox issues)
_test_persistence_dir = tempfile.mkdtemp(prefix="launchpad_mapper_test_")
os.environ["LAUNCHPAD_MAPPER_DATA_DIR"] = _test_persistence_dir

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock keyboard module before imports since it requires root on Linux
mock_keyboard_module = MagicMock()
mock_keyboard_module.send = MagicMock()
sys.modules['keyboard'] = mock_keyboard_module

# Mock pynput since it may not be available
mock_pynput = MagicMock()
sys.modules['pynput'] = mock_pynput
sys.modules['pynput.keyboard'] = MagicMock()

# Mock pygetwindow since it may not be available
mock_pygetwindow = MagicMock()
mock_pygetwindow.getActiveWindow = MagicMock(return_value=None)
sys.modules['pygetwindow'] = mock_pygetwindow


@pytest.fixture
def mock_mido():
    """Mock mido module to avoid requiring actual MIDI hardware."""
    with patch.dict('sys.modules', {
        'mido': MagicMock(),
        'mido.backends': MagicMock(),
    }):
        yield


@pytest.fixture
def mock_keyboard():
    """Mock keyboard module to avoid actual key sending."""
    with patch('keyboard.send') as mock_send:
        yield mock_send


@pytest.fixture
def sample_mapping_dict():
    """Return sample mapping data as dict."""
    return {
        'note': 60,
        'key_combo': 'ctrl+c',
        'color': 'green',
        'label': 'Copy',
        'enabled': True,
        'action': 'key',
        'target_layer': None,
        'repeat_enabled': False,
        'repeat_delay': 0.5,
        'repeat_interval': 0.05,
        'macro_steps': None,
        'velocity_mappings': None,
        'long_press_enabled': False,
        'long_press_action': '',
        'long_press_threshold': 0.5,
    }


@pytest.fixture
def sample_profile_dict():
    """Return sample profile data as dict."""
    return {
        'name': 'Test Profile',
        'description': 'A test profile',
        'base_layer': 'Base',
        'layers': {
            'Base': {
                '60': {
                    'note': 60,
                    'key_combo': 'ctrl+c',
                    'color': 'green',
                    'label': 'Copy',
                    'enabled': True,
                    'action': 'key',
                },
                '61': {
                    'note': 61,
                    'key_combo': 'ctrl+v',
                    'color': 'blue',
                    'label': 'Paste',
                    'enabled': True,
                    'action': 'key',
                },
            },
            'Alt': {
                '60': {
                    'note': 60,
                    'key_combo': 'ctrl+x',
                    'color': 'red',
                    'label': 'Cut',
                    'enabled': True,
                    'action': 'key',
                },
            },
        },
    }


@pytest.fixture
def mock_midi_port():
    """Create a mock MIDI port."""
    port = MagicMock()
    port.name = "Test MIDI Port"
    port.iter_pending.return_value = []
    return port


@pytest.fixture
def mock_launchpad_port():
    """Create a mock Launchpad MIDI port."""
    port = MagicMock()
    port.name = "Launchpad Mini MK3 MIDI 1"
    port.iter_pending.return_value = []
    return port
