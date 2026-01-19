#!/usr/bin/env python3
"""
Launchpad Mini MIDI to Keyboard Mapper
Improved version with Windows support, hex colors, and key repeat
"""

import json
import os
import platform
import queue
import threading
import time
import tempfile
import uuid
from dataclasses import dataclass, asdict
from functools import lru_cache
from itertools import chain
from typing import Optional, Dict, List, Callable, Any

import mido
from mido import Message
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Use 'keyboard' library for better Windows support (sends to active window)
import keyboard

# ============================================================================
# CONFIGURATION
# ============================================================================

# Launchpad color palette (velocity values for LED colors)
LAUNCHPAD_COLORS = {
    "off": 0,
    "white": 3,
    "red": 5,
    "red_dim": 7,
    "orange": 9,
    "orange_dim": 11,
    "yellow": 13,
    "yellow_dim": 15,
    "lime": 17,
    "lime_dim": 19,
    "green": 21,
    "green_dim": 23,
    "spring": 29,
    "spring_dim": 27,
    "cyan": 37,
    "cyan_dim": 35,
    "sky": 41,
    "sky_dim": 39,
    "blue": 45,
    "blue_dim": 43,
    "purple": 49,
    "purple_dim": 47,
    "magenta": 53,
    "magenta_dim": 51,
    "pink": 57,
    "pink_dim": 55,
    "coral": 61,
    "coral_dim": 59,
    "amber": 65,
    "amber_dim": 63,
}

COLOR_HEX = {
    "off": "#333333",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "red_dim": "#800000",
    "orange": "#FF8000",
    "orange_dim": "#804000",
    "yellow": "#FFFF00",
    "yellow_dim": "#808000",
    "lime": "#80FF00",
    "lime_dim": "#408000",
    "green": "#00FF00",
    "green_dim": "#008000",
    "spring": "#00FF80",
    "spring_dim": "#008040",
    "cyan": "#00FFFF",
    "cyan_dim": "#008080",
    "sky": "#0080FF",
    "sky_dim": "#004080",
    "blue": "#0000FF",
    "blue_dim": "#000080",
    "purple": "#8000FF",
    "purple_dim": "#400080",
    "magenta": "#FF00FF",
    "magenta_dim": "#800080",
    "pink": "#FF0080",
    "pink_dim": "#800040",
    "coral": "#FF4040",
    "coral_dim": "#802020",
    "amber": "#FFBF00",
    "amber_dim": "#806000",
}

# Map color names to closest Launchpad velocity by RGB distance
@lru_cache(maxsize=128)
def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_distance(c1, c2):
    """Calculate color distance."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

@lru_cache(maxsize=128)
def find_closest_launchpad_color(hex_color):
    """Find the closest Launchpad color to a given hex color."""
    target_rgb = hex_to_rgb(hex_color)
    best_match = "green"
    best_distance = float('inf')
    
    for name, hex_val in COLOR_HEX.items():
        if name == "off":
            continue
        dist = rgb_distance(target_rgb, hex_to_rgb(hex_val))
        if dist < best_distance:
            best_distance = dist
            best_match = name
    
    return best_match


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PadMapping:
    note: int
    key_combo: str
    color: str  # Can be palette name or hex
    label: str
    enabled: bool = True
    action: str = "key"
    target_layer: Optional[str] = None
    repeat_enabled: bool = False
    repeat_delay: float = 0.5  # Initial delay before repeat starts (seconds)
    repeat_interval: float = 0.05  # Interval between repeats (seconds)
    # Macro sequences support
    macro_steps: Optional[List[Dict[str, Any]]] = None  # List of {key_combo, delay_after}
    # Velocity sensitivity support
    velocity_mappings: Optional[Dict[str, str]] = None  # {range: key_combo} e.g., "0-42": "ctrl+c"
    # Long press support
    long_press_enabled: bool = False
    long_press_action: str = ""  # Different action for long press
    long_press_threshold: float = 0.5  # Seconds to trigger long press
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        # Handle older profiles without new settings
        return cls(
            note=data['note'],
            key_combo=data['key_combo'],
            color=data['color'],
            label=data.get('label', ''),
            enabled=data.get('enabled', True),
            action=data.get('action', 'key'),
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
    
    def get_launchpad_color(self):
        """Get the Launchpad velocity value for this color."""
        if self.color.startswith('#'):
            closest = find_closest_launchpad_color(self.color)
            return LAUNCHPAD_COLORS.get(closest, 21)
        return LAUNCHPAD_COLORS.get(self.color, 21)
    
    def get_display_hex(self):
        """Get hex color for UI display."""
        if self.color.startswith('#'):
            return self.color
        return COLOR_HEX.get(self.color, '#00FF00')


class Profile:
    def __init__(self, name: str = "Default", base_layer: str = "Base"):
        self.name = name
        self.description = ""
        self.base_layer = base_layer
        self.layers: Dict[str, Dict[int, PadMapping]] = {base_layer: {}}
        
    def add_mapping(self, mapping: PadMapping, layer: Optional[str] = None):
        layer_name = layer or self.base_layer
        self.layers.setdefault(layer_name, {})[mapping.note] = mapping
        
    def remove_mapping(self, note: int, layer: Optional[str] = None):
        layer_name = layer or self.base_layer
        if note in self.layers.get(layer_name, {}):
            del self.layers[layer_name][note]
            
    def get_mapping(self, note: int, layer: Optional[str] = None) -> Optional[PadMapping]:
        layer_name = layer or self.base_layer
        return self.layers.get(layer_name, {}).get(note)

    def get_layer_mappings(self, layer: Optional[str] = None) -> Dict[int, PadMapping]:
        layer_name = layer or self.base_layer
        return self.layers.get(layer_name, {})

    def ensure_layer(self, layer: str):
        self.layers.setdefault(layer, {})
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "base_layer": self.base_layer,
            "layers": {
                layer: {str(k): v.to_dict() for k, v in mappings.items()}
                for layer, mappings in self.layers.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data):
        profile = cls(data.get("name", "Imported"), data.get("base_layer", "Base"))
        profile.description = data.get("description", "")
        layers = data.get("layers")
        if layers:
            for layer_name, mappings in layers.items():
                for note_str, mapping_data in mappings.items():
                    mapping_note = mapping_data.get("note")
                    if mapping_note is None:
                        mapping_data = dict(mapping_data)
                        mapping_data["note"] = int(note_str)
                    profile.add_mapping(PadMapping.from_dict(mapping_data), layer=layer_name)
        else:
            for note_str, mapping_data in data.get("mappings", {}).items():
                mapping_note = mapping_data.get("note")
                if mapping_note is None:
                    mapping_data = dict(mapping_data)
                    mapping_data["note"] = int(note_str)
                profile.add_mapping(PadMapping.from_dict(mapping_data))
        profile.ensure_layer(profile.base_layer)
        return profile


# ============================================================================
# LED ANIMATION ENGINE
# ============================================================================

class LEDAnimation:
    """Base class for LED animations."""
    def __init__(self, mapper, note: int):
        self.mapper = mapper
        self.note = note
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)

    def run(self):
        raise NotImplementedError


class PulseAnimation(LEDAnimation):
    """Pulse a pad color."""
    def __init__(self, mapper, note: int, color: str, duration: float = 0.5):
        super().__init__(mapper, note)
        self.color = color
        self.duration = duration

    def run(self):
        # Pulse effect: bright -> dim -> off
        if self.color in LAUNCHPAD_COLORS:
            dim_color = self.color + "_dim" if self.color != "off" else "off"
        else:
            dim_color = "off"

        steps = 5
        step_duration = self.duration / (steps * 2)

        for _ in range(steps):
            if self.stop_event.is_set():
                return
            self.mapper.set_pad_color(self.note, self.color)
            time.sleep(step_duration)
            if self.stop_event.is_set():
                return
            self.mapper.set_pad_color(self.note, dim_color)
            time.sleep(step_duration)


class ProgressBarAnimation(LEDAnimation):
    """Show progress bar across a row of pads."""
    def __init__(self, mapper, row_notes: List[int], percentage: float, color: str = "green"):
        super().__init__(mapper, row_notes[0] if row_notes else 0)
        self.row_notes = row_notes
        self.percentage = max(0, min(100, percentage))
        self.color = color

    def run(self):
        num_pads = len(self.row_notes)
        lit_count = int((self.percentage / 100) * num_pads)

        for i, note in enumerate(self.row_notes):
            if self.stop_event.is_set():
                return
            if i < lit_count:
                self.mapper.set_pad_color(note, self.color)
            else:
                self.mapper.set_pad_color(note, "off")
            time.sleep(0.05)


class RainbowCycleAnimation(LEDAnimation):
    """Rainbow cycle across all pads."""
    def __init__(self, mapper, speed: float = 0.5):
        super().__init__(mapper, 0)
        self.speed = speed
        self.colors = ["red", "orange", "yellow", "lime", "green", "cyan", "blue", "purple", "magenta"]

    def run(self):
        all_notes = list(chain.from_iterable(LaunchpadMapper.GRID_NOTES))
        color_index = 0

        while not self.stop_event.is_set():
            for i, note in enumerate(all_notes):
                color = self.colors[(i + color_index) % len(self.colors)]
                self.mapper.set_pad_color(note, color)

            color_index = (color_index + 1) % len(self.colors)
            time.sleep(self.speed)


# ============================================================================
# LAUNCHPAD MAPPER
# ============================================================================

class LaunchpadMapper:
    GRID_NOTES = [
        [81, 82, 83, 84, 85, 86, 87, 88],
        [71, 72, 73, 74, 75, 76, 77, 78],
        [61, 62, 63, 64, 65, 66, 67, 68],
        [51, 52, 53, 54, 55, 56, 57, 58],
        [41, 42, 43, 44, 45, 46, 47, 48],
        [31, 32, 33, 34, 35, 36, 37, 38],
        [21, 22, 23, 24, 25, 26, 27, 28],
        [11, 12, 13, 14, 15, 16, 17, 18],
    ]
    CONTROL_NOTES = [91, 92, 93, 94, 95, 96, 97, 98]
    SCENE_NOTES = [89, 79, 69, 59, 49, 39, 29, 19]
    
    def __init__(self):
        self.profile = Profile()
        self.input_port = None
        self.output_port = None
        self.running = False
        self.midi_thread = None
        self.callbacks: List[Callable] = []
        self.layer_stack = [self.profile.base_layer]

        # Key repeat handling
        self.active_repeats: Dict[int, threading.Thread] = {}
        self.repeat_stop_events: Dict[int, threading.Event] = {}

        # Long press handling
        self.press_times: Dict[int, float] = {}  # note -> press timestamp
        self.long_press_triggered: Dict[int, bool] = {}  # note -> whether long press fired

        # Active animations
        self.active_animations: List[LEDAnimation] = []
        
    def get_available_ports(self) -> Dict[str, Any]:
        """Get available MIDI ports with error handling"""
        inputs = []
        outputs = []
        errors = []

        try:
            inputs = list(mido.get_input_names())
        except Exception as e:
            error_msg = f"Error getting MIDI inputs: {e}"
            print(error_msg)
            errors.append(error_msg)

        try:
            outputs = list(mido.get_output_names())
        except Exception as e:
            error_msg = f"Error getting MIDI outputs: {e}"
            print(error_msg)
            errors.append(error_msg)

        result = {
            "inputs": inputs,
            "outputs": outputs
        }

        # Add error information if no ports found or errors occurred
        if not inputs and not outputs:
            if errors:
                result["error"] = "MIDI error: " + "; ".join(errors)
            else:
                result["error"] = "No MIDI ports detected. Please ensure your Launchpad is connected and drivers are installed."
        elif errors:
            result["error"] = "; ".join(errors)

        return result
    
    def find_launchpad_ports(self) -> Dict[str, Optional[str]]:
        ports = self.get_available_ports()

        def pick_port(port_list: List[str]) -> Optional[str]:
            if not port_list:
                return None
            normalized = [(port, port.lower().replace(" ", "")) for port in port_list]
            keywords = [
                "launchpad",
                "lpmini",
                "lpminimk",
                "lpmk",
                "lppro",
                "launchpadx",
                "novation",
            ]
            for port, normalized_name in normalized:
                if any(keyword in normalized_name for keyword in keywords):
                    return port
            if len(port_list) == 1:
                return port_list[0]
            return None

        return {
            "input": pick_port(ports["inputs"]),
            "output": pick_port(ports["outputs"]),
        }
    
    def connect(
        self,
        input_port: str = None,
        output_port: str = None,
        retries: int = 3,
        retry_delay: float = 0.5,
    ) -> Dict[str, Any]:
        """Connect to MIDI ports with retries."""
        errors = []
        try:
            for attempt in range(1, retries + 1):
                if self.input_port or self.output_port:
                    self.disconnect()

                detected_input = input_port
                detected_output = output_port
                if not detected_input or not detected_output:
                    detected = self.find_launchpad_ports()
                    detected_input = detected_input or detected["input"]
                    detected_output = detected_output or detected["output"]

                if not detected_input and not detected_output:
                    errors.append("No Launchpad detected. Please connect your device and click Refresh.")
                    time.sleep(retry_delay)
                    continue

                messages = []
                try:
                    if detected_input:
                        self.input_port = mido.open_input(detected_input)
                        messages.append(f"Input: {detected_input}")
                        print(f"Connected to input: {detected_input}")
                    if detected_output:
                        self.output_port = mido.open_output(detected_output)
                        messages.append(f"Output: {detected_output}")
                        print(f"Connected to output: {detected_output}")
                except Exception as e:
                    if self.input_port:
                        self.input_port.close()
                        self.input_port = None
                    if self.output_port:
                        self.output_port.close()
                        self.output_port = None
                    errors.append(str(e))
                    time.sleep(retry_delay)
                    continue

                if self.input_port is not None:
                    self.enter_programmer_mode()
                    return {
                        "success": True,
                        "message": "Connected: " + ", ".join(messages),
                        "attempt": attempt,
                    }

                errors.append("Input port is required for MIDI input.")
                time.sleep(retry_delay)

            return {
                "success": False,
                "message": "Failed to connect after retries",
                "error": errors[-1] if errors else "Unknown MIDI error",
                "errors": errors,
            }
        except Exception as e:
            print(f"Error connecting to MIDI: {e}")
            return {
                "success": False,
                "message": "Connection failed",
                "error": str(e),
                "errors": errors + [str(e)],
            }
    
    def disconnect(self):
        self.stop()
        if self.input_port:
            self.input_port.close()
            self.input_port = None
        if self.output_port:
            self.output_port.close()
            self.output_port = None

    def enter_programmer_mode(self):
        """Send SysEx to enter Programmer mode for custom LED control."""
        if not self.output_port:
            return

        # SysEx messages to enter Programmer mode for various Launchpad models
        # Launchpad Mini MK3: F0 00 20 29 02 0D 0E 01 F7
        # Launchpad X: F0 00 20 29 02 0C 0E 01 F7
        # Launchpad Pro MK3: F0 00 20 29 02 0E 0E 01 F7
        sysex_messages = [
            [0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01],  # Mini MK3
            [0x00, 0x20, 0x29, 0x02, 0x0C, 0x0E, 0x01],  # Launchpad X
            [0x00, 0x20, 0x29, 0x02, 0x0E, 0x0E, 0x01],  # Pro MK3
        ]

        try:
            for sysex_data in sysex_messages:
                msg = Message('sysex', data=sysex_data)
                self.output_port.send(msg)
            print("Sent Programmer mode SysEx commands")
        except Exception as e:
            print(f"Error sending Programmer mode SysEx: {e}")

    def set_pad_color(self, note: int, color: str):
        if self.output_port:
            if color.startswith('#'):
                closest = find_closest_launchpad_color(color)
                velocity = LAUNCHPAD_COLORS.get(closest, 0)
            else:
                velocity = LAUNCHPAD_COLORS.get(color, 0)
            msg = Message('note_on', note=note, velocity=velocity)
            self.output_port.send(msg)
    
    def clear_all_pads(self):
        if self.output_port:
            for note in chain.from_iterable(self.GRID_NOTES):
                self.set_pad_color(note, "off")
            for note in chain(self.CONTROL_NOTES, self.SCENE_NOTES):
                self.set_pad_color(note, "off")
    
    def update_pad_colors(self):
        self.clear_all_pads()
        for note, mapping in self.profile.get_layer_mappings(self.current_layer).items():
            if mapping.enabled:
                self.set_pad_color(note, mapping.color)

    @property
    def current_layer(self) -> str:
        return self.layer_stack[-1]

    def push_layer(self, layer: str):
        self.profile.ensure_layer(layer)
        self.layer_stack.append(layer)
        if self.running:
            self.update_pad_colors()
        self.notify_layer_change()

    def pop_layer(self):
        if len(self.layer_stack) > 1:
            self.layer_stack.pop()
            if self.running:
                self.update_pad_colors()
            self.notify_layer_change()

    def set_layer(self, layer: str):
        self.profile.ensure_layer(layer)
        self.layer_stack = [layer]
        if self.running:
            self.update_pad_colors()
        self.notify_layer_change()

    def set_profile(self, profile: Profile):
        self.profile = profile
        self.layer_stack = [profile.base_layer]
        if self.running:
            self.update_pad_colors()
        self.notify_layer_change()
    
    def execute_key_combo(self, combo: str):
        """Execute a keyboard shortcut using the keyboard library (works on Windows)."""
        try:
            if combo.startswith("lrslider:"):
                command = combo.split(":", 1)[1].strip()
                if command:
                    ipc_dir = os.path.join(tempfile.gettempdir(), "lrslider_ipc")
                    os.makedirs(ipc_dir, exist_ok=True)
                    filename = f"cmd_{uuid.uuid4().hex}.txt"
                    with open(os.path.join(ipc_dir, filename), "w", encoding="utf-8") as handle:
                        handle.write(command)
                return
            # The keyboard library uses '+' for combinations naturally
            # It sends to the active window
            keyboard.send(combo)
        except Exception as e:
            print(f"Error sending key combo '{combo}': {e}")

    def execute_macro(self, mapping: PadMapping):
        """Execute a macro sequence."""
        if not mapping.macro_steps:
            return

        def macro_worker():
            for step in mapping.macro_steps:
                key_combo = step.get('key_combo', '')
                delay_after = step.get('delay_after', 0.0)
                if key_combo:
                    self.execute_key_combo(key_combo)
                    print(f"Macro step: {key_combo}")
                if delay_after > 0:
                    time.sleep(delay_after)

        thread = threading.Thread(target=macro_worker, daemon=True)
        thread.start()

    def get_velocity_action(self, mapping: PadMapping, velocity: int) -> Optional[str]:
        """Get the action for a specific velocity value."""
        if not mapping.velocity_mappings:
            return mapping.key_combo

        # Parse velocity ranges like "0-42", "43-84", "85-127"
        for range_str, action in mapping.velocity_mappings.items():
            try:
                if '-' in range_str:
                    low, high = map(int, range_str.split('-'))
                    if low <= velocity <= high:
                        return action
            except ValueError:
                continue

        return mapping.key_combo  # Fallback to default

    def start_animation(self, animation: LEDAnimation):
        """Start an LED animation."""
        self.active_animations.append(animation)
        animation.start()

    def stop_all_animations(self):
        """Stop all active animations."""
        for anim in self.active_animations:
            anim.stop()
        self.active_animations.clear()

    def pulse(self, note: int, color: str, duration: float = 0.5):
        """Pulse a pad with visual feedback."""
        anim = PulseAnimation(self, note, color, duration)
        self.start_animation(anim)
    
    def key_repeat_worker(self, note: int, mapping: PadMapping, stop_event: threading.Event):
        """Worker thread for key repeat."""
        # Initial delay
        if stop_event.wait(mapping.repeat_delay):
            return  # Stopped during initial delay
        
        # Repeat loop
        while not stop_event.is_set():
            self.execute_key_combo(mapping.key_combo)
            for callback in self.callbacks:
                callback({"type": "key_repeat", "note": note, "combo": mapping.key_combo})
            if stop_event.wait(mapping.repeat_interval):
                break
    
    def start_key_repeat(self, note: int, mapping: PadMapping):
        """Start key repeat for a pad."""
        if note in self.active_repeats:
            return  # Already repeating
        
        stop_event = threading.Event()
        self.repeat_stop_events[note] = stop_event
        
        thread = threading.Thread(
            target=self.key_repeat_worker,
            args=(note, mapping, stop_event),
            daemon=True
        )
        self.active_repeats[note] = thread
        thread.start()
    
    def stop_key_repeat(self, note: int):
        """Stop key repeat for a pad."""
        if note in self.repeat_stop_events:
            self.repeat_stop_events[note].set()
            del self.repeat_stop_events[note]
        if note in self.active_repeats:
            del self.active_repeats[note]
    
    def stop_all_repeats(self):
        """Stop all active key repeats."""
        for note in list(self.repeat_stop_events.keys()):
            self.stop_key_repeat(note)
    
    def handle_midi_message(self, msg):
        if msg.type == 'note_on' and msg.velocity > 0:
            note = msg.note
            mapping = self.profile.get_mapping(note, self.current_layer)

            # Track press time for long press detection
            self.press_times[note] = time.time()
            self.long_press_triggered[note] = False

            for callback in self.callbacks:
                callback({"type": "pad_press", "note": note, "velocity": msg.velocity})

            if mapping and mapping.enabled:
                # Handle layer actions
                if mapping.action == "layer_up":
                    self.pop_layer()
                    print(f"Pad {note} -> layer up")
                    self.pulse(note, mapping.color, 0.3)
                    return
                elif mapping.action == "layer" and mapping.target_layer:
                    self.push_layer(mapping.target_layer)
                    print(f"Pad {note} -> layer {mapping.target_layer}")
                    self.pulse(note, mapping.color, 0.3)
                    return

                # Check for long press support
                if mapping.long_press_enabled and mapping.long_press_action:
                    # Start a timer to check for long press
                    def check_long_press():
                        time.sleep(mapping.long_press_threshold)
                        if note in self.press_times and not self.long_press_triggered.get(note, False):
                            # Long press detected
                            self.long_press_triggered[note] = True
                            self.execute_key_combo(mapping.long_press_action)
                            print(f"Pad {note} -> LONG PRESS: {mapping.long_press_action}")
                            for callback in self.callbacks:
                                callback({"type": "long_press", "note": note, "combo": mapping.long_press_action})

                    threading.Thread(target=check_long_press, daemon=True).start()
                else:
                    # No long press, execute immediately
                    # Check for macro sequence
                    if mapping.macro_steps:
                        self.execute_macro(mapping)
                        print(f"Pad {note} -> Executing macro sequence")
                    else:
                        # Check for velocity sensitivity
                        action = self.get_velocity_action(mapping, msg.velocity)
                        if action:
                            self.execute_key_combo(action)
                            print(f"Pad {note} (vel:{msg.velocity}) -> {action}")

                # Start repeat if enabled (and not macro or long press)
                if mapping.repeat_enabled and mapping.action == "key" and not mapping.macro_steps and not mapping.long_press_enabled:
                    self.start_key_repeat(note, mapping)

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            note = msg.note
            mapping = self.profile.get_mapping(note, self.current_layer)

            # Check if this is a short press (for long press feature)
            if note in self.press_times and mapping and mapping.enabled:
                press_duration = time.time() - self.press_times[note]
                # Short press - only execute if long press wasn't triggered
                if mapping.long_press_enabled and not self.long_press_triggered.get(note, False):
                    if press_duration < mapping.long_press_threshold:
                        # Execute the regular action for short press
                        if mapping.macro_steps:
                            self.execute_macro(mapping)
                        else:
                            self.execute_key_combo(mapping.key_combo)
                        print(f"Pad {note} -> SHORT PRESS: {mapping.key_combo}")

            # Cleanup
            self.press_times.pop(note, None)
            self.long_press_triggered.pop(note, None)

            # Stop any active repeat
            self.stop_key_repeat(note)

            for callback in self.callbacks:
                callback({"type": "pad_release", "note": note})

        elif msg.type == 'control_change':
            for callback in self.callbacks:
                callback({"type": "control", "control": msg.control, "value": msg.value})
    
    def midi_loop(self):
        while self.running:
            try:
                # Check input_port inside try block to handle race condition
                port = self.input_port
                if port is None:
                    break
                for msg in port.iter_pending():
                    self.handle_midi_message(msg)
                time.sleep(0.001)
            except Exception as e:
                print(f"MIDI loop error: {e}")
                # Brief pause before retrying to avoid tight error loop
                time.sleep(0.1)
                # If port was closed, exit the loop
                if self.input_port is None:
                    break
    
    def start(self):
        if self.running:
            return True
        if not self.input_port:
            print("No input port connected")
            return False
        self.running = True
        self.midi_thread = threading.Thread(target=self.midi_loop, daemon=True)
        self.midi_thread.start()
        self.update_pad_colors()
        print("Mapper started")
        return True
    
    def stop(self):
        self.running = False
        self.stop_all_repeats()
        self.stop_all_animations()
        if self.midi_thread:
            self.midi_thread.join(timeout=1)
        self.clear_all_pads()
        print("Mapper stopped")
    
    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def notify_layer_change(self):
        event = {"type": "layer_change", "current_layer": self.current_layer}
        for callback in self.callbacks:
            callback(event)


# ============================================================================
# HTML TEMPLATE (embedded)
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Launchpad Mapper</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #00d4ff 0%, #ff00ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            color: #888;
            font-size: 1.1em;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 30px;
        }
        
        @media (max-width: 1000px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #00d4ff;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
            color: #000;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            color: #000;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
            color: #fff;
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffaa00 0%, #cc8800 100%);
            color: #000;
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .status-bar {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 15px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 20px;
            font-size: 13px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ff4444;
        }
        
        .status-dot.connected {
            background: #00ff88;
            box-shadow: 0 0 10px #00ff88;
        }
        
        .status-dot.running {
            background: #00d4ff;
            box-shadow: 0 0 10px #00d4ff;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .port-select {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 6px;
            color: #aaa;
            font-size: 13px;
            font-weight: 500;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: #e0e0e0;
            font-size: 14px;
            transition: border-color 0.2s ease;
        }
        
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #00d4ff;
        }
        
        .form-group input::placeholder {
            color: #666;
        }
        
        /* Launchpad Grid */
        .launchpad-container {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        
        .launchpad-grid {
            display: grid;
            grid-template-columns: repeat(9, 1fr);
            gap: 6px;
            max-width: 550px;
            padding: 25px;
            background: linear-gradient(145deg, #2a2a3e 0%, #1a1a2e 100%);
            border-radius: 20px;
            box-shadow: 
                0 20px 40px rgba(0, 0, 0, 0.5),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }
        
        .pad {
            width: 50px;
            height: 50px;
            border: 2px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            text-align: center;
            padding: 3px;
            word-break: break-word;
            background: #333;
            position: relative;
            overflow: hidden;
        }
        
        .pad::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 50%;
            background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 100%);
            border-radius: 4px 4px 0 0;
            pointer-events: none;
        }
        
        .pad:hover {
            transform: scale(1.08);
            border-color: rgba(255, 255, 255, 0.3);
            z-index: 1;
        }
        
        .pad.active {
            animation: padPress 0.15s ease;
        }
        
        .pad.selected {
            border-color: #00d4ff !important;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }
        
        .pad.scene {
            border-radius: 50%;
            width: 50px;
        }
        
        .pad.control {
            border-radius: 4px;
            height: 30px;
        }
        
        .pad.spacer {
            visibility: hidden;
        }

        .pad.dragging {
            opacity: 0.5;
            transform: scale(1.1);
        }

        .pad.drag-over {
            border-color: #00d4ff !important;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.8);
        }

        .pad-actions {
            position: absolute;
            top: 2px;
            right: 2px;
            display: none;
            gap: 2px;
            z-index: 10;
        }

        .pad:hover .pad-actions {
            display: flex;
        }

        .pad-action-btn {
            width: 16px;
            height: 16px;
            border-radius: 3px;
            border: none;
            cursor: pointer;
            font-size: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            padding: 0;
            line-height: 1;
        }

        .pad-action-btn.delete {
            background: rgba(255, 59, 48, 0.9);
            color: white;
        }

        .pad-action-btn.delete:hover {
            background: rgb(255, 59, 48);
            transform: scale(1.1);
        }

        .pad-action-btn.duplicate {
            background: rgba(0, 212, 255, 0.9);
            color: white;
        }

        .pad-action-btn.duplicate:hover {
            background: rgb(0, 212, 255);
            transform: scale(1.1);
        }

        @keyframes padPress {
            0% { transform: scale(1); }
            50% { transform: scale(0.92); }
            100% { transform: scale(1); }
        }
        
        /* Color Picker */
        .color-picker {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 6px;
        }
        
        .color-option {
            width: 100%;
            aspect-ratio: 1;
            border-radius: 6px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.15s ease;
            position: relative;
        }
        
        .color-option::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 50%;
            background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%);
            border-radius: 4px 4px 0 0;
            pointer-events: none;
        }
        
        .color-option:hover {
            transform: scale(1.15);
            z-index: 1;
        }
        
        .color-option.selected {
            border-color: #fff;
            box-shadow: 0 0 15px currentColor;
        }
        
        /* Editor Panel */
        .editor-panel {
            position: sticky;
            top: 20px;
        }
        
        .editor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .pad-note {
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            cursor: pointer;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        
        .editor-actions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 20px;
        }
        
        /* Profile Section */
        .profile-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        /* Log */
        .log {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            padding: 15px;
            height: 150px;
            overflow-y: auto;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
        }
        
        .log-entry {
            padding: 4px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            gap: 10px;
        }
        
        .log-time {
            color: #666;
        }
        
        .log-message {
            color: #aaa;
        }
        
        .log-entry.press .log-message {
            color: #00ff88;
        }
        
        .log-entry.release .log-message {
            color: #ffaa00;
        }
        
        .log-entry.error .log-message {
            color: #ff4444;
        }
        
        /* Key Hints */
        .key-hints {
            margin-top: 20px;
        }
        
        .key-hints h3 {
            font-size: 14px;
            color: #888;
            margin-bottom: 10px;
        }
        
        .hints-grid {
            display: grid;
            gap: 8px;
            font-size: 12px;
        }
        
        .hint-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .hint-label {
            color: #666;
            min-width: 80px;
        }
        
        code {
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', monospace;
            color: #00d4ff;
        }
        
        input[type="file"] {
            display: none;
        }
        
        .divider {
            height: 1px;
            background: rgba(255, 255, 255, 0.1);
            margin: 20px 0;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        /* Collapsible Sections */
        .collapsible-header {
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 15px;
        }

        .collapsible-header:hover {
            color: #00d4ff;
        }

        .collapse-icon {
            transition: transform 0.3s ease;
            font-size: 18px;
        }

        .collapse-icon.collapsed {
            transform: rotate(-90deg);
        }

        .collapsible-content {
            max-height: 2000px;
            overflow: hidden;
            transition: max-height 0.3s ease, opacity 0.3s ease;
            opacity: 1;
        }

        .collapsible-content.collapsed {
            max-height: 0;
            opacity: 0;
        }

        /* Compact Status Bar */
        .compact-status {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .status-row {
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }

        .status-row:last-child {
            margin-bottom: 0;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            padding: 4px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
        }

        /* Compact Form Row */
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }

        .form-row-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎹 Launchpad Mapper</h1>
            <p class="subtitle">Map your Launchpad Mini to keyboard shortcuts</p>
        </header>

        <!-- Compact Connection & Status -->
        <div class="compact-status">
            <div class="status-row">
                <div class="status-badge">
                    <div class="status-dot" id="connectionDot"></div>
                    <span id="connectionStatus">Disconnected</span>
                </div>
                <div class="status-badge">
                    <div class="status-dot" id="runningDot"></div>
                    <span id="runningStatus">Stopped</span>
                </div>
                <div class="status-badge">
                    <span>Mappings: <strong id="mappingCount">0</strong></span>
                </div>
                <div class="status-badge">
                    <span>Profile: <strong id="currentProfile">Default</strong></span>
                </div>
            </div>

            <div class="status-row">
                <div class="form-group" style="margin-bottom: 0; flex: 1; min-width: 200px;">
                    <select id="inputPort" style="padding: 8px 12px;">
                        <option value="">MIDI Input Port...</option>
                    </select>
                </div>
                <div class="form-group" style="margin-bottom: 0; flex: 1; min-width: 200px;">
                    <select id="outputPort" style="padding: 8px 12px;">
                        <option value="">MIDI Output Port...</option>
                    </select>
                </div>
                <button class="btn-success" onclick="quickStart()" id="quickStartBtn" style="padding: 8px 16px;">
                    <span>⚡</span> Connect & Start
                </button>
                <button class="btn-warning" onclick="stopMapper()" id="stopBtn" style="padding: 8px 16px;">
                    <span>⏹</span> Stop
                </button>
                <button class="btn-secondary" onclick="refreshPorts()" style="padding: 8px 16px;">
                    <span>↻</span>
                </button>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="left-panel">
                <div class="card">
                    <h2>🎮 Launchpad Grid</h2>
                    <p style="color: #666; margin-bottom: 15px; font-size: 13px;">Click a pad to configure its mapping. Colors and labels will appear on your physical Launchpad.</p>
                    
                    <div class="launchpad-container">
                        <div class="launchpad-grid" id="launchpadGrid">
                            <!-- Grid will be generated by JavaScript -->
                        </div>
                    </div>
                </div>
                
                <!-- Combined Preset & Profile Management -->
                <div class="card" style="margin-top: 20px;">
                    <h2>💾 Presets & Profiles</h2>

                    <!-- Quick Load Preset -->
                    <div class="form-row">
                        <div class="form-group" style="margin-bottom: 0;">
                            <select id="presetSelect">
                                <option value="">Load a preset...</option>
                            </select>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-success" onclick="loadPreset()" style="flex: 1;">
                                <span>📥</span> Load
                            </button>
                            <button class="btn-secondary" onclick="loadPresetList()">
                                <span>↻</span>
                            </button>
                        </div>
                    </div>

                    <div class="divider"></div>

                    <!-- Profile Actions -->
                    <div class="form-row">
                        <input type="text" id="profileName" value="Default" placeholder="Profile name" style="padding: 10px 12px;">
                        <select id="profileSelect" style="padding: 10px 12px;">
                            <option value="">Switch profile...</option>
                        </select>
                    </div>

                    <div class="form-row-3">
                        <button class="btn-primary" onclick="exportProfile()">
                            <span>📤</span> Export
                        </button>
                        <button class="btn-secondary" onclick="document.getElementById('importFile').click()">
                            <span>📥</span> Import
                        </button>
                        <button class="btn-secondary" onclick="switchProfile()">
                            <span>🔀</span> Switch
                        </button>
                        <input type="file" id="importFile" accept=".json" onchange="importProfile(event)">
                    </div>

                    <!-- Advanced Options (Collapsible) -->
                    <div class="collapsible-header" onclick="toggleSection('advancedOptions')">
                        <span style="font-size: 0.95em; color: #888;">⚙️ Advanced Options</span>
                        <span class="collapse-icon collapsed" id="advancedOptionsIcon">▼</span>
                    </div>
                    <div class="collapsible-content collapsed" id="advancedOptionsContent">
                        <!-- Layers -->
                        <div style="margin-bottom: 15px;">
                            <label style="color: #888; font-size: 13px; display: block; margin-bottom: 8px;">Layer: <strong id="currentLayer">Base</strong></label>
                            <div class="form-row">
                                <select id="layerSelect" style="padding: 8px 12px;">
                                    <option value="">Select layer...</option>
                                </select>
                                <input type="text" id="newLayerName" placeholder="New layer name" style="padding: 8px 12px;">
                            </div>
                            <div class="form-row-3">
                                <button class="btn-secondary" onclick="setLayer()" style="padding: 6px 10px; font-size: 13px;">
                                    Switch
                                </button>
                                <button class="btn-secondary" onclick="pushLayer()" style="padding: 6px 10px; font-size: 13px;">
                                    Push Layer
                                </button>
                                <button class="btn-secondary" onclick="popLayer()" style="padding: 6px 10px; font-size: 13px;">
                                    Pop Layer
                                </button>
                            </div>
                        </div>

                        <div class="divider"></div>

                        <!-- Auto Switch -->
                        <div>
                            <label class="checkbox-group" style="padding: 8px 0;">
                                <input type="checkbox" id="autoSwitchEnabled">
                                <span style="font-size: 13px;">Auto-switch by window title</span>
                            </label>
                            <div class="form-row" style="margin-top: 10px;">
                                <input type="text" id="autoMatch" placeholder="Window title contains..." style="padding: 8px 12px;">
                                <select id="autoProfileSelect" style="padding: 8px 12px;">
                                    <option value="">Select profile...</option>
                                </select>
                            </div>
                            <div class="form-row">
                                <button class="btn-success" onclick="addAutoRule()" style="padding: 6px 10px; font-size: 13px;">
                                    <span>➕</span> Add Rule
                                </button>
                                <button class="btn-secondary" onclick="saveAutoSwitchRules()" style="padding: 6px 10px; font-size: 13px;">
                                    <span>💾</span> Save Rules
                                </button>
                            </div>
                            <div class="log" id="autoRulesLog" style="height: 100px; margin-top: 10px;"></div>
                        </div>

                        <div class="divider"></div>

                        <button class="btn-danger" onclick="clearAllMappings()" style="width: 100%; padding: 8px;">
                            <span>🗑</span> Clear All Mappings
                        </button>
                    </div>
                </div>

                <!-- Event Log (Collapsible) -->
                <div class="card" style="margin-top: 20px;">
                    <div class="collapsible-header" onclick="toggleSection('eventLog')">
                        <h2 style="margin: 0;">📋 Event Log</h2>
                        <span class="collapse-icon collapsed" id="eventLogIcon">▼</span>
                    </div>
                    <div class="collapsible-content collapsed" id="eventLogContent">
                        <div class="log" id="eventLog"></div>
                    </div>
                </div>
            </div>
            
            <div class="right-panel">
                <div class="card editor-panel">
                    <div class="editor-header">
                        <h2>⚙️ Pad Configuration</h2>
                        <span class="pad-note" id="selectedPadNote">Select a pad</span>
                    </div>
                    
                    <div id="editorContent">
                        <div class="form-group">
                            <label>Label (shown on pad)</label>
                            <input type="text" id="padLabel" placeholder="e.g., Copy, Play, F5" maxlength="10">
                        </div>
                        
                        <div class="form-group">
                            <label>Key Combination</label>
                            <input type="text" id="keyCombo" placeholder="e.g., ctrl+c, space, shift+alt+f1">
                        </div>

                        <div class="form-group">
                            <label>Action Type</label>
                            <select id="actionType" onchange="updateActionFields()">
                                <option value="key">Key Combination</option>
                                <option value="macro">Macro Sequence</option>
                                <option value="layer">Go to Layer</option>
                                <option value="layer_up">Go Up One Layer</option>
                            </select>
                        </div>

                        <div class="form-group" id="targetLayerGroup" style="display: none;">
                            <label>Target Layer</label>
                            <input type="text" id="targetLayer" placeholder="e.g., Editing">
                        </div>

                        <!-- Macro Builder -->
                        <div id="macroBuilderGroup" style="display: none;">
                            <div class="form-group">
                                <label>Macro Steps</label>
                                <div id="macroSteps" style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 8px; max-height: 200px; overflow-y: auto;">
                                    <div style="color: #666; font-size: 12px; text-align: center; padding: 20px;">
                                        No macro steps yet. Add steps below.
                                    </div>
                                </div>
                            </div>

                            <div class="form-group">
                                <label>Add Step</label>
                                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 8px;">
                                    <input type="text" id="macroStepKey" placeholder="Key combo or 'wait'">
                                    <input type="number" id="macroStepDelay" placeholder="Delay (ms)" value="100" min="0" step="50">
                                </div>
                                <div style="margin-top: 8px; display: flex; gap: 8px;">
                                    <button class="btn-success" onclick="addMacroStep()" style="flex: 1; padding: 6px;">
                                        <span>➕</span> Add Step
                                    </button>
                                    <button class="btn-secondary" onclick="clearMacroSteps()" style="padding: 6px;">
                                        <span>🗑</span> Clear All
                                    </button>
                                </div>
                            </div>

                            <div style="background: rgba(0,212,255,0.1); padding: 10px; border-radius: 6px; margin-top: 10px;">
                                <div style="font-size: 12px; color: #00d4ff; margin-bottom: 6px;"><strong>💡 Macro Tips:</strong></div>
                                <ul style="font-size: 11px; color: #aaa; margin: 0; padding-left: 20px;">
                                    <li>Enter "wait" as key combo to add a pure delay</li>
                                    <li>Delay is time to wait AFTER the action (in milliseconds)</li>
                                    <li>Example: "ctrl+c" with 500ms delay, then "wait" with 1000ms</li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Pad Color</label>
                            <div class="color-picker" id="colorPicker">
                                <!-- Colors will be generated by JavaScript -->
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label class="checkbox-group">
                                <input type="checkbox" id="padEnabled" checked>
                                <span>Enabled</span>
                            </label>
                        </div>
                        
                        <div class="editor-actions">
                            <button class="btn-primary" onclick="saveMapping()">
                                <span>💾</span> Save Mapping
                            </button>
                            <button class="btn-danger" onclick="deleteMapping()">
                                <span>🗑</span> Delete
                            </button>
                        </div>
                        
                        <div class="divider"></div>
                        
                        <button class="btn-secondary" onclick="testKeyCombo()" style="width: 100%;">
                            <span>🧪</span> Test Key Combination
                        </button>
                    </div>
                    
                    <div class="key-hints">
                        <h3>Key Combination Examples</h3>
                        <div class="hints-grid">
                            <div class="hint-row">
                                <span class="hint-label">Single:</span>
                                <code>a</code> <code>space</code> <code>enter</code> <code>f1</code>
                            </div>
                            <div class="hint-row">
                                <span class="hint-label">Modifier:</span>
                                <code>ctrl+c</code> <code>shift+a</code> <code>alt+tab</code>
                            </div>
                            <div class="hint-row">
                                <span class="hint-label">Multi:</span>
                                <code>ctrl+shift+s</code> <code>ctrl+alt+del</code>
                            </div>
                            <div class="hint-row">
                                <span class="hint-label">Arrows:</span>
                                <code>up</code> <code>down</code> <code>left</code> <code>right</code>
                            </div>
                            <div class="hint-row">
                                <span class="hint-label">Media:</span>
                                <code>playpause</code> <code>next</code> <code>mute</code>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Grid layout matching Launchpad Mini (Programmer mode)
        const GRID_NOTES = [
            [91, 92, 93, 94, 95, 96, 97, 98, null],  // Top control row
            [81, 82, 83, 84, 85, 86, 87, 88, 89],
            [71, 72, 73, 74, 75, 76, 77, 78, 79],
            [61, 62, 63, 64, 65, 66, 67, 68, 69],
            [51, 52, 53, 54, 55, 56, 57, 58, 59],
            [41, 42, 43, 44, 45, 46, 47, 48, 49],
            [31, 32, 33, 34, 35, 36, 37, 38, 39],
            [21, 22, 23, 24, 25, 26, 27, 28, 29],
            [11, 12, 13, 14, 15, 16, 17, 18, 19],
        ];
        
        const COLORS = {{ colors | safe }};
        const COLOR_HEX = {{ color_hex | safe }};
        
        let selectedPad = null;
        let mappings = {};
        let selectedColor = 'green';
        let eventSource = null;
        let isConnected = false;
        let isRunning = false;
        let currentLayer = 'Base';
        let availableLayers = [];
        let autoRules = [];
        let autoSwitchAvailable = false;
        
        // Initialize the grid
        function initGrid() {
            const grid = document.getElementById('launchpadGrid');
            grid.innerHTML = '';

            GRID_NOTES.forEach((row, rowIndex) => {
                row.forEach((note, colIndex) => {
                    const pad = document.createElement('div');
                    if (note === null) {
                        pad.className = 'pad spacer';
                    } else {
                        pad.className = 'pad';
                        if (rowIndex === 0) pad.classList.add('control');
                        if (colIndex === 8) pad.classList.add('scene');
                        pad.dataset.note = note;
                        pad.draggable = true;

                        // Add action buttons container
                        const actionsDiv = document.createElement('div');
                        actionsDiv.className = 'pad-actions';

                        // Delete button
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'pad-action-btn delete';
                        deleteBtn.innerHTML = '×';
                        deleteBtn.title = 'Delete mapping';
                        deleteBtn.onclick = (e) => {
                            e.stopPropagation();
                            deletePadMapping(note);
                        };

                        // Duplicate button
                        const duplicateBtn = document.createElement('button');
                        duplicateBtn.className = 'pad-action-btn duplicate';
                        duplicateBtn.innerHTML = '⧉';
                        duplicateBtn.title = 'Duplicate mapping';
                        duplicateBtn.onclick = (e) => {
                            e.stopPropagation();
                            duplicatePadMapping(note);
                        };

                        actionsDiv.appendChild(deleteBtn);
                        actionsDiv.appendChild(duplicateBtn);
                        pad.appendChild(actionsDiv);

                        // Click handler
                        pad.onclick = () => selectPad(note);

                        // Double-click handler for layer actions
                        pad.addEventListener('dblclick', () => handlePadDoubleClick(note));

                        // Drag and drop handlers
                        pad.addEventListener('dragstart', handleDragStart);
                        pad.addEventListener('dragover', handleDragOver);
                        pad.addEventListener('dragleave', handleDragLeave);
                        pad.addEventListener('drop', handleDrop);
                        pad.addEventListener('dragend', handleDragEnd);
                    }
                    grid.appendChild(pad);
                });
            });
        }

        // Drag and drop variables
        let draggedNote = null;

        function handleDragStart(e) {
            draggedNote = parseInt(e.target.dataset.note);
            e.target.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedNote);
        }

        function handleDragOver(e) {
            if (e.preventDefault) {
                e.preventDefault();
            }
            e.dataTransfer.dropEffect = 'move';
            e.target.closest('.pad')?.classList.add('drag-over');
            return false;
        }

        function handleDragLeave(e) {
            e.target.closest('.pad')?.classList.remove('drag-over');
        }

        function handleDrop(e) {
            if (e.stopPropagation) {
                e.stopPropagation();
            }
            e.preventDefault();

            const targetPad = e.target.closest('.pad');
            targetPad?.classList.remove('drag-over');

            const targetNote = parseInt(targetPad?.dataset.note);
            if (draggedNote !== null && targetNote && draggedNote !== targetNote) {
                swapMappings(draggedNote, targetNote);
            }

            return false;
        }

        function handleDragEnd(e) {
            e.target.classList.remove('dragging');
            document.querySelectorAll('.pad').forEach(pad => {
                pad.classList.remove('drag-over');
            });
            draggedNote = null;
        }

        async function swapMappings(note1, note2) {
            const mapping1 = mappings[note1];
            const mapping2 = mappings[note2];

            if (mapping1) {
                mapping1.note = note2;
                mappings[note2] = mapping1;
            } else {
                delete mappings[note2];
            }

            if (mapping2) {
                mapping2.note = note1;
                mappings[note1] = mapping2;
            } else {
                delete mappings[note1];
            }

            updatePadDisplay();

            try {
                await fetch('/api/mapping', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mappings: Object.values(mappings), layer: currentLayer })
                });
                log(`Swapped mappings between ${note1} and ${note2}`);
            } catch (err) {
                log('Failed to save swapped mappings', 'error');
            }
        }

        function deletePadMapping(note) {
            if (!mappings[note]) {
                log('No mapping to delete', 'warn');
                return;
            }

            if (!confirm(`Delete mapping for pad ${note}?`)) {
                return;
            }

            delete mappings[note];
            updatePadDisplay();

            fetch('/api/mapping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mappings: Object.values(mappings), layer: currentLayer })
            }).then(() => {
                log(`Deleted mapping for pad ${note}`);
            }).catch(() => {
                log('Failed to save after delete', 'error');
            });
        }

        function duplicatePadMapping(note) {
            const sourceMapping = mappings[note];
            if (!sourceMapping) {
                log('No mapping to duplicate', 'warn');
                return;
            }

            // Find first empty pad
            let targetNote = null;
            for (let row of GRID_NOTES) {
                for (let n of row) {
                    if (n !== null && !mappings[n]) {
                        targetNote = n;
                        break;
                    }
                }
                if (targetNote) break;
            }

            if (!targetNote) {
                log('No empty pad available for duplication', 'warn');
                return;
            }

            // Create duplicate
            mappings[targetNote] = {
                ...sourceMapping,
                note: targetNote
            };

            updatePadDisplay();
            selectPad(targetNote);

            fetch('/api/mapping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mappings: Object.values(mappings), layer: currentLayer })
            }).then(() => {
                log(`Duplicated pad ${note} to ${targetNote}`);
            }).catch(() => {
                log('Failed to save duplicated mapping', 'error');
            });
        }

        // Handle double-click on pads to execute layer actions
        async function handlePadDoubleClick(note) {
            const mapping = mappings[note];
            if (!mapping) return;

            // Only handle layer-related actions
            if (mapping.action === 'layer' && mapping.target_layer) {
                log(`Double-click: Switching to layer "${mapping.target_layer}"`);
                try {
                    const response = await fetch('/api/layer/set', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ layer: mapping.target_layer })
                    });
                    if (response.ok) {
                        currentLayer = mapping.target_layer;
                        document.getElementById('currentLayer').textContent = currentLayer;
                        await loadMappings();
                        log(`Switched to layer: ${currentLayer}`);
                    }
                } catch (err) {
                    log('Failed to switch layer', 'error');
                }
            } else if (mapping.action === 'layer_up') {
                log('Double-click: Going up one layer');
                try {
                    const response = await fetch('/api/layer/pop', {
                        method: 'POST'
                    });
                    if (response.ok) {
                        const data = await response.json();
                        currentLayer = data.current_layer || 'Base';
                        document.getElementById('currentLayer').textContent = currentLayer;
                        await loadMappings();
                        log(`Layer popped, now on: ${currentLayer}`);
                    }
                } catch (err) {
                    log('Failed to pop layer', 'error');
                }
            }
        }

        // Initialize color picker
        function initColorPicker() {
            const picker = document.getElementById('colorPicker');
            picker.innerHTML = '';
            
            // Only show main colors (not dim variants)
            const mainColors = Object.keys(COLOR_HEX).filter(c => !c.includes('dim'));
            
            mainColors.forEach(name => {
                const hex = COLOR_HEX[name];
                const option = document.createElement('div');
                option.className = 'color-option';
                option.style.backgroundColor = hex;
                option.style.color = hex;
                option.title = name;
                option.onclick = () => selectColor(name);
                if (name === selectedColor) option.classList.add('selected');
                picker.appendChild(option);
            });
        }
        
        function selectColor(color) {
            selectedColor = color;
            document.querySelectorAll('.color-option').forEach(el => {
                el.classList.toggle('selected', el.title === color);
            });
        }
        
        function selectPad(note) {
            selectedPad = note;
            document.querySelectorAll('.pad').forEach(el => {
                el.classList.toggle('selected', el.dataset.note == note);
            });

            document.getElementById('selectedPadNote').textContent = `Note: ${note}`;

            // Load existing mapping
            const mapping = mappings[note];
            if (mapping) {
                document.getElementById('padLabel').value = mapping.label || '';
                document.getElementById('keyCombo').value = mapping.key_combo || '';
                document.getElementById('padEnabled').checked = mapping.enabled !== false;
                selectColor(mapping.color || 'green');
                document.getElementById('actionType').value = mapping.action || 'key';
                document.getElementById('targetLayer').value = mapping.target_layer || '';

                // Load macro steps if this is a macro action
                if (mapping.action === 'macro' && mapping.macro_steps) {
                    currentMacroSteps = mapping.macro_steps.map(step => ({
                        key_combo: step.key_combo || '',
                        delay_after: step.delay_after || 0
                    }));
                } else {
                    currentMacroSteps = [];
                }
                updateMacroStepsDisplay();
            } else {
                document.getElementById('padLabel').value = '';
                document.getElementById('keyCombo').value = '';
                document.getElementById('padEnabled').checked = true;
                selectColor('green');
                document.getElementById('actionType').value = 'key';
                document.getElementById('targetLayer').value = '';
                currentMacroSteps = [];
                updateMacroStepsDisplay();
            }
            updateActionFields();
        }
        
        function updatePadDisplay() {
            document.querySelectorAll('.pad').forEach(el => {
                const note = parseInt(el.dataset.note);
                if (!isNaN(note) && mappings[note]) {
                    const mapping = mappings[note];
                    const label = mapping.label || (mapping.action === 'layer' ? `↧ ${mapping.target_layer || ''}` : '');
                    const hexColor = mapping.color && mapping.color.startsWith('#')
                        ? mapping.color
                        : (COLOR_HEX[mapping.color] || '#333');
                    el.style.backgroundColor = hexColor;
                    el.textContent = label;
                    el.style.color = isLightColor(hexColor) ? '#000' : '#fff';
                } else if (!isNaN(note)) {
                    el.style.backgroundColor = '#333';
                    el.textContent = '';
                    el.style.color = '#fff';
                }
            });
            
            // Update mapping count
            document.getElementById('mappingCount').textContent = Object.keys(mappings).length;
        }
        
        function isLightColor(hex) {
            if (!hex) return false;
            const c = hex.substring(1);
            const rgb = parseInt(c, 16);
            const r = (rgb >> 16) & 0xff;
            const g = (rgb >> 8) & 0xff;
            const b = (rgb >> 0) & 0xff;
            const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            return luma > 128;
        }
        
        async function saveMapping() {
            if (selectedPad === null) {
                log('Please select a pad first', 'error');
                return;
            }

            const keyCombo = document.getElementById('keyCombo').value.trim();
            const actionType = document.getElementById('actionType').value;
            const targetLayer = document.getElementById('targetLayer').value.trim();

            if (actionType === 'key' && !keyCombo) {
                log('Please enter a key combination', 'error');
                return;
            }
            if (actionType === 'layer' && !targetLayer) {
                log('Please enter a target layer', 'error');
                return;
            }
            if (actionType === 'macro' && currentMacroSteps.length === 0) {
                log('Please add at least one macro step', 'error');
                return;
            }

            const mapping = {
                note: selectedPad,
                label: document.getElementById('padLabel').value,
                key_combo: keyCombo,
                color: selectedColor,
                enabled: document.getElementById('padEnabled').checked,
                action: actionType,
                target_layer: targetLayer,
                layer: currentLayer
            };

            // Add macro steps if action is macro
            if (actionType === 'macro') {
                mapping.macro_steps = currentMacroSteps;
            }
            
            try {
                const response = await fetch('/api/mapping', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(mapping)
                });
                
                if (response.ok) {
                    mappings[selectedPad] = mapping;
                    updatePadDisplay();
                    log(`Saved: Pad ${selectedPad} → ${keyCombo}`, 'success');
                }
            } catch (e) {
                log('Failed to save mapping', 'error');
            }
        }
        
        async function deleteMapping() {
            if (selectedPad === null) {
                log('Please select a pad first', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/mapping/${selectedPad}?layer=${encodeURIComponent(currentLayer)}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    delete mappings[selectedPad];
                    updatePadDisplay();
                    document.getElementById('padLabel').value = '';
                    document.getElementById('keyCombo').value = '';
                    log(`Deleted mapping for pad ${selectedPad}`);
                }
            } catch (e) {
                log('Failed to delete mapping', 'error');
            }
        }
        
        async function testKeyCombo() {
            const combo = document.getElementById('keyCombo').value.trim();
            if (!combo) {
                log('Enter a key combination to test', 'error');
                return;
            }
            
            try {
                await fetch('/api/test-key', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({combo})
                });
                log(`Tested: ${combo}`);
            } catch (e) {
                log('Failed to test key', 'error');
            }
        }
        
        // Toggle collapsible sections
        function toggleSection(sectionId) {
            const content = document.getElementById(sectionId + 'Content');
            const icon = document.getElementById(sectionId + 'Icon');

            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                icon.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                icon.classList.add('collapsed');
            }
        }

        // Quick start: connect and start in one click
        async function quickStart() {
            await connect();
            // Wait a moment for connection to establish
            setTimeout(async () => {
                await startMapper();
            }, 500);
        }

        async function connect() {
            const inputPort = document.getElementById('inputPort').value;
            const outputPort = document.getElementById('outputPort').value;

            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({input_port: inputPort, output_port: outputPort})
                });
                
                const data = await response.json();
                isConnected = data.connected;
                updateStatus();
                if (data.connected) {
                    log(data.message, 'success');
                } else {
                    log(data.error || data.message, 'error');
                }
            } catch (e) {
                log('Failed to connect', 'error');
            }
        }
        
        async function disconnect() {
            try {
                const response = await fetch('/api/disconnect', {method: 'POST'});
                const data = await response.json();
                isConnected = false;
                isRunning = false;
                updateStatus();
                log(data.message);
            } catch (e) {
                log('Failed to disconnect', 'error');
            }
        }
        
        async function startMapper() {
            try {
                const response = await fetch('/api/start', {method: 'POST'});
                const data = await response.json();
                isRunning = data.started;
                updateStatus();
                log(data.message, data.started ? 'success' : 'error');
                if (data.started) {
                    startEventStream();
                }
            } catch (e) {
                log('Failed to start', 'error');
            }
        }
        
        async function stopMapper() {
            try {
                const response = await fetch('/api/stop', {method: 'POST'});
                const data = await response.json();
                isRunning = false;
                updateStatus();
                log(data.message);
                stopEventStream();
            } catch (e) {
                log('Failed to stop', 'error');
            }
        }
        
        function isLaunchpadPort(port) {
            const normalized = port.toLowerCase().replace(/\s+/g, '');
            const keywords = [
                'launchpad',
                'lpmini',
                'lpminimk',
                'lpmk',
                'lppro',
                'launchpadx',
                'novation'
            ];
            return keywords.some(keyword => normalized.includes(keyword));
        }

        async function refreshPorts() {
            try {
                const response = await fetch('/api/ports');
                const data = await response.json();

                const inputSelect = document.getElementById('inputPort');
                const outputSelect = document.getElementById('outputPort');

                inputSelect.innerHTML = '<option value="">Select input port...</option>';
                outputSelect.innerHTML = '<option value="">Select output port...</option>';

                data.inputs.forEach(port => {
                    const option = document.createElement('option');
                    option.value = port;
                    option.textContent = port;
                    if (isLaunchpadPort(port)) option.selected = true;
                    inputSelect.appendChild(option);
                });

                data.outputs.forEach(port => {
                    const option = document.createElement('option');
                    option.value = port;
                    option.textContent = port;
                    if (isLaunchpadPort(port)) option.selected = true;
                    outputSelect.appendChild(option);
                });

                if (data.inputs.length === 0 && data.outputs.length === 0 && data.error) {
                    log(data.error, 'error');
                } else {
                    log(`Found ${data.inputs.length} input(s), ${data.outputs.length} output(s)`);
                }
            } catch (e) {
                log('Failed to refresh ports: ' + e.message, 'error');
            }
        }
        
        async function loadMappings() {
            try {
                const response = await fetch('/api/profile');
                const data = await response.json();
                mappings = {};
                const activeLayer = data.active_layer || currentLayer || data.base_layer || 'Base';
                const layerMappings = data.layers ? data.layers[activeLayer] : data.mappings;
                Object.values(layerMappings || {}).forEach(m => {
                    mappings[m.note] = m;
                });
                document.getElementById('profileName').value = data.name || 'Default';
                document.getElementById('profileDescription').value = data.description || '';
                document.getElementById('currentProfile').textContent = data.name || 'Default';
                currentLayer = activeLayer;
                document.getElementById('currentLayer').textContent = currentLayer;
                updatePadDisplay();
            } catch (e) {
                log('Failed to load profile', 'error');
            }
        }
        
        async function exportProfile() {
            const name = document.getElementById('profileName').value || 'Default';
            
            try {
                const response = await fetch(`/api/profile/export?name=${encodeURIComponent(name)}`);
                const data = await response.json();
                
                const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `launchpad-profile-${name.replace(/[^a-z0-9]/gi, '_')}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                log(`Exported profile: ${name}`, 'success');
            } catch (e) {
                log('Failed to export profile', 'error');
            }
        }
        
        async function importProfile(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            try {
                const text = await file.text();
                const data = JSON.parse(text);
                
                const response = await fetch('/api/profile/import', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: text
                });
                
                if (response.ok) {
                    await loadMappings();
                    await loadProfiles();
                    log(`Imported profile: ${data.name || 'Unknown'}`, 'success');
                }
            } catch (e) {
                log('Failed to import profile', 'error');
            }
            
            event.target.value = '';
        }
        
        async function clearAllMappings() {
            if (!confirm('Clear all mappings? This cannot be undone.')) return;
            
            try {
                const response = await fetch('/api/clear', {method: 'POST'});
                if (response.ok) {
                    mappings = {};
                    updatePadDisplay();
                    log('All mappings cleared');
                }
            } catch (e) {
                log('Failed to clear mappings', 'error');
            }
        }

        // Macro steps storage
        let currentMacroSteps = [];

        function updateActionFields() {
            const actionType = document.getElementById('actionType').value;
            const targetGroup = document.getElementById('targetLayerGroup');
            const macroGroup = document.getElementById('macroBuilderGroup');
            const keyCombo = document.getElementById('keyCombo');

            if (actionType === 'layer') {
                targetGroup.style.display = 'block';
                macroGroup.style.display = 'none';
                keyCombo.placeholder = 'Optional';
            } else if (actionType === 'macro') {
                targetGroup.style.display = 'none';
                macroGroup.style.display = 'block';
                keyCombo.placeholder = 'Not used for macros';
                keyCombo.value = '';
            } else {
                targetGroup.style.display = 'none';
                macroGroup.style.display = 'none';
                keyCombo.placeholder = 'e.g., ctrl+c, space, shift+alt+f1';
            }
        }

        function addMacroStep() {
            const keyCombo = document.getElementById('macroStepKey').value.trim();
            const delay = parseInt(document.getElementById('macroStepDelay').value) || 0;

            if (!keyCombo) {
                log('Please enter a key combo or "wait"', 'warn');
                return;
            }

            currentMacroSteps.push({
                key_combo: keyCombo,
                delay_after: delay / 1000 // Convert ms to seconds
            });

            updateMacroStepsDisplay();

            // Clear inputs
            document.getElementById('macroStepKey').value = '';
            document.getElementById('macroStepDelay').value = '100';
            log(`Added macro step: ${keyCombo} (${delay}ms delay)`);
        }

        function removeMacroStep(index) {
            currentMacroSteps.splice(index, 1);
            updateMacroStepsDisplay();
            log('Removed macro step');
        }

        function clearMacroSteps() {
            if (currentMacroSteps.length === 0) return;
            if (confirm('Clear all macro steps?')) {
                currentMacroSteps = [];
                updateMacroStepsDisplay();
                log('Cleared all macro steps');
            }
        }

        function updateMacroStepsDisplay() {
            const container = document.getElementById('macroSteps');

            if (currentMacroSteps.length === 0) {
                container.innerHTML = '<div style="color: #666; font-size: 12px; text-align: center; padding: 20px;">No macro steps yet. Add steps below.</div>';
                return;
            }

            container.innerHTML = currentMacroSteps.map((step, index) => {
                const isWait = step.key_combo.toLowerCase() === 'wait';
                const icon = isWait ? '⏱️' : '⌨️';
                const label = isWait ? 'Wait' : step.key_combo;
                const delayMs = Math.round(step.delay_after * 1000);

                return `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; margin-bottom: 4px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; flex: 1;">
                            <span style="font-size: 14px;">${icon}</span>
                            <span style="color: #00d4ff; font-family: monospace;">${index + 1}.</span>
                            <code style="color: ${isWait ? '#ffaa00' : '#00ff88'};">${label}</code>
                            ${delayMs > 0 ? `<span style="color: #666;">→ ${delayMs}ms</span>` : ''}
                        </div>
                        <button onclick="removeMacroStep(${index})" style="background: rgba(255,59,48,0.8); color: white; border: none; border-radius: 4px; padding: 2px 6px; cursor: pointer; font-size: 11px;">×</button>
                    </div>
                `;
            }).join('');
        }

        async function loadLayers() {
            try {
                const response = await fetch('/api/layers');
                const data = await response.json();
                availableLayers = data.layers || [];
                currentLayer = data.current_layer || currentLayer;
                document.getElementById('currentLayer').textContent = currentLayer;
                const select = document.getElementById('layerSelect');
                select.innerHTML = '';
                availableLayers.forEach(layer => {
                    const option = document.createElement('option');
                    option.value = layer;
                    option.textContent = layer;
                    if (layer === currentLayer) option.selected = true;
                    select.appendChild(option);
                });
            } catch (e) {
                log('Failed to load layers', 'error');
            }
        }

        async function pushLayer() {
            const newLayer = document.getElementById('newLayerName').value.trim();
            const selected = document.getElementById('layerSelect').value;
            const layer = newLayer || selected;
            if (!layer) {
                log('Provide a layer name', 'error');
                return;
            }
            try {
                const response = await fetch('/api/layer/push', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({layer})
                });
                if (response.ok) {
                    await loadLayers();
                    await loadMappings();
                    log(`Entered layer: ${layer}`, 'success');
                }
            } catch (e) {
                log('Failed to enter layer', 'error');
            }
        }

        async function popLayer() {
            try {
                const response = await fetch('/api/layer/pop', {method: 'POST'});
                if (response.ok) {
                    await loadLayers();
                    await loadMappings();
                    log('Returned to previous layer', 'success');
                }
            } catch (e) {
                log('Failed to go up a layer', 'error');
            }
        }

        async function setLayer() {
            const selected = document.getElementById('layerSelect').value;
            if (!selected) {
                log('Select a layer', 'error');
                return;
            }
            try {
                const response = await fetch('/api/layer/set', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({layer: selected})
                });
                if (response.ok) {
                    await loadLayers();
                    await loadMappings();
                    log(`Switched to layer: ${selected}`, 'success');
                }
            } catch (e) {
                log('Failed to switch layer', 'error');
            }
        }

        async function loadProfiles() {
            try {
                const response = await fetch('/api/profiles');
                const data = await response.json();
                const profileSelect = document.getElementById('profileSelect');
                const autoSelect = document.getElementById('autoProfileSelect');
                profileSelect.innerHTML = '';
                autoSelect.innerHTML = '';
                (data.profiles || []).forEach(name => {
                    const option = document.createElement('option');
                    option.value = name;
                    option.textContent = name;
                    if (name === data.active_profile) option.selected = true;
                    profileSelect.appendChild(option);
                    const autoOption = option.cloneNode(true);
                    autoSelect.appendChild(autoOption);
                });
            } catch (e) {
                log('Failed to load profiles', 'error');
            }
        }

        async function switchProfile() {
            const name = document.getElementById('profileSelect').value;
            if (!name) {
                log('Select a profile', 'error');
                return;
            }
            try {
                const response = await fetch('/api/profile/switch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name})
                });
                if (response.ok) {
                    await loadMappings();
                    await loadLayers();
                    log(`Switched to profile: ${name}`, 'success');
                } else {
                    const data = await response.json();
                    log(data.error || 'Failed to switch profile', 'error');
                }
            } catch (e) {
                log('Failed to switch profile', 'error');
            }
        }

        async function loadAutoSwitch() {
            try {
                const response = await fetch('/api/profile/auto');
                const data = await response.json();
                autoRules = data.rules || [];
                autoSwitchAvailable = data.available;
                const checkbox = document.getElementById('autoSwitchEnabled');
                checkbox.disabled = !autoSwitchAvailable;
                checkbox.checked = data.enabled && autoSwitchAvailable;
                renderAutoRules();
            } catch (e) {
                log('Failed to load auto-switch settings', 'error');
            }
        }

        function renderAutoRules() {
            const logEl = document.getElementById('autoRulesLog');
            logEl.innerHTML = '';
            if (!autoRules.length) {
                logEl.textContent = 'No auto-switch rules added.';
                return;
            }
            autoRules.forEach((rule, index) => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                const msg = document.createElement('span');
                msg.className = 'log-message';
                msg.textContent = `${rule.match} → ${rule.profile}`;
                const remove = document.createElement('button');
                remove.className = 'btn-danger';
                remove.textContent = 'Remove';
                remove.style.marginLeft = 'auto';
                remove.onclick = () => removeAutoRule(index);
                entry.appendChild(msg);
                entry.appendChild(remove);
                logEl.appendChild(entry);
            });
        }

        function addAutoRule() {
            const match = document.getElementById('autoMatch').value.trim();
            const profile = document.getElementById('autoProfileSelect').value;
            if (!match || !profile) {
                log('Provide a match text and profile', 'error');
                return;
            }
            autoRules.push({match, profile});
            document.getElementById('autoMatch').value = '';
            renderAutoRules();
        }

        function removeAutoRule(index) {
            autoRules.splice(index, 1);
            renderAutoRules();
        }

        async function saveAutoSwitchRules() {
            if (!autoSwitchAvailable) {
                log('Auto-switch not available on this platform', 'error');
                return;
            }
            const enabled = document.getElementById('autoSwitchEnabled').checked;
            try {
                const response = await fetch('/api/profile/auto', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({enabled, rules: autoRules})
                });
                if (response.ok) {
                    log('Auto-switch rules saved', 'success');
                } else {
                    const data = await response.json();
                    log(data.error || 'Failed to save auto-switch rules', 'error');
                }
            } catch (e) {
                log('Failed to save auto-switch rules', 'error');
            }
        }
        
        function updateStatus() {
            const connectionDot = document.getElementById('connectionDot');
            const runningDot = document.getElementById('runningDot');
            
            connectionDot.classList.toggle('connected', isConnected);
            document.getElementById('connectionStatus').textContent = isConnected ? 'Connected' : 'Disconnected';
            
            runningDot.classList.toggle('running', isRunning);
            document.getElementById('runningStatus').textContent = isRunning ? 'Running' : 'Stopped';
            
            // Update button states
            document.getElementById('startBtn').disabled = !isConnected || isRunning;
            document.getElementById('stopBtn').disabled = !isRunning;
            document.getElementById('disconnectBtn').disabled = !isConnected;
        }
        
        function log(message, type = '') {
            const logEl = document.getElementById('eventLog');
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            
            const time = document.createElement('span');
            time.className = 'log-time';
            time.textContent = new Date().toLocaleTimeString();
            
            const msg = document.createElement('span');
            msg.className = 'log-message';
            msg.textContent = message;
            
            entry.appendChild(time);
            entry.appendChild(msg);
            logEl.insertBefore(entry, logEl.firstChild);
            
            // Keep only last 100 entries
            while (logEl.children.length > 100) {
                logEl.removeChild(logEl.lastChild);
            }
        }
        
        function startEventStream() {
            if (eventSource) eventSource.close();
            
            eventSource = new EventSource('/api/events');
            
            eventSource.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'pad_press') {
                    const pad = document.querySelector(`.pad[data-note="${data.note}"]`);
                    if (pad) {
                        pad.classList.add('active');
                        setTimeout(() => pad.classList.remove('active'), 150);
                    }
                    
                    const mapping = mappings[data.note];
                    if (mapping) {
                        log(`Pad ${data.note} → ${mapping.key_combo}`, 'press');
                    } else {
                        log(`Pad ${data.note} pressed (no mapping)`, 'press');
                    }
                } else if (data.type === 'layer_change') {
                    currentLayer = data.current_layer || currentLayer;
                    document.getElementById('currentLayer').textContent = currentLayer;
                    await loadLayers();
                    await loadMappings();
                    log(`Active layer: ${currentLayer}`, 'success');
                } else if (data.type === 'pad_release') {
                    // Optional: handle release events
                }
            };
            
            eventSource.onerror = () => {
                log('Event stream disconnected', 'error');
            };
        }
        
        function stopEventStream() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }
        
        // Keyboard shortcut to save (Ctrl+S)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                if (selectedPad !== null) {
                    saveMapping();
                }
            }
        });
        
        async function loadPresetList() {
            try {
                const response = await fetch('/api/presets');
                const data = await response.json();
                const select = document.getElementById('presetSelect');
                select.innerHTML = '<option value="">Select a preset...</option>';
                (data.presets || []).forEach(preset => {
                    const option = document.createElement('option');
                    option.value = preset.filename;
                    option.textContent = preset.name;
                    select.appendChild(option);
                });
                log(`Found ${data.presets.length} preset(s)`);
            } catch (e) {
                log('Failed to load presets', 'error');
            }
        }

        async function loadPreset() {
            const filename = document.getElementById('presetSelect').value;
            if (!filename) {
                log('Select a preset first', 'error');
                return;
            }

            try {
                const response = await fetch(`/api/presets/${filename}`);
                const presetData = await response.json();

                if (presetData.error) {
                    log(presetData.error, 'error');
                    return;
                }

                // Import the preset as current profile
                const importResponse = await fetch('/api/profile/import', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(presetData)
                });

                if (importResponse.ok) {
                    await loadMappings();
                    await loadLayers();
                    await loadProfiles();
                    log(`Loaded preset: ${presetData.name}`, 'success');
                } else {
                    log('Failed to load preset', 'error');
                }
            } catch (e) {
                log('Failed to load preset', 'error');
            }
        }

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {
            initGrid();
            initColorPicker();
            refreshPorts();
            loadMappings();
            loadLayers();
            loadProfiles();
            loadAutoSwitch();
            loadPresetList();
            updateStatus();
            log('Launchpad Mapper initialized');
        });
    </script>
</body>
</html>

'''


# ============================================================================
# FLASK APPLICATION
# ============================================================================

app = Flask(__name__)
CORS(app)

mapper = LaunchpadMapper()
event_queues = []


def broadcast_event(data):
    for q in event_queues:
        try:
            q.put_nowait(data)
        except queue.Full:
            pass


mapper.add_callback(broadcast_event)


@app.route('/')
def index():
    return HTML_TEMPLATE


@app.route('/api/ports')
def get_ports():
    ports = mapper.get_available_ports()
    # Add helpful message if no ports found
    has_ports = len(ports["inputs"]) > 0 or len(ports["outputs"]) > 0
    response = {
        **ports,
        "error": None if has_ports else "No MIDI ports detected. Please ensure:\n1. A MIDI device is connected\n2. MIDI drivers are installed\n3. The device is powered on"
    }
    return jsonify(response)


@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json or {}
    result = mapper.connect(data.get('input_port'), data.get('output_port'))
    return jsonify({
        "connected": result.get("success", False),
        "message": result.get("message", "Connection failed"),
        "error": result.get("error"),
    })


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    mapper.disconnect()
    return jsonify({"message": "Disconnected"})


@app.route('/api/start', methods=['POST'])
def api_start():
    success = mapper.start()
    return jsonify({"started": success, "message": "Mapper started" if success else "Connect MIDI first"})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    mapper.stop()
    return jsonify({"message": "Mapper stopped"})


@app.route('/api/mapping', methods=['POST'])
def save_mapping():
    data = request.json
    mapping = PadMapping(
        note=data['note'],
        key_combo=data['key_combo'],
        color=data['color'],
        label=data.get('label', ''),
        enabled=data.get('enabled', True),
        repeat_enabled=data.get('repeat_enabled', False),
        repeat_delay=data.get('repeat_delay', 0.5),
        repeat_interval=data.get('repeat_interval', 0.05)
    )
    mapper.profile.add_mapping(mapping)
    if mapper.running:
        mapper.set_pad_color(mapping.note, mapping.color if mapping.enabled else 'off')
    return jsonify({"success": True})


@app.route('/api/mapping/<int:note>', methods=['DELETE'])
def delete_mapping(note):
    mapper.profile.remove_mapping(note)
    if mapper.running:
        mapper.set_pad_color(note, 'off')
    return jsonify({"success": True})


@app.route('/api/profile')
def get_profile():
    profile_data = mapper.profile.to_dict()
    profile_data["active_layer"] = mapper.current_layer
    return jsonify(profile_data)


@app.route('/api/profile/export')
def export_profile():
    name = request.args.get('name')
    if name:
        mapper.profile.name = name
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile/import', methods=['POST'])
def import_profile():
    data = request.get_json(silent=True)
    if data is None:
        raw = request.data.decode('utf-8') if request.data else ''
        if not raw:
            return jsonify({"success": False, "error": "No profile data provided"}), 400
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return jsonify({"success": False, "error": f"Invalid JSON: {exc}"}), 400
    mapper.set_profile(Profile.from_dict(data))
    return jsonify({"success": True, "profile": mapper.profile.to_dict()})


@app.route('/api/clear', methods=['POST'])
def clear_mappings():
    mapper.set_profile(Profile(mapper.profile.name))
    if mapper.running:
        mapper.clear_all_pads()
    return jsonify({"success": True})


@app.route('/api/layers')
def get_layers():
    return jsonify({
        "layers": sorted(mapper.profile.layers.keys()),
        "current_layer": mapper.current_layer
    })


@app.route('/api/layer/push', methods=['POST'])
def push_layer():
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    layer = data.get("layer")
    if not layer:
        return jsonify({"success": False, "error": "No layer provided"}), 400
    mapper.set_layer(layer)
    return jsonify({"success": True, "current_layer": mapper.current_layer})


@app.route('/api/test-key', methods=['POST'])
def test_key():
    data = request.json
    combo = data.get('combo', '')
    if combo:
        mapper.execute_key_combo(combo)
    return jsonify({"success": True})


@app.route('/api/events')
def events():
    def generate():
        q = queue.Queue(maxsize=100)
        event_queues.append(q)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            event_queues.remove(q)
    return Response(generate(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


def main():
    print("\n" + "=" * 60)
    print("  Launchpad Mapper (Windows Enhanced)")
    print("=" * 60)
    print("\n  Features:")
    print("  - Sends keystrokes to active window (Windows compatible)")
    print("  - Hex color picker + preset palette")
    print("  - Key repeat (hold pad to repeat)")
    print("\n  Open http://localhost:5000 in your browser")
    print("  Press Ctrl+C to quit\n")
    
    # Note about running as admin on Windows
    if platform.system() == 'Windows':
        print("  Note: If keys aren't working, try running as Administrator")
        print()
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == '__main__':
    main()
