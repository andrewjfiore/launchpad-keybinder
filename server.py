#!/usr/bin/env python3
"""
Web server for Launchpad Mapper configuration interface.
"""

import atexit
import glob
import json
import os
import queue
import tempfile
import threading
import time
from flask import Flask, render_template, jsonify, request, Response, send_file
from flask_cors import CORS

from launchpad_mapper import (
    LaunchpadMapper, Profile, PadMapping,
    LAUNCHPAD_COLORS, COLOR_HEX,
    PulseAnimation, ProgressBarAnimation, RainbowCycleAnimation
)
from persistence import get_persistence_manager, PersistenceManager
from schema_validation import validate_profile_import, ValidationError

try:
    import pygetwindow
except ImportError:
    pygetwindow = None


app = Flask(__name__)
CORS(app)

LOG_PATH = os.path.join(tempfile.gettempdir(), "launchpad_mapper.log")

# Global mapper instance
mapper = LaunchpadMapper()
profiles = {mapper.profile.name: mapper.profile}
profile_lock = threading.Lock()
auto_switch_lock = threading.Lock()
auto_switch_rules = []
auto_switch_enabled = False
mapper.set_auto_reconnect(True, 2.0)

# Persistence manager
persistence = get_persistence_manager()


def load_persisted_state():
    """Load profiles and config from disk on startup."""
    global profiles, auto_switch_rules, auto_switch_enabled

    # Load profiles
    profiles_data = persistence.load_profiles()
    if profiles_data:
        with profile_lock:
            profiles.clear()
            for name, profile_dict in profiles_data.get('profiles', {}).items():
                try:
                    profile = Profile.from_dict(profile_dict)
                    profiles[profile.name] = profile
                except Exception as e:
                    print(f"Error loading profile '{name}': {e}")

            # Set active profile
            active_name = profiles_data.get('active_profile')
            if active_name and active_name in profiles:
                mapper.set_profile(profiles[active_name])
                print(f"Restored active profile: {active_name}")
            elif profiles:
                # Use first available profile
                first_profile = next(iter(profiles.values()))
                mapper.set_profile(first_profile)

    # Load config
    config = persistence.load_config()
    if config:
        # Restore auto-switch settings
        with auto_switch_lock:
            auto_switch_rules[:] = config.get('auto_switch_rules', [])
            auto_switch_enabled = config.get('auto_switch_enabled', False)

        # Restore last MIDI ports (will be used on auto-reconnect)
        last_input = config.get('last_input_port')
        last_output = config.get('last_output_port')
        if last_input:
            mapper.last_input_port = last_input
        if last_output:
            mapper.last_output_port = last_output

        print(f"Config restored: auto_switch={auto_switch_enabled}, "
              f"last_ports=({last_input}, {last_output})")


def save_profiles_async():
    """Save profiles to disk (debounced)."""
    with profile_lock:
        persistence.schedule_save_profiles(
            {name: p.to_dict() for name, p in profiles.items()},
            mapper.profile.name
        )


def save_config_async():
    """Save config to disk."""
    with auto_switch_lock:
        config = {
            'last_input_port': mapper.last_input_port,
            'last_output_port': mapper.last_output_port,
            'auto_switch_rules': auto_switch_rules,
            'auto_switch_enabled': auto_switch_enabled,
        }
    persistence.save_config(config)


# Load persisted state on startup
load_persisted_state()

# Event queue for server-sent events
event_queues = []
event_queues_lock = threading.Lock()


def append_log(message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


with open(LOG_PATH, "a", encoding="utf-8") as _handle:
    _handle.write("")
append_log("Server initialized")


def broadcast_event(data):
    """Broadcast an event to all connected clients."""
    with event_queues_lock:
        for q in list(event_queues):
            try:
                q.put_nowait(data)
            except queue.Full:
                pass


def event_callback(data):
    """Callback for MIDI events."""
    broadcast_event(data)


# Register the callback
mapper.add_callback(event_callback)


def request_shutdown():
    shutdown_fn = request.environ.get('werkzeug.server.shutdown')
    if shutdown_fn:
        shutdown_fn()


@app.route('/')
def index():
    return render_template('index.html',
        colors=json.dumps(LAUNCHPAD_COLORS),
        color_hex=json.dumps(COLOR_HEX)
    )


def get_active_window_title():
    if not pygetwindow:
        return None
    try:
        window = pygetwindow.getActiveWindow()
        if window:
            return window.title or ""
    except Exception:
        return None
    return None


def switch_profile(name: str) -> bool:
    with profile_lock:
        profile = profiles.get(name)
        if not profile:
            return False
        mapper.set_profile(profile)
        return True


def auto_switch_worker():
    last_profile = None
    while True:
        time.sleep(1)
        with auto_switch_lock:
            enabled = auto_switch_enabled
            rules = list(auto_switch_rules)
        if not enabled or not rules:
            continue
        title = get_active_window_title()
        if not title:
            continue
        title_lower = title.lower()
        target_profile = None
        for rule in rules:
            if rule["match"].lower() in title_lower:
                target_profile = rule["profile"]
                break
        if target_profile and target_profile != last_profile:
            if switch_profile(target_profile):
                last_profile = target_profile


@app.route('/api/ports')
def get_ports():
    """Get available MIDI ports."""
    return jsonify(mapper.get_available_ports())


@app.route('/api/logs/download')
def download_logs():
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "a", encoding="utf-8"):
            pass
        append_log("Log download requested with no log file present")
    return send_file(LOG_PATH, as_attachment=True, download_name="launchpad_mapper.log")


@app.route('/api/logs/click', methods=['POST'])
def log_click():
    data = request.json or {}
    label = data.get("label", "")
    target_id = data.get("id", "")
    tag = data.get("tag", "")
    append_log(f"Click: label={label} id={target_id} tag={tag}")
    return jsonify({"success": True})


@app.route('/api/emulate', methods=['POST'])
def emulate_pad():
    data = request.json or {}
    note = data.get("note")
    if note is None:
        return jsonify({"success": False, "error": "No note provided"}), 400
    # skip_pulse defaults to True to prevent MIDI sounds during emulation
    skip_pulse = data.get("skip_pulse", True)
    result = mapper.emulate_pad_press(int(note), skip_pulse=skip_pulse)
    append_log(f"Emulate pad: note={note}, success={result.get('success')}, label={result.get('label')}")
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to MIDI ports."""
    data = request.json or {}
    retries = data.get('retries', 3)
    retry_delay = data.get('retry_delay', 0.5)
    try:
        retries = max(1, int(retries))
    except (TypeError, ValueError):
        retries = 3
    try:
        retry_delay = max(0.1, float(retry_delay))
    except (TypeError, ValueError):
        retry_delay = 0.5
    result = mapper.connect(
        data.get('input_port'),
        data.get('output_port'),
        retries=retries,
        retry_delay=retry_delay,
    )
    mapper.set_auto_reconnect(True, 2.0)
    append_log(
        "Connect request: "
        f"input={data.get('input_port')}, output={data.get('output_port')}, "
        f"success={result.get('success')}, error={result.get('error')}"
    )

    # Save last used ports to config
    if result.get("success"):
        save_config_async()

    return jsonify({
        "connected": result.get("success", False),
        "message": result.get("message", "Unknown error"),
        "error": result.get("error"),
        "errors": result.get("errors"),
        "attempt": result.get("attempt"),
    })


@app.route('/api/auto-reconnect', methods=['GET', 'POST'])
def auto_reconnect():
    if request.method == 'GET':
        return jsonify({
            "enabled": mapper.auto_reconnect_enabled,
            "interval": mapper.auto_reconnect_interval,
        })
    data = request.json or {}
    enabled = bool(data.get('enabled', True))
    interval = data.get('interval', 2.0)
    try:
        interval = max(0.5, float(interval))
    except (TypeError, ValueError):
        interval = 2.0
    mapper.set_auto_reconnect(enabled, interval)
    return jsonify({
        "enabled": mapper.auto_reconnect_enabled,
        "interval": mapper.auto_reconnect_interval,
    })


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from MIDI ports."""
    mapper.disconnect()
    append_log("Disconnected from MIDI ports")
    return jsonify({"message": "Disconnected"})


@app.route('/api/start', methods=['POST'])
def start():
    """Start the mapper."""
    success = mapper.start()
    append_log(f"Mapper start requested (success={success})")
    return jsonify({
        "started": success,
        "message": "Mapper started" if success else "Failed to start - is MIDI connected?"
    })


@app.route('/api/stop', methods=['POST'])
def stop():
    """Stop the mapper."""
    mapper.stop()
    append_log("Mapper stopped")
    return jsonify({"message": "Mapper stopped"})


@app.route('/api/status')
def status():
    """Get current mapper status."""
    return jsonify({
        "connected": mapper.input_port is not None,
        "running": mapper.running,
        "profile_name": mapper.profile.name,
        "mapping_count": len(mapper.profile.get_layer_mappings(mapper.current_layer)),
        "input": getattr(mapper.input_port, 'name', None) if mapper.input_port else None,
        "output": getattr(mapper.output_port, 'name', None) if mapper.output_port else None,
    })


@app.route('/api/midi-backend')
def get_backend():
    """Get the current MIDI backend."""
    return jsonify({
        "backend": os.environ.get("MIDO_BACKEND", "mido.backends.rtmidi"),
        "available": mapper.get_midi_backends()
    })


@app.route('/api/set-backend', methods=['POST'])
def set_backend():
    """Set the MIDI backend (requires server restart to take effect)."""
    data = request.json or {}
    backend = data.get('backend')
    if not backend:
        return jsonify({"success": False, "error": "No backend provided"}), 400
    result = mapper.set_midi_backend(backend)
    if result.get("success"):
        os.environ["MIDO_BACKEND"] = backend
        append_log(f"MIDI backend set to: {backend}")
    return jsonify(result)


@app.route('/api/diagnostics')
def diagnostics():
    """Get diagnostic information about MIDI state."""
    import mido
    return jsonify({
        "backend": os.environ.get("MIDO_BACKEND", "mido.backends.rtmidi"),
        "inputs": list(mido.get_input_names()),
        "outputs": list(mido.get_output_names()),
        "connected": mapper.input_port is not None,
        "device": getattr(mapper, 'device_type', None),
        "input_port": getattr(mapper.input_port, 'name', None) if mapper.input_port else None,
        "output_port": getattr(mapper.output_port, 'name', None) if mapper.output_port else None,
    })


@app.route('/api/mapping', methods=['POST'])
def save_mapping():
    """Save or update a pad mapping."""
    data = request.json or {}
    required = {"note", "key_combo", "color"}
    if not required.issubset(data) and data.get("action") != "layer_up":
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    layer = data.get("layer") or mapper.current_layer
    action = data.get("action", "key")
    mapping = PadMapping(
        note=data['note'],
        key_combo=data.get('key_combo', ''),
        color=data.get('color', 'green'),
        label=data.get('label', ''),
        enabled=data.get('enabled', True),
        action=action,
        target_layer=data.get('target_layer'),
        repeat_enabled=data.get('repeat_enabled', False),
        repeat_delay=data.get('repeat_delay', 0.5),
        repeat_interval=data.get('repeat_interval', 0.05),
        macro_steps=data.get('macro_steps'),
        velocity_mappings=data.get('velocity_mappings'),
        long_press_enabled=data.get('long_press_enabled', False),
        long_press_action=data.get('long_press_action', ''),
        long_press_threshold=data.get('long_press_threshold', 0.5)
    )
    mapper.profile.add_mapping(mapping, layer=layer)

    # Update pad color if running
    if mapper.running and layer == mapper.current_layer:
        mapper.update_pad_colors()

    append_log(
        "Saved mapping: "
        f"note={mapping.note}, key_combo={mapping.key_combo}, color={mapping.color}, "
        f"layer={layer}"
    )

    # Auto-save profiles to disk
    save_profiles_async()

    return jsonify({"success": True, "mapping": mapping.to_dict()})


@app.route('/api/mapping/<int:note>', methods=['GET'])
def get_mapping(note):
    """Get a specific mapping."""
    layer = request.args.get("layer") or mapper.current_layer
    mapping = mapper.profile.get_mapping(note, layer)
    if mapping:
        return jsonify(mapping.to_dict())
    return jsonify(None)


@app.route('/api/mapping/<int:note>', methods=['DELETE'])
def delete_mapping(note):
    """Delete a pad mapping."""
    layer = request.args.get("layer") or mapper.current_layer
    mapper.profile.remove_mapping(note, layer)
    if mapper.running and layer == mapper.current_layer:
        mapper.update_pad_colors()
    append_log(f"Deleted mapping: note={note}, layer={layer}")

    # Auto-save profiles to disk
    save_profiles_async()

    return jsonify({"success": True})


@app.route('/api/profile')
def get_profile():
    """Get current profile."""
    data = mapper.profile.to_dict()
    data["active_layer"] = mapper.current_layer
    return jsonify(data)


@app.route('/api/profile', methods=['PUT'])
def update_profile():
    """Update profile metadata."""
    data = request.json or {}
    if 'name' in data:
        with profile_lock:
            old_name = mapper.profile.name
            mapper.profile.name = data['name']
            profiles.pop(old_name, None)
            profiles[mapper.profile.name] = mapper.profile
            append_log(f"Profile renamed: {old_name} -> {mapper.profile.name}")
    if 'description' in data:
        mapper.profile.description = data['description']
        append_log("Profile description updated")

    # Auto-save profiles to disk
    save_profiles_async()

    return jsonify({"success": True})


@app.route('/api/profile/export')
def export_profile():
    """Export current profile as JSON."""
    name = request.args.get('name')
    if name:
        with profile_lock:
            old_name = mapper.profile.name
            mapper.profile.name = name
            profiles.pop(old_name, None)
            profiles[mapper.profile.name] = mapper.profile
            append_log(f"Profile export renamed: {old_name} -> {mapper.profile.name}")
    append_log(f"Profile exported: {mapper.profile.name}")
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile/import', methods=['POST'])
def import_profile():
    """Import a profile from JSON with schema validation."""
    data = request.json or {}
    if not data:
        return jsonify({"success": False, "error": "No profile data provided"}), 400

    # Calculate raw size for DoS protection
    raw_size = len(request.data) if request.data else 0

    # Validate the profile data
    try:
        validated_data, warnings = validate_profile_import(data, raw_size)
    except ValidationError as e:
        append_log(f"Profile import validation failed: {e.message}")
        return jsonify({
            "success": False,
            "error": f"Validation error: {e.message}",
            "field": e.field
        }), 400

    # Create profile from validated data
    profile = Profile.from_dict(validated_data)
    with profile_lock:
        profiles[profile.name] = profile
    mapper.set_profile(profile)
    append_log(f"Profile imported: {profile.name}")

    # Auto-save profiles to disk
    save_profiles_async()

    response = {"success": True, "profile": mapper.profile.to_dict()}
    if warnings:
        response["warnings"] = warnings
    return jsonify(response)


@app.route('/api/clear', methods=['POST'])
def clear_mappings():
    """Clear all mappings."""
    current_name = mapper.profile.name
    current_description = mapper.profile.description
    current_base_layer = mapper.profile.base_layer
    profile = Profile(current_name, current_base_layer)
    profile.description = current_description
    mapper.set_profile(profile)
    with profile_lock:
        profiles[current_name] = profile
    if mapper.running:
        mapper.update_pad_colors()
    append_log(f"Cleared mappings for profile: {current_name}")

    # Auto-save profiles to disk
    save_profiles_async()

    return jsonify({"success": True})


@app.route('/api/test-key', methods=['POST'])
def test_key():
    """Test a key combination."""
    data = request.json or {}
    combo = data.get('combo', '')
    if combo:
        mapper.execute_key_combo(combo)
        return jsonify({"success": True, "combo": combo})
    return jsonify({"success": False, "error": "No combo provided"})


@app.route('/api/set-color', methods=['POST'])
def set_color():
    """Set a pad color directly."""
    data = request.json or {}
    note = data.get('note')
    color = data.get('color', 'off')
    if note is not None:
        mapper.set_pad_color(note, color)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No note provided"})


@app.route('/api/layers')
def get_layers():
    return jsonify({
        "layers": sorted(mapper.profile.layers.keys()),
        "current_layer": mapper.current_layer
    })


@app.route('/api/layer/push', methods=['POST'])
def push_layer():
    data = request.json or {}
    layer = data.get("layer")
    if not layer:
        return jsonify({"success": False, "error": "No layer provided"}), 400
    mapper.push_layer(layer)
    return jsonify({"success": True, "current_layer": mapper.current_layer})


@app.route('/api/layer/pop', methods=['POST'])
def pop_layer():
    mapper.pop_layer()
    return jsonify({"success": True, "current_layer": mapper.current_layer})


@app.route('/api/layer/set', methods=['POST'])
def set_layer():
    data = request.json or {}
    layer = data.get("layer")
    if not layer:
        return jsonify({"success": False, "error": "No layer provided"}), 400
    mapper.set_layer(layer)
    return jsonify({"success": True, "current_layer": mapper.current_layer})


@app.route('/api/profiles')
def list_profiles():
    with profile_lock:
        names = sorted(profiles.keys())
    return jsonify({
        "profiles": names,
        "active_profile": mapper.profile.name
    })


@app.route('/api/profile/switch', methods=['POST'])
def switch_profile_endpoint():
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"success": False, "error": "No profile name provided"}), 400
    if not switch_profile(name):
        return jsonify({"success": False, "error": "Profile not found"}), 404

    # Save profiles to persist active profile selection
    save_profiles_async()

    return jsonify({"success": True, "profile": mapper.profile.to_dict()})


@app.route('/api/profile/auto', methods=['GET', 'POST'])
def profile_auto_switch():
    global auto_switch_enabled
    if request.method == 'GET':
        with auto_switch_lock:
            return jsonify({
                "enabled": auto_switch_enabled,
                "rules": auto_switch_rules,
                "available": pygetwindow is not None
            })
    data = request.json or {}
    rules = data.get("rules", [])
    enabled = data.get("enabled", False)
    if enabled and pygetwindow is None:
        return jsonify({"success": False, "error": "Auto switch unavailable"}), 400
    with auto_switch_lock:
        auto_switch_rules[:] = [
            {"match": rule.get("match", ""), "profile": rule.get("profile", "")}
            for rule in rules
            if rule.get("match") and rule.get("profile")
        ]
        auto_switch_enabled = bool(enabled)

    # Save auto-switch settings to config
    save_config_async()

    return jsonify({"success": True, "enabled": auto_switch_enabled, "rules": auto_switch_rules})


@app.route('/api/events')
def events():
    """Server-sent events for real-time updates."""
    def generate():
        q = queue.Queue(maxsize=100)
        with event_queues_lock:
            event_queues.append(q)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Send keepalive
                    yield f": keepalive\n\n"
        finally:
            with event_queues_lock:
                event_queues.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the server (used for one-click close)."""
    mapper.stop()
    mapper.disconnect()
    request_shutdown()
    return jsonify({"success": True})


@app.route('/api/animation/pulse', methods=['POST'])
def animate_pulse():
    """Trigger a pulse animation on a pad."""
    data = request.json or {}
    note = data.get('note')
    color = data.get('color', 'green')
    duration = data.get('duration', 0.5)
    if note is not None:
        mapper.pulse(note, color, duration)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No note provided"}), 400


@app.route('/api/animation/progress', methods=['POST'])
def animate_progress():
    """Show a progress bar animation."""
    data = request.json or {}
    row = data.get('row', 0)  # Row index 0-7
    percentage = data.get('percentage', 0)
    color = data.get('color', 'green')
    if 0 <= row < len(mapper.GRID_NOTES):
        row_notes = mapper.GRID_NOTES[row]
        anim = ProgressBarAnimation(mapper, row_notes, percentage, color)
        mapper.start_animation(anim)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid row"}), 400


@app.route('/api/animation/rainbow', methods=['POST'])
def animate_rainbow():
    """Start rainbow cycle animation."""
    data = request.json or {}
    speed = data.get('speed', 0.5)
    anim = RainbowCycleAnimation(mapper, speed)
    mapper.start_animation(anim)
    return jsonify({"success": True})


@app.route('/api/animation/stop', methods=['POST'])
def stop_animations():
    """Stop all active animations."""
    mapper.stop_all_animations()
    if mapper.running:
        mapper.update_pad_colors()
    return jsonify({"success": True})


@app.route('/api/animation/smiley', methods=['GET', 'POST'])
def animate_smiley():
    """Play smiley face animation or get available faces."""
    if request.method == 'GET':
        return jsonify({
            "faces": mapper.get_available_smiley_faces(),
            "description": "Use POST to play animation or show a specific face"
        })

    data = request.json or {}
    face = data.get('face')
    duration = data.get('duration', 15.0)

    # If a specific face is requested, show it
    if face:
        result = mapper.show_smiley_face(face)
        append_log(f"Show smiley face: {face}, success={result.get('success')}")
        if not result.get("success"):
            return jsonify(result), 400
        return jsonify(result)

    # Otherwise play the animation
    result = mapper.play_smiley_animation(duration)
    append_log(f"Play smiley animation: duration={duration}, success={result.get('success')}")
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/presets')
def list_presets():
    """List available preset profiles."""
    import os
    preset_dir = os.path.join(os.path.dirname(__file__), 'presets')
    if not os.path.exists(preset_dir):
        return jsonify({"presets": []})

    presets = []
    for filename in os.listdir(preset_dir):
        if filename.endswith('.json'):
            preset_name = filename[:-5].replace('_', ' ').title()
            presets.append({
                "filename": filename,
                "name": preset_name
            })
    return jsonify({"presets": presets})


@app.route('/api/presets/<filename>')
def get_preset(filename):
    """Load a specific preset profile."""
    import os
    preset_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), 'presets'))
    filepath = os.path.realpath(os.path.join(preset_dir, filename))

    # Prevent path traversal attacks
    if not filepath.startswith(preset_dir + os.sep):
        return jsonify({"error": "Invalid preset path"}), 400

    if not os.path.exists(filepath) or not filename.endswith('.json'):
        return jsonify({"error": "Preset not found"}), 404

    try:
        with open(filepath, 'r') as f:
            preset_data = json.load(f)
        return jsonify(preset_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def cleanup_on_exit():
    """Cleanup handler for graceful shutdown."""
    print("\nCleaning up server resources...")

    # Flush any pending profile saves
    persistence.flush_pending_saves()

    # Final save of current state
    with profile_lock:
        persistence.save_profiles(
            {name: p.to_dict() for name, p in profiles.items()},
            mapper.profile.name
        )

    with auto_switch_lock:
        persistence.save_config({
            'last_input_port': mapper.last_input_port,
            'last_output_port': mapper.last_output_port,
            'auto_switch_rules': auto_switch_rules,
            'auto_switch_enabled': auto_switch_enabled,
        })

    # Disconnect mapper
    mapper.disconnect()
    print("Server cleanup complete")


# Register cleanup handler
atexit.register(cleanup_on_exit)


def main():
    print("\n" + "="*50)
    print("  Launchpad Mapper")
    print("="*50)
    print("\nStarting web interface at http://localhost:5000")
    print(f"Config stored at: {persistence.persistence_dir}")
    print("Press Ctrl+C to quit\n")

    ipc_dir = os.path.join(tempfile.gettempdir(), "lrslider_ipc")
    if os.path.exists(ipc_dir):
        print(f"Cleaning up old command files in {ipc_dir}...")
        for ipc_file in glob.glob(os.path.join(ipc_dir, "*.txt")):
            try:
                os.remove(ipc_file)
            except OSError:
                pass

    thread = threading.Thread(target=auto_switch_worker, daemon=True)
    thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        # atexit handler will handle cleanup


if __name__ == '__main__':
    main()
