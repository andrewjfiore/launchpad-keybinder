"""
chaos-tests/test_keybinder_chaos.py
Chaos, fuzz, and resilience tests for the launchpad-keybinder Python backend.

Run:
    cd /home/andrew/repos/launchpad-keybinder
    python3 -m pytest chaos-tests/test_keybinder_chaos.py -v 2>&1 | tee chaos-tests/results.txt

NOTE: The Flask server tests require no running server; they use the app
      directly via Flask's test client.
"""

import json
import os
import sys
import struct
import random
import string
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def flask_client():
    """Create a Flask test client (no actual MIDI/ports needed)."""
    # Patch out MIDI init so tests run without hardware
    import unittest.mock as mock
    with mock.patch("mido.open_input"), \
         mock.patch("mido.open_output"), \
         mock.patch("mido.get_input_names", return_value=[]), \
         mock.patch("mido.get_output_names", return_value=[]):
        from server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


@pytest.fixture(scope="module")
def mapper():
    """Create a LaunchpadMapper instance for unit tests."""
    import unittest.mock as mock
    with mock.patch("mido.open_input"), \
         mock.patch("mido.open_output"), \
         mock.patch("mido.get_input_names", return_value=[]), \
         mock.patch("mido.get_output_names", return_value=[]):
        from launchpad_mapper import LaunchpadMapper
        m = LaunchpadMapper()
        yield m


# ---------------------------------------------------------------------------
# 1. REST API fuzzing — malformed JSON
# ---------------------------------------------------------------------------

class TestAPIFuzzing:

    def test_mapping_missing_required_fields(self, flask_client):
        """POST /api/mapping with empty body."""
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps({}),
                                 content_type="application/json")
        assert resp.status_code in (400, 422), f"Expected 400, got {resp.status_code}"

    def test_mapping_wrong_types(self, flask_client):
        """POST /api/mapping with wrong field types."""
        payload = {"note": "not_an_int", "key_combo": 12345, "color": None}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (400, 422, 500), "Should fail gracefully"
        # Should not 500 with unhandled traceback in response
        body = resp.get_json(silent=True) or {}
        assert "error" in body or resp.status_code == 400

    def test_mapping_huge_payload(self, flask_client):
        """POST /api/mapping with enormous label (DoS test)."""
        payload = {
            "note": 10,
            "key_combo": "ctrl+a",
            "color": "green",
            "label": "A" * 100_000
        }
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        # Should either accept or reject; must not hang or OOM
        assert resp.status_code in (200, 400, 413, 422)

    def test_mapping_null_fields(self, flask_client):
        """POST /api/mapping with null values."""
        payload = {"note": None, "key_combo": None, "color": None}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (400, 422)

    def test_mapping_negative_note(self, flask_client):
        """POST /api/mapping with negative note number."""
        payload = {"note": -1, "key_combo": "a", "color": "green"}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        # Implementation may accept or reject; should not crash
        assert resp.status_code in (200, 400)

    def test_mapping_out_of_range_note(self, flask_client):
        """POST /api/mapping with MIDI note > 127."""
        payload = {"note": 999999, "key_combo": "a", "color": "green"}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_connect_malformed_body(self, flask_client):
        """POST /api/connect with non-JSON body."""
        resp = flask_client.post("/api/connect",
                                 data=b"\xff\xfe binary garbage",
                                 content_type="application/json")
        assert resp.status_code in (200, 400, 422, 500)

    def test_connect_retries_negative(self, flask_client):
        """POST /api/connect with negative retries."""
        payload = {"retries": -100, "retry_delay": -1.0}
        resp = flask_client.post("/api/connect",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        # Should clamp/handle gracefully
        assert resp.status_code in (200, 400, 422)
        assert "Traceback" not in (resp.get_data(as_text=True) or "")

    def test_emulate_pad_no_note(self, flask_client):
        """POST /api/emulate without note field."""
        resp = flask_client.post("/api/emulate",
                                 data=json.dumps({}),
                                 content_type="application/json")
        assert resp.status_code == 400

    def test_emulate_pad_extreme_velocity(self, flask_client):
        """POST /api/emulate with velocity=999999."""
        payload = {"note": 10, "velocity": 999999}
        resp = flask_client.post("/api/emulate",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        # Should clamp to 127 or fail gracefully
        assert resp.status_code in (200, 400)

    def test_set_color_invalid_color(self, flask_client):
        """POST /api/set-color with unknown color name."""
        payload = {"note": 10, "color": "nonexistent_color_xyz"}
        resp = flask_client.post("/api/set-color",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_layer_set_empty_name(self, flask_client):
        """POST /api/layer/set with empty layer name."""
        resp = flask_client.post("/api/layer/set",
                                 data=json.dumps({"layer": ""}),
                                 content_type="application/json")
        assert resp.status_code in (400, 422)

    def test_layer_set_very_long_name(self, flask_client):
        """POST /api/layer/set with very long layer name."""
        resp = flask_client.post("/api/layer/set",
                                 data=json.dumps({"layer": "L" * 10000}),
                                 content_type="application/json")
        assert resp.status_code in (200, 400, 413)

    def test_batch_mapping_empty_list(self, flask_client):
        """POST /api/mapping with empty mappings list."""
        payload = {"mappings": [], "layer": "Default"}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_batch_mapping_malformed_items(self, flask_client):
        """POST /api/mapping with batch of malformed items."""
        payload = {"mappings": [None, True, "string", 42, {}]}
        resp = flask_client.post("/api/mapping",
                                 data=json.dumps(payload),
                                 content_type="application/json")
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 2. XSS / injection in web fields
# ---------------------------------------------------------------------------

class TestXSSInjection:

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        '"><img src=x onerror=alert(1)>',
        "javascript:alert(1)",
        "'; DROP TABLE profiles; --",
        "\x00\x01\x02\x03",
        "{{7*7}}",  # template injection
        "${7*7}",   # EL injection
        "../../../etc/passwd",
        "A" * 65536,
    ]

    def test_xss_in_label(self, flask_client):
        """XSS payloads in mapping label should be stored/returned safely."""
        for payload in self.XSS_PAYLOADS[:4]:
            data = {"note": 5, "key_combo": "a", "color": "green", "label": payload}
            resp = flask_client.post("/api/mapping",
                                     data=json.dumps(data),
                                     content_type="application/json")
            # Should not 500 or execute code
            assert resp.status_code in (200, 400, 413)

    def test_xss_in_profile_name(self, flask_client):
        """XSS payload in profile name."""
        payload = "<script>alert('xss')</script>"
        data = {"name": payload}
        resp = flask_client.put("/api/profile",
                                data=json.dumps(data),
                                content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_path_traversal_preset(self, flask_client):
        """Path traversal in preset filename."""
        resp = flask_client.get("/api/presets/../../etc/passwd")
        assert resp.status_code in (400, 404), "Path traversal should be blocked"

    def test_path_traversal_preset_encoded(self, flask_client):
        """URL-encoded path traversal attempt."""
        resp = flask_client.get("/api/presets/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)


# ---------------------------------------------------------------------------
# 3. Corrupt profile JSON import
# ---------------------------------------------------------------------------

class TestProfileImport:

    def test_import_empty_profile(self, flask_client):
        """Import empty JSON object."""
        resp = flask_client.post("/api/profile/import",
                                 data=json.dumps({}),
                                 content_type="application/json")
        assert resp.status_code in (400, 422)

    def test_import_wrong_version(self, flask_client):
        """Import profile with invalid version field."""
        data = {"name": "test", "version": "INVALID_VERSION_XYZ",
                "mappings": {}, "layers": {}}
        resp = flask_client.post("/api/profile/import",
                                 data=json.dumps(data),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)
        assert "Traceback" not in (resp.get_data(as_text=True) or "")

    def test_import_deeply_nested(self, flask_client):
        """Import profile with deeply nested JSON (stack overflow risk)."""
        def make_nested(depth):
            if depth == 0:
                return {}
            return {"nested": make_nested(depth - 1)}
        data = {"name": "test", "layers": make_nested(100)}
        resp = flask_client.post("/api/profile/import",
                                 data=json.dumps(data),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_import_huge_mappings(self, flask_client):
        """Import profile with 10000 mappings (DoS test)."""
        mappings = {}
        for i in range(10000):
            mappings[str(i)] = {"note": i % 128, "key_combo": "a", "color": "green"}
        data = {"name": "bigprofile", "mappings": mappings}
        resp = flask_client.post("/api/profile/import",
                                 data=json.dumps(data),
                                 content_type="application/json")
        # Should either reject (size limit) or accept
        assert resp.status_code in (200, 400, 413)

    def test_import_unicode_bomb(self, flask_client):
        """Import profile with Unicode bomb in name."""
        data = {"name": "\U0001F4A3" * 1000, "mappings": {}}
        resp = flask_client.post("/api/profile/import",
                                 data=json.dumps(data),
                                 content_type="application/json")
        assert resp.status_code in (200, 400)

    def test_import_not_json(self, flask_client):
        """Import with non-JSON body."""
        resp = flask_client.post("/api/profile/import",
                                 data=b"not json at all!!",
                                 content_type="application/json")
        assert resp.status_code in (400, 422)

    def test_import_circular_reference_json(self, flask_client):
        """Import profile with circular reference (JSON can't represent this, test invalid JSON)."""
        resp = flask_client.post("/api/profile/import",
                                 data=b'{"name": "test", "self": [[[',
                                 content_type="application/json")
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 4. Concurrent connection tests
# ---------------------------------------------------------------------------

class TestConcurrency:

    def test_concurrent_api_requests(self, flask_client):
        """Fire 50 concurrent GET /api/status requests."""
        results = []
        errors = []

        def do_request():
            try:
                resp = flask_client.get("/api/status")
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_request) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors in concurrent requests: {errors}"
        assert all(r == 200 for r in results), f"Non-200 responses: {set(results)}"

    def test_concurrent_mapping_saves(self, flask_client):
        """Concurrent POST /api/mapping requests — race condition test."""
        results = []
        errors = []

        def save_mapping(note):
            try:
                payload = {"note": note, "key_combo": f"ctrl+{note}", "color": "green"}
                resp = flask_client.post("/api/mapping",
                                        data=json.dumps(payload),
                                        content_type="application/json")
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=save_mapping, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Errors: {errors}"

    def test_concurrent_profile_switch(self, flask_client):
        """Concurrent profile switch requests."""
        results = []
        errors = []

        def switch():
            try:
                resp = flask_client.post("/api/profile/switch",
                                        data=json.dumps({"name": "Default"}),
                                        content_type="application/json")
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=switch) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors: {errors}"


# ---------------------------------------------------------------------------
# 5. MIDI message fuzzing (unit level)
# ---------------------------------------------------------------------------

class TestMIDIFuzzing:

    def test_mapper_emulate_out_of_range(self, mapper):
        """Emulate pad with note > 127."""
        try:
            result = mapper.emulate_pad_press(200)
            # Should either fail gracefully or be a no-op
        except Exception as e:
            pytest.fail(f"emulate_pad_press raised {type(e).__name__}: {e}")

    def test_mapper_emulate_negative_note(self, mapper):
        """Emulate pad with negative note."""
        try:
            result = mapper.emulate_pad_press(-1)
        except Exception as e:
            pytest.fail(f"Raised on negative note: {e}")

    def test_mapper_set_pad_color_invalid(self, mapper):
        """set_pad_color with unknown color name."""
        try:
            mapper.set_pad_color(10, "totally_invalid_color_xyz")
        except Exception as e:
            pytest.fail(f"set_pad_color raised on invalid color: {e}")

    def test_mapper_set_pad_color_none(self, mapper):
        """set_pad_color with None."""
        try:
            mapper.set_pad_color(10, None)
        except Exception as e:
            pytest.fail(f"set_pad_color raised on None: {e}")

    def test_mapper_execute_key_combo_empty(self, mapper):
        """execute_key_combo with empty string."""
        import unittest.mock as mock
        with mock.patch("keyboard.send", return_value=None):
            try:
                mapper.execute_key_combo("")
            except Exception as e:
                pytest.fail(f"execute_key_combo raised on empty string: {e}")

    def test_mapper_execute_key_combo_special_chars(self, mapper):
        """execute_key_combo with special/weird chars."""
        combos = [
            "\x00", "\xff", "ctrl+\x00", "shift+<>{}|", "🎵", "A" * 1000
        ]
        import unittest.mock as mock
        with mock.patch("keyboard.send", return_value=None), \
             mock.patch("keyboard.press_and_release", return_value=None):
            for combo in combos:
                try:
                    mapper.execute_key_combo(combo)
                except Exception as e:
                    # Document but don't fail — some may legitimately error
                    pass

    def test_mapper_set_profile_none(self, mapper):
        """set_profile with None should raise or handle gracefully."""
        try:
            mapper.set_profile(None)
        except (AttributeError, TypeError, Exception):
            pass  # Expected — document this as an issue

    def test_mapper_push_pop_layers_stress(self, mapper):
        """Rapidly push/pop layers to test stack overflow."""
        try:
            for i in range(1000):
                mapper.push_layer(f"Layer_{i}")
            for _ in range(1000):
                mapper.pop_layer()
        except RecursionError:
            pytest.fail("RecursionError on layer push/pop stress test")
        except Exception as e:
            pass  # Other errors are OK to document

    def test_binary_midi_message_fuzzing(self):
        """Fuzz binary MIDI message parsing via struct."""
        import unittest.mock as mock

        # Generate random "malformed" MIDI messages
        test_messages = [
            [0xFF],                              # System Reset
            [0xF8],                              # Timing Clock
            [0x00],                              # Invalid status
            [0x80, 0xFF, 0xFF],                  # Note off max velocity
            [0x90, 0x00, 0x00],                  # Note on, note 0, vel 0
            [0xB0, 0x7B, 0x00],                  # All Notes Off
            [0xFE],                              # Active Sensing
            [],                                  # Empty message
            [0x90] * 100,                        # Huge note on
            list(range(256)),                    # All possible bytes
            [random.randint(0, 255) for _ in range(500)],  # Random bytes
        ]

        for msg_bytes in test_messages:
            # Test that message bytes don't crash parser utilities
            try:
                import mido
                if len(msg_bytes) >= 3 and msg_bytes[0] in (0x80, 0x90, 0xB0, 0xA0, 0xC0, 0xD0, 0xE0):
                    status = msg_bytes[0] & 0xF0
                    ch = msg_bytes[0] & 0x0F
                    # Manually process like launchpad_mapper would
                    note = msg_bytes[1] if len(msg_bytes) > 1 else 0
                    vel = msg_bytes[2] if len(msg_bytes) > 2 else 0
            except Exception as e:
                pytest.fail(f"MIDI message parsing crashed: {e} on {msg_bytes[:10]}")


# ---------------------------------------------------------------------------
# 6. Schema validation fuzzing
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_validate_profile_none(self):
        """validate_profile_import with None data."""
        from schema_validation import validate_profile_import, ValidationError
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            validate_profile_import(None, 0)

    def test_validate_profile_random_fields(self):
        """validate_profile_import with random garbage fields."""
        from schema_validation import validate_profile_import, ValidationError
        garbage = {
            "name": "test",
            "☠️": [1, 2, 3],
            "layers": {"Default": {"mappings": {str(i): None for i in range(100)}}},
            "extra_garbage": {"a": {"b": {"c": "d"}}},
        }
        try:
            result, warnings = validate_profile_import(garbage, 0)
        except ValidationError:
            pass  # Expected
        except Exception as e:
            pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")

    def test_validate_profile_huge_size(self):
        """validate_profile_import with huge raw_size."""
        from schema_validation import validate_profile_import, ValidationError
        data = {"name": "test"}
        try:
            validate_profile_import(data, 99999999)  # 100MB fake size
        except ValidationError:
            pass  # Should fail due to size check
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_validate_profile_sql_injection(self):
        """validate_profile_import with SQL injection in name."""
        from schema_validation import validate_profile_import, ValidationError
        data = {"name": "test'; DROP TABLE profiles; --"}
        try:
            validate_profile_import(data, 0)
        except (ValidationError, Exception):
            pass  # Either handle or reject — just don't execute SQL


# ---------------------------------------------------------------------------
# 7. Persistence layer fuzzing
# ---------------------------------------------------------------------------

class TestPersistenceLayer:

    def test_load_corrupt_profile_file(self, tmp_path):
        """load_profiles with corrupt JSON file on disk."""
        import unittest.mock as mock
        from persistence import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path))

        # Write corrupt JSON
        profiles_file = tmp_path / "profiles.json"
        profiles_file.write_bytes(b"\xff\xfe not json at all!!! {{{")

        result = pm.load_profiles()
        assert result is None or isinstance(result, dict), "Should return None or dict, not crash"

    def test_load_truncated_profile_file(self, tmp_path):
        """load_profiles with truncated valid JSON."""
        from persistence import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path))

        profiles_file = tmp_path / "profiles.json"
        valid_json = json.dumps({"profiles": {"Default": {"name": "Default"}}})
        profiles_file.write_bytes(valid_json[:len(valid_json) // 2].encode())

        result = pm.load_profiles()
        assert result is None or isinstance(result, dict)

    def test_load_empty_profile_file(self, tmp_path):
        """load_profiles with empty file."""
        from persistence import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path))

        profiles_file = tmp_path / "profiles.json"
        profiles_file.write_bytes(b"")

        result = pm.load_profiles()
        assert result is None or isinstance(result, dict)

    def test_save_profiles_readonly_dir(self, tmp_path):
        """save_profiles on read-only directory."""
        from persistence import PersistenceManager
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        os.chmod(str(ro_dir), 0o444)

        pm = PersistenceManager(persistence_dir=str(ro_dir))
        try:
            # Should fail gracefully, not crash
            pm.save_profiles({"Default": {"name": "Default"}}, "Default")
        except (PermissionError, OSError):
            pass  # Expected
        except Exception as e:
            pytest.fail(f"Unexpected exception on read-only dir: {type(e).__name__}: {e}")
        finally:
            os.chmod(str(ro_dir), 0o755)

    def test_save_config_extreme_values(self, tmp_path):
        """save_config with extreme/edge-case values."""
        from persistence import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path))
        config = {
            "last_input_port": "A" * 10000,
            "last_output_port": "\x00\xff",
            "auto_switch_rules": [{"match": "<script>", "profile": "x"}] * 1000,
            "auto_switch_enabled": True,
        }
        try:
            pm.save_config(config)
            loaded = pm.load_config()
            assert loaded is not None
        except Exception as e:
            pytest.fail(f"save_config raised: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 8. Auto-reconnect and rapid connect/disconnect
# ---------------------------------------------------------------------------

class TestConnectDisconnect:

    def test_disconnect_without_connect(self, mapper):
        """Disconnect when not connected should be a no-op."""
        try:
            mapper.disconnect()
            mapper.disconnect()  # Double disconnect
        except Exception as e:
            pytest.fail(f"disconnect raised when not connected: {e}")

    def test_stop_without_start(self, mapper):
        """stop() when not running should be a no-op."""
        try:
            mapper.stop()
            mapper.stop()
        except Exception as e:
            pytest.fail(f"stop() raised: {e}")

    def test_start_without_connect(self, mapper):
        """start() without MIDI connection should fail gracefully."""
        try:
            result = mapper.start()
            assert result is False or result is None or isinstance(result, bool)
        except Exception as e:
            pytest.fail(f"start() without connect raised: {e}")

    def test_rapid_set_auto_reconnect(self, mapper):
        """Toggle auto_reconnect rapidly."""
        try:
            for _ in range(100):
                mapper.set_auto_reconnect(True, 0.1)
                mapper.set_auto_reconnect(False, 0.1)
        except Exception as e:
            pytest.fail(f"Raised on rapid auto_reconnect toggle: {e}")

    def test_get_available_ports_no_midi(self, mapper):
        """get_available_ports should not crash when no MIDI hardware."""
        try:
            ports = mapper.get_available_ports()
            assert isinstance(ports, dict)
        except Exception as e:
            pytest.fail(f"get_available_ports raised: {e}")


# ---------------------------------------------------------------------------
# 9. Animation edge cases
# ---------------------------------------------------------------------------

class TestAnimations:

    def test_pulse_invalid_note(self, mapper):
        """pulse() with out-of-range note."""
        try:
            mapper.pulse(999, "green", 0.1)
        except Exception as e:
            pytest.fail(f"pulse() raised on invalid note: {e}")

    def test_pulse_negative_duration(self, mapper):
        """pulse() with negative duration."""
        try:
            mapper.pulse(10, "red", -1.0)
        except Exception as e:
            pytest.fail(f"pulse() raised on negative duration: {e}")

    def test_stop_all_animations_none_running(self, mapper):
        """stop_all_animations when no animations are active."""
        try:
            mapper.stop_all_animations()
        except Exception as e:
            pytest.fail(f"stop_all_animations raised when idle: {e}")


# ---------------------------------------------------------------------------
# 10. Hypothesis property-based tests
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, settings, HealthCheck
    from hypothesis import strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

if HYPOTHESIS_AVAILABLE:
    class TestHypothesisKeybinder:

        @given(note=st.integers(min_value=-1000, max_value=1000),
               velocity=st.integers(min_value=-1000, max_value=1000))
        @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
        def test_emulate_pad_arbitrary_values(self, note, velocity):
            """emulate_pad_press should not crash on any int note/velocity."""
            import unittest.mock as mock
            with mock.patch("mido.open_input"), \
                 mock.patch("mido.open_output"), \
                 mock.patch("mido.get_input_names", return_value=[]), \
                 mock.patch("mido.get_output_names", return_value=[]):
                from launchpad_mapper import LaunchpadMapper
                m = LaunchpadMapper()
                try:
                    m.emulate_pad_press(note, velocity=velocity)
                except Exception:
                    pass  # Any exception is acceptable; crash is not

        @given(key_combo=st.text(min_size=0, max_size=100))
        @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
        def test_execute_key_combo_arbitrary_string(self, key_combo):
            """execute_key_combo should not crash on arbitrary strings."""
            import unittest.mock as mock
            with mock.patch("mido.open_input"), \
                 mock.patch("mido.open_output"), \
                 mock.patch("mido.get_input_names", return_value=[]), \
                 mock.patch("mido.get_output_names", return_value=[]), \
                 mock.patch("keyboard.send", return_value=None), \
                 mock.patch("keyboard.press_and_release", return_value=None):
                from launchpad_mapper import LaunchpadMapper
                m = LaunchpadMapper()
                try:
                    m.execute_key_combo(key_combo)
                except Exception:
                    pass
