"""Tests for Profile class."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launchpad_mapper import Profile, PadMapping


class TestProfileCreation:
    """Test Profile creation and initialization."""

    def test_create_default_profile(self):
        """Test creating profile with defaults."""
        profile = Profile()
        assert profile.name == 'Default'
        assert profile.base_layer == 'Base'
        assert profile.description == ''
        assert 'Base' in profile.layers
        assert len(profile.layers['Base']) == 0

    def test_create_named_profile(self):
        """Test creating profile with custom name."""
        profile = Profile(name='My Profile')
        assert profile.name == 'My Profile'
        assert profile.base_layer == 'Base'

    def test_create_profile_custom_base_layer(self):
        """Test creating profile with custom base layer."""
        profile = Profile(name='Test', base_layer='Main')
        assert profile.base_layer == 'Main'
        assert 'Main' in profile.layers


class TestProfileMappingManagement:
    """Test Profile mapping CRUD operations."""

    def test_add_mapping_to_base_layer(self):
        """Test adding mapping to base layer."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping)
        assert 60 in profile.layers['Base']
        assert profile.layers['Base'][60] == mapping

    def test_add_mapping_to_specific_layer(self):
        """Test adding mapping to specific layer."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping, layer='Alt')
        assert 'Alt' in profile.layers
        assert 60 in profile.layers['Alt']
        assert 60 not in profile.layers['Base']

    def test_overwrite_mapping(self):
        """Test overwriting existing mapping."""
        profile = Profile()
        mapping1 = PadMapping(note=60, key_combo='a', color='red', label='First')
        mapping2 = PadMapping(note=60, key_combo='b', color='blue', label='Second')
        profile.add_mapping(mapping1)
        profile.add_mapping(mapping2)
        assert profile.layers['Base'][60].key_combo == 'b'
        assert profile.layers['Base'][60].color == 'blue'

    def test_remove_mapping(self):
        """Test removing a mapping."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping)
        assert 60 in profile.layers['Base']
        profile.remove_mapping(60)
        assert 60 not in profile.layers['Base']

    def test_remove_mapping_from_specific_layer(self):
        """Test removing mapping from specific layer."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping, layer='Alt')
        profile.remove_mapping(60, layer='Alt')
        assert 60 not in profile.layers.get('Alt', {})

    def test_remove_nonexistent_mapping(self):
        """Test removing mapping that doesn't exist (should not raise)."""
        profile = Profile()
        # Should not raise an exception
        profile.remove_mapping(60)
        profile.remove_mapping(60, layer='NonexistentLayer')

    def test_get_mapping(self):
        """Test retrieving a mapping."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping)
        retrieved = profile.get_mapping(60)
        assert retrieved == mapping

    def test_get_mapping_from_specific_layer(self):
        """Test retrieving mapping from specific layer."""
        profile = Profile()
        base_mapping = PadMapping(note=60, key_combo='a', color='red', label='Base')
        alt_mapping = PadMapping(note=60, key_combo='b', color='blue', label='Alt')
        profile.add_mapping(base_mapping, layer='Base')
        profile.add_mapping(alt_mapping, layer='Alt')

        assert profile.get_mapping(60, layer='Base').key_combo == 'a'
        assert profile.get_mapping(60, layer='Alt').key_combo == 'b'

    def test_get_nonexistent_mapping(self):
        """Test retrieving mapping that doesn't exist."""
        profile = Profile()
        assert profile.get_mapping(60) is None
        assert profile.get_mapping(60, layer='NonexistentLayer') is None

    def test_get_layer_mappings(self):
        """Test getting all mappings for a layer."""
        profile = Profile()
        mapping1 = PadMapping(note=60, key_combo='a', color='red', label='M1')
        mapping2 = PadMapping(note=61, key_combo='b', color='blue', label='M2')
        profile.add_mapping(mapping1)
        profile.add_mapping(mapping2)

        mappings = profile.get_layer_mappings()
        assert len(mappings) == 2
        assert 60 in mappings
        assert 61 in mappings

    def test_get_layer_mappings_empty_layer(self):
        """Test getting mappings for empty layer."""
        profile = Profile()
        mappings = profile.get_layer_mappings('NonexistentLayer')
        assert mappings == {}


class TestProfileLayerManagement:
    """Test Profile layer management."""

    def test_ensure_layer_creates_new(self):
        """Test ensure_layer creates new layer if needed."""
        profile = Profile()
        assert 'Custom' not in profile.layers
        profile.ensure_layer('Custom')
        assert 'Custom' in profile.layers
        assert profile.layers['Custom'] == {}

    def test_ensure_layer_preserves_existing(self):
        """Test ensure_layer preserves existing layer."""
        profile = Profile()
        mapping = PadMapping(note=60, key_combo='a', color='red', label='Test')
        profile.add_mapping(mapping, layer='Custom')
        profile.ensure_layer('Custom')
        assert 60 in profile.layers['Custom']

    def test_multiple_layers(self):
        """Test profile with multiple layers."""
        profile = Profile()
        m1 = PadMapping(note=60, key_combo='a', color='red', label='Base60')
        m2 = PadMapping(note=60, key_combo='b', color='blue', label='Alt60')
        m3 = PadMapping(note=61, key_combo='c', color='green', label='Shift61')

        profile.add_mapping(m1, layer='Base')
        profile.add_mapping(m2, layer='Alt')
        profile.add_mapping(m3, layer='Shift')

        assert len(profile.layers) == 3
        assert profile.get_mapping(60, 'Base').key_combo == 'a'
        assert profile.get_mapping(60, 'Alt').key_combo == 'b'
        assert profile.get_mapping(61, 'Shift').key_combo == 'c'


class TestProfileSerialization:
    """Test Profile serialization to/from dict."""

    def test_to_dict_empty_profile(self):
        """Test converting empty profile to dict."""
        profile = Profile(name='Test')
        profile.description = 'Test Description'
        data = profile.to_dict()
        assert data['name'] == 'Test'
        assert data['description'] == 'Test Description'
        assert data['base_layer'] == 'Base'
        assert 'layers' in data
        assert 'Base' in data['layers']

    def test_to_dict_with_mappings(self):
        """Test converting profile with mappings to dict."""
        profile = Profile(name='Test')
        mapping = PadMapping(note=60, key_combo='space', color='green', label='Test')
        profile.add_mapping(mapping)

        data = profile.to_dict()
        assert '60' in data['layers']['Base']
        assert data['layers']['Base']['60']['key_combo'] == 'space'

    def test_from_dict_complete(self, sample_profile_dict):
        """Test creating profile from complete dict."""
        profile = Profile.from_dict(sample_profile_dict)
        assert profile.name == 'Test Profile'
        assert profile.description == 'A test profile'
        assert profile.base_layer == 'Base'
        assert len(profile.layers) == 2
        assert 60 in profile.layers['Base']
        assert profile.get_mapping(60, 'Base').key_combo == 'ctrl+c'

    def test_from_dict_minimal(self):
        """Test creating profile from minimal dict."""
        data = {'name': 'Minimal'}
        profile = Profile.from_dict(data)
        assert profile.name == 'Minimal'
        assert profile.base_layer == 'Base'

    def test_from_dict_legacy_format(self):
        """Test creating profile from legacy format (mappings dict instead of layers)."""
        data = {
            'name': 'Legacy',
            'mappings': {
                '60': {
                    'note': 60,
                    'key_combo': 'space',
                    'color': 'green',
                    'label': 'Test',
                }
            }
        }
        profile = Profile.from_dict(data)
        assert profile.name == 'Legacy'
        assert 60 in profile.layers['Base']

    def test_from_dict_note_in_key(self):
        """Test handling note not in mapping dict but in key."""
        data = {
            'name': 'Test',
            'layers': {
                'Base': {
                    '60': {
                        'key_combo': 'space',
                        'color': 'green',
                        'label': 'Test',
                        # note field missing, should be inferred from key
                    }
                }
            }
        }
        profile = Profile.from_dict(data)
        mapping = profile.get_mapping(60)
        assert mapping is not None
        assert mapping.note == 60

    def test_round_trip(self):
        """Test that to_dict -> from_dict preserves data."""
        original = Profile(name='RoundTrip', base_layer='Main')
        original.description = 'Test round trip'
        m1 = PadMapping(note=60, key_combo='a', color='red', label='M1')
        m2 = PadMapping(note=61, key_combo='b', color='blue', label='M2',
                       repeat_enabled=True, long_press_enabled=True)
        original.add_mapping(m1, layer='Main')
        original.add_mapping(m2, layer='Alt')

        data = original.to_dict()
        restored = Profile.from_dict(data)

        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.base_layer == original.base_layer
        assert restored.get_mapping(60, 'Main').key_combo == 'a'
        assert restored.get_mapping(61, 'Alt').repeat_enabled is True
        assert restored.get_mapping(61, 'Alt').long_press_enabled is True
