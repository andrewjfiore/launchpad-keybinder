#!/usr/bin/env python3
"""
Web server for Launchpad Mapper configuration interface.
"""

import json
import time
import queue
from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS

from launchpad_mapper import (
    LaunchpadMapper, Profile, PadMapping,
    LAUNCHPAD_COLORS, COLOR_HEX
)


app = Flask(__name__)
CORS(app)

# Global mapper instance
mapper = LaunchpadMapper()

# Event queue for server-sent events
event_queues = []


def broadcast_event(data):
    """Broadcast an event to all connected clients."""
    for q in event_queues:
        try:
            q.put_nowait(data)
        except queue.Full:
            pass


def event_callback(data):
    """Callback for MIDI events."""
    broadcast_event(data)


# Register the callback
mapper.add_callback(event_callback)


@app.route('/')
def index():
    return render_template('index.html',
        colors=json.dumps(LAUNCHPAD_COLORS),
        color_hex=json.dumps(COLOR_HEX)
    )


@app.route('/api/ports')
def get_ports():
    """Get available MIDI ports."""
    return jsonify(mapper.get_available_ports())


@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to MIDI ports."""
    data = request.json or {}
    success = mapper.connect(data.get('input_port'), data.get('output_port'))
    return jsonify({
        "connected": success,
        "message": "Connected successfully" if success else "Failed to connect"
    })


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from MIDI ports."""
    mapper.disconnect()
    return jsonify({"message": "Disconnected"})


@app.route('/api/start', methods=['POST'])
def start():
    """Start the mapper."""
    success = mapper.start()
    return jsonify({
        "started": success,
        "message": "Mapper started" if success else "Failed to start - is MIDI connected?"
    })


@app.route('/api/stop', methods=['POST'])
def stop():
    """Stop the mapper."""
    mapper.stop()
    return jsonify({"message": "Mapper stopped"})


@app.route('/api/status')
def status():
    """Get current mapper status."""
    return jsonify({
        "connected": mapper.input_port is not None,
        "running": mapper.running,
        "profile_name": mapper.profile.name,
        "mapping_count": len(mapper.profile.mappings)
    })


@app.route('/api/mapping', methods=['POST'])
def save_mapping():
    """Save or update a pad mapping."""
    data = request.json
    mapping = PadMapping(
        note=data['note'],
        key_combo=data['key_combo'],
        color=data['color'],
        label=data.get('label', ''),
        enabled=data.get('enabled', True)
    )
    mapper.profile.add_mapping(mapping)
    
    # Update pad color if running
    if mapper.running:
        mapper.set_pad_color(mapping.note, mapping.color if mapping.enabled else 'off')
    
    return jsonify({"success": True, "mapping": mapping.to_dict()})


@app.route('/api/mapping/<int:note>', methods=['GET'])
def get_mapping(note):
    """Get a specific mapping."""
    mapping = mapper.profile.get_mapping(note)
    if mapping:
        return jsonify(mapping.to_dict())
    return jsonify(None)


@app.route('/api/mapping/<int:note>', methods=['DELETE'])
def delete_mapping(note):
    """Delete a pad mapping."""
    mapper.profile.remove_mapping(note)
    if mapper.running:
        mapper.set_pad_color(note, 'off')
    return jsonify({"success": True})


@app.route('/api/profile')
def get_profile():
    """Get current profile."""
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile', methods=['PUT'])
def update_profile():
    """Update profile metadata."""
    data = request.json
    if 'name' in data:
        mapper.profile.name = data['name']
    if 'description' in data:
        mapper.profile.description = data['description']
    return jsonify({"success": True})


@app.route('/api/profile/export')
def export_profile():
    """Export current profile as JSON."""
    name = request.args.get('name')
    if name:
        mapper.profile.name = name
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile/import', methods=['POST'])
def import_profile():
    """Import a profile from JSON."""
    data = request.json
    mapper.profile = Profile.from_dict(data)
    if mapper.running:
        mapper.update_pad_colors()
    return jsonify({"success": True, "profile": mapper.profile.to_dict()})


@app.route('/api/clear', methods=['POST'])
def clear_mappings():
    """Clear all mappings."""
    mapper.profile = Profile(mapper.profile.name)
    if mapper.running:
        mapper.clear_all_pads()
    return jsonify({"success": True})


@app.route('/api/test-key', methods=['POST'])
def test_key():
    """Test a key combination."""
    data = request.json
    combo = data.get('combo', '')
    if combo:
        mapper.execute_key_combo(combo)
        return jsonify({"success": True, "combo": combo})
    return jsonify({"success": False, "error": "No combo provided"})


@app.route('/api/set-color', methods=['POST'])
def set_color():
    """Set a pad color directly."""
    data = request.json
    note = data.get('note')
    color = data.get('color', 'off')
    if note is not None:
        mapper.set_pad_color(note, color)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No note provided"})


@app.route('/api/events')
def events():
    """Server-sent events for real-time updates."""
    def generate():
        q = queue.Queue(maxsize=100)
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
            event_queues.remove(q)
    
    return Response(generate(), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def main():
    print("\n" + "="*50)
    print("  Launchpad Mapper")
    print("="*50)
    print("\nStarting web interface at http://localhost:5000")
    print("Press Ctrl+C to quit\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        mapper.disconnect()


if __name__ == '__main__':
    main()
