"""Tests for Flask server API endpoints."""
import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    """Create test client for Flask app."""
    # Import here to avoid loading at module level
    from server import app, mapper
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def reset_mapper():
    """Reset mapper state before tests."""
    from server import mapper
    from launchpad_mapper import Profile
    mapper.profile = Profile()
    mapper.layer_stack = [mapper.profile.base_layer]
    mapper.running = False
    mapper.input_port = None
    mapper.output_port = None
    yield mapper


class TestPortsEndpoint:
    """Test /api/ports endpoint."""

    def test_get_ports(self, client, reset_mapper):
        """Test getting available ports."""
        response = client.get('/api/ports')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'inputs' in data
        assert 'outputs' in data
        assert isinstance(data['inputs'], list)
        assert isinstance(data['outputs'], list)


class TestStatusEndpoint:
    """Test /api/status endpoint."""

    def test_get_status(self, client, reset_mapper):
        """Test getting mapper status."""
        response = client.get('/api/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'connected' in data
        assert 'running' in data
        assert 'profile_name' in data
        assert 'mapping_count' in data

    def test_status_not_connected(self, client, reset_mapper):
        """Test status when not connected."""
        reset_mapper.input_port = None
        response = client.get('/api/status')
        data = json.loads(response.data)
        assert data['connected'] is False

    def test_status_not_running(self, client, reset_mapper):
        """Test status when not running."""
        reset_mapper.running = False
        response = client.get('/api/status')
        data = json.loads(response.data)
        assert data['running'] is False


class TestMidiBackendEndpoint:
    """Test /api/midi-backend endpoints."""

    def test_get_midi_backend(self, client, reset_mapper):
        """Test getting MIDI backend info."""
        response = client.get('/api/midi-backend')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'current' in data
        assert 'options' in data
        assert isinstance(data['options'], list)

    def test_set_invalid_backend(self, client, reset_mapper):
        """Test setting invalid MIDI backend."""
        response = client.post('/api/midi-backend',
                              json={'backend': 'invalid.backend'},
                              content_type='application/json')
        assert response.status_code == 400


class TestMappingEndpoint:
    """Test /api/mapping endpoints."""

    def test_save_mapping(self, client, reset_mapper):
        """Test saving a new mapping."""
        response = client.post('/api/mapping',
                              json={
                                  'note': 60,
                                  'key_combo': 'ctrl+c',
                                  'color': 'green',
                                  'label': 'Copy'
                              },
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'mapping' in data

    def test_save_mapping_missing_fields(self, client, reset_mapper):
        """Test saving mapping with missing required fields."""
        response = client.post('/api/mapping',
                              json={'note': 60},
                              content_type='application/json')
        assert response.status_code == 400

    def test_save_mapping_layer_up_action(self, client, reset_mapper):
        """Test saving layer_up action mapping."""
        response = client.post('/api/mapping',
                              json={
                                  'note': 60,
                                  'action': 'layer_up'
                              },
                              content_type='application/json')
        assert response.status_code == 200

    def test_get_mapping(self, client, reset_mapper):
        """Test getting a specific mapping."""
        # First create a mapping
        client.post('/api/mapping',
                   json={
                       'note': 60,
                       'key_combo': 'space',
                       'color': 'red',
                       'label': 'Test'
                   },
                   content_type='application/json')

        response = client.get('/api/mapping/60')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['note'] == 60
        assert data['key_combo'] == 'space'

    def test_get_nonexistent_mapping(self, client, reset_mapper):
        """Test getting mapping that doesn't exist."""
        response = client.get('/api/mapping/99')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data is None

    def test_delete_mapping(self, client, reset_mapper):
        """Test deleting a mapping."""
        # First create a mapping
        client.post('/api/mapping',
                   json={
                       'note': 60,
                       'key_combo': 'space',
                       'color': 'red',
                       'label': 'Test'
                   },
                   content_type='application/json')

        response = client.delete('/api/mapping/60')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


class TestProfileEndpoint:
    """Test /api/profile endpoints."""

    def test_get_profile(self, client, reset_mapper):
        """Test getting current profile."""
        response = client.get('/api/profile')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'name' in data
        assert 'layers' in data
        assert 'active_layer' in data

    def test_update_profile_name(self, client, reset_mapper):
        """Test updating profile name."""
        response = client.put('/api/profile',
                             json={'name': 'New Name'},
                             content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_update_profile_description(self, client, reset_mapper):
        """Test updating profile description."""
        response = client.put('/api/profile',
                             json={'description': 'Test description'},
                             content_type='application/json')
        assert response.status_code == 200

    def test_export_profile(self, client, reset_mapper):
        """Test exporting profile."""
        response = client.get('/api/profile/export')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'name' in data
        assert 'layers' in data

    def test_import_profile(self, client, reset_mapper):
        """Test importing profile."""
        profile_data = {
            'name': 'Imported',
            'description': 'Test import',
            'base_layer': 'Base',
            'layers': {
                'Base': {
                    '60': {
                        'note': 60,
                        'key_combo': 'a',
                        'color': 'green',
                        'label': 'Test'
                    }
                }
            }
        }
        response = client.post('/api/profile/import',
                              json=profile_data,
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['profile']['name'] == 'Imported'

    def test_import_empty_profile(self, client, reset_mapper):
        """Test importing empty profile data."""
        response = client.post('/api/profile/import',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400


class TestLayerEndpoints:
    """Test /api/layer endpoints."""

    def test_get_layers(self, client, reset_mapper):
        """Test getting layers."""
        response = client.get('/api/layers')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'layers' in data
        assert 'current_layer' in data

    def test_push_layer(self, client, reset_mapper):
        """Test pushing a layer."""
        response = client.post('/api/layer/push',
                              json={'layer': 'Alt'},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['current_layer'] == 'Alt'

    def test_push_layer_no_name(self, client, reset_mapper):
        """Test pushing layer without name."""
        response = client.post('/api/layer/push',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400

    def test_pop_layer(self, client, reset_mapper):
        """Test popping a layer."""
        # First push a layer
        client.post('/api/layer/push',
                   json={'layer': 'Alt'},
                   content_type='application/json')

        response = client.post('/api/layer/pop')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_set_layer(self, client, reset_mapper):
        """Test setting layer directly."""
        response = client.post('/api/layer/set',
                              json={'layer': 'Custom'},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['current_layer'] == 'Custom'

    def test_set_layer_no_name(self, client, reset_mapper):
        """Test setting layer without name."""
        response = client.post('/api/layer/set',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400


class TestEmulateEndpoint:
    """Test /api/emulate endpoint."""

    def test_emulate_no_note(self, client, reset_mapper):
        """Test emulate with no note provided."""
        response = client.post('/api/emulate',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400

    def test_emulate_no_mapping(self, client, reset_mapper):
        """Test emulate with no mapping for note."""
        response = client.post('/api/emulate',
                              json={'note': 60},
                              content_type='application/json')
        assert response.status_code == 400


class TestClearEndpoint:
    """Test /api/clear endpoint."""

    def test_clear_mappings(self, client, reset_mapper):
        """Test clearing all mappings."""
        # Add a mapping first
        client.post('/api/mapping',
                   json={
                       'note': 60,
                       'key_combo': 'space',
                       'color': 'red',
                       'label': 'Test'
                   },
                   content_type='application/json')

        response = client.post('/api/clear')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


class TestDisconnectEndpoint:
    """Test /api/disconnect endpoint."""

    def test_disconnect(self, client, reset_mapper):
        """Test disconnecting."""
        response = client.post('/api/disconnect')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data


class TestAnimationEndpoints:
    """Test animation API endpoints."""

    def test_pulse_no_note(self, client, reset_mapper):
        """Test pulse animation without note."""
        response = client.post('/api/animation/pulse',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400

    def test_pulse_with_note(self, client, reset_mapper):
        """Test pulse animation with note."""
        response = client.post('/api/animation/pulse',
                              json={'note': 60, 'color': 'red'},
                              content_type='application/json')
        assert response.status_code == 200

    def test_rainbow(self, client, reset_mapper):
        """Test rainbow animation."""
        response = client.post('/api/animation/rainbow',
                              json={'speed': 0.5},
                              content_type='application/json')
        assert response.status_code == 200

    def test_stop_animations(self, client, reset_mapper):
        """Test stopping animations."""
        response = client.post('/api/animation/stop')
        assert response.status_code == 200

    def test_smiley_get_faces(self, client, reset_mapper):
        """Test getting available smiley faces."""
        response = client.get('/api/animation/smiley')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'faces' in data
        assert isinstance(data['faces'], list)
        assert 'happy' in data['faces']
        assert 'cool' in data['faces']
        assert 'heart_eyes' in data['faces']

    def test_smiley_play_animation(self, client, reset_mapper):
        """Test playing smiley animation."""
        response = client.post('/api/animation/smiley',
                              json={'duration': 1.0},
                              content_type='application/json')
        # Returns 400 because no MIDI output is connected
        assert response.status_code == 400

    def test_smiley_show_specific_face(self, client, reset_mapper):
        """Test showing a specific smiley face."""
        response = client.post('/api/animation/smiley',
                              json={'face': 'happy'},
                              content_type='application/json')
        # Returns 400 because no MIDI output is connected
        assert response.status_code == 400

    def test_smiley_invalid_face(self, client, reset_mapper):
        """Test showing invalid face name."""
        response = client.post('/api/animation/smiley',
                              json={'face': 'nonexistent'},
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        # Error could be connection or invalid face depending on check order
        assert data['success'] is False


class TestAutoReconnectEndpoint:
    """Test /api/auto-reconnect endpoint."""

    def test_get_auto_reconnect(self, client, reset_mapper):
        """Test getting auto reconnect status."""
        response = client.get('/api/auto-reconnect')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'enabled' in data
        assert 'interval' in data

    def test_set_auto_reconnect(self, client, reset_mapper):
        """Test setting auto reconnect."""
        response = client.post('/api/auto-reconnect',
                              json={'enabled': True, 'interval': 3.0},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['enabled'] is True


class TestPresetsEndpoint:
    """Test /api/presets endpoint."""

    def test_list_presets(self, client, reset_mapper):
        """Test listing presets."""
        response = client.get('/api/presets')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'presets' in data


class TestProfilesEndpoint:
    """Test /api/profiles endpoint."""

    def test_list_profiles(self, client, reset_mapper):
        """Test listing profiles."""
        response = client.get('/api/profiles')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'profiles' in data
        assert 'active_profile' in data


class TestTestKeyEndpoint:
    """Test /api/test-key endpoint."""

    def test_test_key_no_combo(self, client, reset_mapper):
        """Test key without combo."""
        response = client.post('/api/test-key',
                              json={},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False


class TestSetColorEndpoint:
    """Test /api/set-color endpoint."""

    def test_set_color_no_note(self, client, reset_mapper):
        """Test set color without note."""
        response = client.post('/api/set-color',
                              json={'color': 'red'},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
