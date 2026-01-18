#!/usr/bin/env python3
"""
Launchpad Mini MIDI to Keyboard Mapper
Improved version with Windows support, hex colors, and key repeat
"""

import threading
import time
from dataclasses import dataclass, asdict
from functools import lru_cache
from itertools import chain
from typing import Optional, Dict, List, Callable

import mido
from mido import Message

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
    macro_steps: Optional[List[Dict[str, any]]] = None  # List of {key_combo, delay_after}
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
        
    def get_available_ports(self) -> Dict[str, List[str]]:
        return {
            "inputs": list(mido.get_input_names()),
            "outputs": list(mido.get_output_names())
        }
    
    def find_launchpad_ports(self) -> Dict[str, Optional[str]]:
        ports = self.get_available_ports()
        result = {"input": None, "output": None}
        for port in ports["inputs"]:
            if "launchpad" in port.lower():
                result["input"] = port
                break
        for port in ports["outputs"]:
            if "launchpad" in port.lower():
                result["output"] = port
                break
        return result
    
    def connect(self, input_port: str = None, output_port: str = None) -> bool:
        try:
            if self.input_port or self.output_port:
                self.disconnect()
            if not input_port or not output_port:
                detected = self.find_launchpad_ports()
                input_port = input_port or detected["input"]
                output_port = output_port or detected["output"]
            
            if input_port:
                self.input_port = mido.open_input(input_port)
                print(f"Connected to input: {input_port}")
            
            if output_port:
                self.output_port = mido.open_output(output_port)
                print(f"Connected to output: {output_port}")
                
            return self.input_port is not None
        except Exception as e:
            print(f"Error connecting to MIDI: {e}")
            return False
    
    def disconnect(self):
        self.stop()
        if self.input_port:
            self.input_port.close()
            self.input_port = None
        if self.output_port:
            self.output_port.close()
            self.output_port = None
    
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

    def pop_layer(self):
        if len(self.layer_stack) > 1:
            self.layer_stack.pop()
            if self.running:
                self.update_pad_colors()

    def set_layer(self, layer: str):
        self.profile.ensure_layer(layer)
        self.layer_stack = [layer]
        if self.running:
            self.update_pad_colors()

    def set_profile(self, profile: Profile):
        self.profile = profile
        self.layer_stack = [profile.base_layer]
        if self.running:
            self.update_pad_colors()
    
    def execute_key_combo(self, combo: str):
        """Execute a keyboard shortcut using the keyboard library (works on Windows)."""
        try:
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
        while self.running and self.input_port:
            for msg in self.input_port.iter_pending():
                self.handle_midi_message(msg)
            time.sleep(0.001)
    
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
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 30px; }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #00d4ff 0%, #ff00ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .subtitle { color: #888; font-size: 1.1em; }
        .main-grid { display: grid; grid-template-columns: 1fr 420px; gap: 30px; }
        @media (max-width: 1000px) { .main-grid { grid-template-columns: 1fr; } }
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h2 { font-size: 1.2em; margin-bottom: 15px; color: #00d4ff; display: flex; align-items: center; gap: 10px; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
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
        .btn-primary { background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); color: #000; }
        .btn-success { background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%); color: #000; }
        .btn-danger { background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%); color: #fff; }
        .btn-warning { background: linear-gradient(135deg, #ffaa00 0%, #cc8800 100%); color: #000; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: #e0e0e0; border: 1px solid rgba(255, 255, 255, 0.2); }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .status-bar { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        .status-item { display: flex; align-items: center; gap: 8px; padding: 8px 15px; background: rgba(0, 0, 0, 0.3); border-radius: 20px; font-size: 13px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #ff4444; }
        .status-dot.connected { background: #00ff88; box-shadow: 0 0 10px #00ff88; }
        .status-dot.running { background: #00d4ff; box-shadow: 0 0 10px #00d4ff; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .port-select { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 6px; color: #aaa; font-size: 13px; font-weight: 500; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: #e0e0e0;
            font-size: 14px;
        }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #00d4ff; }
        .form-group input[type="color"] {
            padding: 0;
            width: 60px;
            height: 40px;
            border: none;
            cursor: pointer;
        }
        .form-group input[type="number"] { width: 100px; }
        .launchpad-container { display: flex; justify-content: center; margin-bottom: 20px; }
        .launchpad-grid {
            display: grid;
            grid-template-columns: repeat(9, 1fr);
            gap: 6px;
            max-width: 550px;
            padding: 25px;
            background: linear-gradient(145deg, #2a2a3e 0%, #1a1a2e 100%);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
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
            top: 0; left: 0; right: 0;
            height: 50%;
            background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 100%);
            border-radius: 4px 4px 0 0;
            pointer-events: none;
        }
        .pad:hover { transform: scale(1.08); border-color: rgba(255, 255, 255, 0.3); z-index: 1; }
        .pad.active { animation: padPress 0.15s ease; }
        .pad.selected { border-color: #00d4ff !important; box-shadow: 0 0 20px rgba(0, 212, 255, 0.5); }
        .pad.scene { border-radius: 4px; width: 45px; }
        .pad.control { border-radius: 4px; height: 30px; }
        .pad.spacer { visibility: hidden; }
        .pad .repeat-indicator {
            position: absolute;
            bottom: 2px;
            right: 2px;
            font-size: 8px;
            opacity: 0.7;
        }
        @keyframes padPress { 0% { transform: scale(1); } 50% { transform: scale(0.92); } 100% { transform: scale(1); } }
        
        /* Color picker section */
        .color-section { margin-bottom: 15px; }
        .color-section-title { font-size: 12px; color: #888; margin-bottom: 8px; }
        .color-picker-row { display: flex; align-items: center; gap: 15px; margin-bottom: 10px; }
        .hex-input-group { display: flex; align-items: center; gap: 8px; }
        .hex-input-group input[type="text"] { width: 90px; font-family: monospace; }
        .color-preview {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            border: 2px solid rgba(255,255,255,0.2);
            box-shadow: 0 0 10px currentColor;
        }
        .color-palette { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
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
            top: 0; left: 0; right: 0;
            height: 50%;
            background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%);
            border-radius: 4px 4px 0 0;
            pointer-events: none;
        }
        .color-option:hover { transform: scale(1.15); z-index: 1; }
        .color-option.selected { border-color: #fff; box-shadow: 0 0 15px currentColor; }
        
        /* Repeat settings */
        .repeat-settings {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 12px;
            margin-top: 10px;
        }
        .repeat-settings.disabled { opacity: 0.5; pointer-events: none; }
        .repeat-row { display: flex; gap: 15px; align-items: center; }
        .repeat-row .form-group { margin-bottom: 0; flex: 1; }
        .repeat-row label { font-size: 11px; }
        .repeat-row input { padding: 8px; font-size: 13px; }
        
        .editor-panel { position: sticky; top: 20px; }
        .editor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .pad-note { background: rgba(0, 212, 255, 0.2); color: #00d4ff; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; }
        .checkbox-group { display: flex; align-items: center; gap: 10px; padding: 12px; background: rgba(0, 0, 0, 0.2); border-radius: 8px; cursor: pointer; }
        .checkbox-group input[type="checkbox"] { width: 20px; height: 20px; cursor: pointer; }
        .editor-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; }
        .log {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            padding: 15px;
            height: 150px;
            overflow-y: auto;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
        }
        .log-entry { padding: 4px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); display: flex; gap: 10px; }
        .log-time { color: #666; }
        .log-message { color: #aaa; }
        .log-entry.press .log-message { color: #00ff88; }
        .log-entry.repeat .log-message { color: #ffaa00; }
        .log-entry.error .log-message { color: #ff4444; }
        .key-hints { margin-top: 20px; }
        .key-hints h3 { font-size: 14px; color: #888; margin-bottom: 10px; }
        .hints-grid { display: grid; gap: 8px; font-size: 12px; }
        .hint-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .hint-label { color: #666; min-width: 80px; }
        code { background: rgba(0, 0, 0, 0.3); padding: 2px 8px; border-radius: 4px; font-family: 'Monaco', 'Menlo', monospace; color: #00d4ff; }
        input[type="file"] { display: none; }
        .divider { height: 1px; background: rgba(255, 255, 255, 0.1); margin: 20px 0; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.2); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎹 Launchpad Mapper</h1>
            <p class="subtitle">Map your Launchpad Mini to keyboard shortcuts</p>
        </header>
        
        <div class="status-bar">
            <div class="status-item"><div class="status-dot" id="connectionDot"></div><span id="connectionStatus">Disconnected</span></div>
            <div class="status-item"><div class="status-dot" id="runningDot"></div><span id="runningStatus">Stopped</span></div>
            <div class="status-item"><span>Profile: <strong id="currentProfile">Default</strong></span></div>
            <div class="status-item"><span>Mappings: <strong id="mappingCount">0</strong></span></div>
        </div>
        
        <div class="card" style="margin-bottom: 20px;">
            <div class="port-select">
                <div class="form-group">
                    <label>MIDI Input Port</label>
                    <select id="inputPort"><option value="">Select input port...</option></select>
                </div>
                <div class="form-group">
                    <label>MIDI Output Port</label>
                    <select id="outputPort"><option value="">Select output port...</option></select>
                </div>
            </div>
            <div class="controls">
                <button class="btn-primary" onclick="connect()" id="connectBtn"><span>⚡</span> Connect</button>
                <button class="btn-secondary" onclick="disconnect()" id="disconnectBtn"><span>✕</span> Disconnect</button>
                <button class="btn-success" onclick="startMapper()" id="startBtn"><span>▶</span> Start</button>
                <button class="btn-warning" onclick="stopMapper()" id="stopBtn"><span>⏹</span> Stop</button>
                <button class="btn-secondary" onclick="refreshPorts()"><span>↻</span> Refresh Ports</button>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="left-panel">
                <div class="card">
                    <h2>🎮 Launchpad Grid</h2>
                    <p style="color: #666; margin-bottom: 15px; font-size: 13px;">Click a pad to configure. 🔄 = repeat enabled</p>
                    <div class="launchpad-container">
                        <div class="launchpad-grid" id="launchpadGrid"></div>
                    </div>
                </div>
                <div class="card" style="margin-top: 20px;">
                    <h2>📋 Event Log</h2>
                    <div class="log" id="eventLog"></div>
                </div>
                <div class="card" style="margin-top: 20px;">
                    <h2>💾 Profile Management</h2>
                    <div class="port-select">
                        <div class="form-group"><label>Profile Name</label><input type="text" id="profileName" value="Default"></div>
                        <div class="form-group"><label>Description</label><input type="text" id="profileDescription" placeholder="Optional"></div>
                    </div>
                    <div class="controls">
                        <button class="btn-primary" onclick="exportProfile()"><span>📤</span> Export</button>
                        <button class="btn-secondary" onclick="document.getElementById('importFile').click()"><span>📥</span> Import</button>
                        <button class="btn-danger" onclick="clearAllMappings()"><span>🗑</span> Clear All</button>
                        <input type="file" id="importFile" accept=".json" onchange="importProfile(event)">
                    </div>
                </div>
            </div>
            <div class="right-panel">
                <div class="card editor-panel">
                    <div class="editor-header">
                        <h2>⚙️ Pad Configuration</h2>
                        <span class="pad-note" id="selectedPadNote">Select a pad</span>
                    </div>
                    <div class="form-group"><label>Label</label><input type="text" id="padLabel" placeholder="e.g., Copy, Play" maxlength="10"></div>
                    <div class="form-group"><label>Key Combination</label><input type="text" id="keyCombo" placeholder="e.g., ctrl+c, space"></div>
                    
                    <!-- Color Section -->
                    <div class="color-section">
                        <label class="form-group label">Pad Color</label>
                        <div class="color-picker-row">
                            <div class="hex-input-group">
                                <input type="color" id="hexColorPicker" value="#00FF00">
                                <input type="text" id="hexColorText" placeholder="#00FF00" maxlength="7">
                            </div>
                            <div class="color-preview" id="colorPreview" style="background-color: #00FF00;"></div>
                        </div>
                        <div class="color-section-title">Or choose from palette:</div>
                        <div class="color-palette" id="colorPalette"></div>
                    </div>
                    
                    <div class="form-group">
                        <label class="checkbox-group"><input type="checkbox" id="padEnabled" checked><span>Enabled</span></label>
                    </div>
                    
                    <!-- Key Repeat Section -->
                    <div class="form-group">
                        <label class="checkbox-group">
                            <input type="checkbox" id="repeatEnabled">
                            <span>Enable Key Repeat (hold to repeat)</span>
                        </label>
                    </div>
                    <div class="repeat-settings disabled" id="repeatSettings">
                        <div class="repeat-row">
                            <div class="form-group">
                                <label>Initial Delay (sec)</label>
                                <input type="number" id="repeatDelay" value="0.5" min="0.1" max="2" step="0.1">
                            </div>
                            <div class="form-group">
                                <label>Repeat Interval (sec)</label>
                                <input type="number" id="repeatInterval" value="0.05" min="0.01" max="1" step="0.01">
                            </div>
                        </div>
                    </div>
                    
                    <div class="editor-actions">
                        <button class="btn-primary" onclick="saveMapping()"><span>💾</span> Save</button>
                        <button class="btn-danger" onclick="deleteMapping()"><span>🗑</span> Delete</button>
                    </div>
                    <div class="divider"></div>
                    <button class="btn-secondary" onclick="testKeyCombo()" style="width: 100%;"><span>🧪</span> Test Key Combination</button>
                    <div class="key-hints">
                        <h3>Key Examples (keyboard library syntax)</h3>
                        <div class="hints-grid">
                            <div class="hint-row"><span class="hint-label">Single:</span><code>a</code> <code>space</code> <code>enter</code> <code>f1</code></div>
                            <div class="hint-row"><span class="hint-label">Modifier:</span><code>ctrl+c</code> <code>shift+a</code> <code>alt+tab</code></div>
                            <div class="hint-row"><span class="hint-label">Multi:</span><code>ctrl+shift+s</code> <code>ctrl+alt+delete</code></div>
                            <div class="hint-row"><span class="hint-label">Arrows:</span><code>up</code> <code>down</code> <code>left</code> <code>right</code></div>
                            <div class="hint-row"><span class="hint-label">Media:</span><code>play/pause media</code> <code>volume up</code> <code>volume down</code></div>
                            <div class="hint-row"><span class="hint-label">Special:</span><code>windows</code> <code>backspace</code> <code>delete</code> <code>home</code> <code>end</code></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        const GRID_NOTES = [
            [91, 92, 93, 94, 95, 96, 97, 98, null],
            [81, 82, 83, 84, 85, 86, 87, 88, 89],
            [71, 72, 73, 74, 75, 76, 77, 78, 79],
            [61, 62, 63, 64, 65, 66, 67, 68, 69],
            [51, 52, 53, 54, 55, 56, 57, 58, 59],
            [41, 42, 43, 44, 45, 46, 47, 48, 49],
            [31, 32, 33, 34, 35, 36, 37, 38, 39],
            [21, 22, 23, 24, 25, 26, 27, 28, 29],
            [11, 12, 13, 14, 15, 16, 17, 18, 19],
        ];
        const COLOR_HEX = ''' + json.dumps(COLOR_HEX) + ''';
        let selectedPad = null, mappings = {}, selectedColor = '#00FF00', eventSource = null, isConnected = false, isRunning = false;
        
        function initGrid() {
            const grid = document.getElementById('launchpadGrid');
            grid.innerHTML = '';
            GRID_NOTES.forEach((row, ri) => {
                row.forEach((note, ci) => {
                    const pad = document.createElement('div');
                    if (note === null) { pad.className = 'pad spacer'; }
                    else {
                        pad.className = 'pad';
                        if (ri === 0) pad.classList.add('control');
                        if (ci === 8) pad.classList.add('scene');
                        pad.dataset.note = note;
                        pad.onclick = () => selectPad(note);
                    }
                    grid.appendChild(pad);
                });
            });
        }
        
        function initColorPalette() {
            const palette = document.getElementById('colorPalette');
            palette.innerHTML = '';
            Object.entries(COLOR_HEX).filter(([name]) => !name.includes('dim') && name !== 'off').forEach(([name, hex]) => {
                const opt = document.createElement('div');
                opt.className = 'color-option';
                opt.style.backgroundColor = hex;
                opt.dataset.color = name;
                opt.dataset.hex = hex;
                opt.title = name;
                opt.onclick = () => selectColorFromPalette(name, hex);
                palette.appendChild(opt);
            });
        }
        
        function selectColorFromPalette(name, hex) {
            selectedColor = hex;
            updateColorDisplay(hex);
            document.querySelectorAll('.color-option').forEach(el => el.classList.toggle('selected', el.dataset.hex === hex));
        }
        
        function updateColorDisplay(hex) {
            document.getElementById('hexColorPicker').value = hex;
            document.getElementById('hexColorText').value = hex;
            document.getElementById('colorPreview').style.backgroundColor = hex;
            document.getElementById('colorPreview').style.boxShadow = '0 0 15px ' + hex;
            // Update palette selection
            document.querySelectorAll('.color-option').forEach(el => el.classList.toggle('selected', el.dataset.hex.toUpperCase() === hex.toUpperCase()));
        }
        
        // Color picker events
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('hexColorPicker').addEventListener('input', (e) => {
                selectedColor = e.target.value;
                updateColorDisplay(e.target.value);
            });
            document.getElementById('hexColorText').addEventListener('input', (e) => {
                let val = e.target.value;
                if (val.match(/^#[0-9A-Fa-f]{6}$/)) {
                    selectedColor = val;
                    updateColorDisplay(val);
                }
            });
            document.getElementById('repeatEnabled').addEventListener('change', (e) => {
                document.getElementById('repeatSettings').classList.toggle('disabled', !e.target.checked);
            });
        });
        
        function selectPad(note) {
            selectedPad = note;
            document.querySelectorAll('.pad').forEach(el => el.classList.toggle('selected', el.dataset.note == note));
            document.getElementById('selectedPadNote').textContent = 'Note: ' + note;
            const m = mappings[note];
            if (m) {
                document.getElementById('padLabel').value = m.label || '';
                document.getElementById('keyCombo').value = m.key_combo || '';
                document.getElementById('padEnabled').checked = m.enabled !== false;
                document.getElementById('repeatEnabled').checked = m.repeat_enabled || false;
                document.getElementById('repeatDelay').value = m.repeat_delay || 0.5;
                document.getElementById('repeatInterval').value = m.repeat_interval || 0.05;
                document.getElementById('repeatSettings').classList.toggle('disabled', !m.repeat_enabled);
                // Handle color (could be hex or palette name)
                let hex = m.color;
                if (!hex.startsWith('#')) {
                    hex = COLOR_HEX[m.color] || '#00FF00';
                }
                selectedColor = hex;
                updateColorDisplay(hex);
            } else {
                document.getElementById('padLabel').value = '';
                document.getElementById('keyCombo').value = '';
                document.getElementById('padEnabled').checked = true;
                document.getElementById('repeatEnabled').checked = false;
                document.getElementById('repeatDelay').value = 0.5;
                document.getElementById('repeatInterval').value = 0.05;
                document.getElementById('repeatSettings').classList.add('disabled');
                selectedColor = '#00FF00';
                updateColorDisplay('#00FF00');
            }
        }
        
        function updatePadDisplay() {
            document.querySelectorAll('.pad').forEach(el => {
                const note = parseInt(el.dataset.note);
                if (!isNaN(note) && mappings[note]) {
                    const m = mappings[note];
                    let hex = m.color;
                    if (!hex.startsWith('#')) {
                        hex = COLOR_HEX[m.color] || '#333';
                    }
                    el.style.backgroundColor = hex;
                    el.innerHTML = (m.label || '') + (m.repeat_enabled ? '<span class="repeat-indicator">🔄</span>' : '');
                    el.style.color = isLight(hex) ? '#000' : '#fff';
                } else if (!isNaN(note)) {
                    el.style.backgroundColor = '#333';
                    el.innerHTML = '';
                }
            });
            document.getElementById('mappingCount').textContent = Object.keys(mappings).length;
        }
        
        function isLight(hex) {
            if (!hex) return false;
            const c = hex.replace('#', '');
            const rgb = parseInt(c, 16);
            const luma = 0.2126 * ((rgb >> 16) & 0xff) + 0.7152 * ((rgb >> 8) & 0xff) + 0.0722 * (rgb & 0xff);
            return luma > 128;
        }
        
        async function saveMapping() {
            if (selectedPad === null) { log('Select a pad first', 'error'); return; }
            const kc = document.getElementById('keyCombo').value.trim();
            if (!kc) { log('Enter a key combination', 'error'); return; }
            const m = {
                note: selectedPad,
                label: document.getElementById('padLabel').value,
                key_combo: kc,
                color: selectedColor,
                enabled: document.getElementById('padEnabled').checked,
                repeat_enabled: document.getElementById('repeatEnabled').checked,
                repeat_delay: parseFloat(document.getElementById('repeatDelay').value) || 0.5,
                repeat_interval: parseFloat(document.getElementById('repeatInterval').value) || 0.05
            };
            const r = await fetch('/api/mapping', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(m) });
            if (r.ok) { mappings[selectedPad] = m; updatePadDisplay(); log('Saved: Pad ' + selectedPad + ' → ' + kc + (m.repeat_enabled ? ' (repeat)' : ''), 'press'); }
        }
        
        async function deleteMapping() {
            if (selectedPad === null) return;
            const r = await fetch('/api/mapping/' + selectedPad, { method: 'DELETE' });
            if (r.ok) { delete mappings[selectedPad]; updatePadDisplay(); log('Deleted pad ' + selectedPad); }
        }
        
        async function testKeyCombo() {
            const c = document.getElementById('keyCombo').value.trim();
            if (!c) { log('Enter a key combination', 'error'); return; }
            await fetch('/api/test-key', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({combo: c}) });
            log('Tested: ' + c);
        }
        
        async function connect() {
            const r = await fetch('/api/connect', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({input_port: document.getElementById('inputPort').value, output_port: document.getElementById('outputPort').value}) });
            const d = await r.json();
            isConnected = d.connected;
            updateStatus();
            log(d.message, d.connected ? 'press' : 'error');
        }
        
        async function disconnect() {
            await fetch('/api/disconnect', { method: 'POST' });
            isConnected = false; isRunning = false;
            updateStatus();
            log('Disconnected');
        }
        
        async function startMapper() {
            const r = await fetch('/api/start', { method: 'POST' });
            const d = await r.json();
            isRunning = d.started;
            updateStatus();
            log(d.message, d.started ? 'press' : 'error');
            if (d.started) startEventStream();
        }
        
        async function stopMapper() {
            await fetch('/api/stop', { method: 'POST' });
            isRunning = false;
            updateStatus();
            log('Stopped');
            stopEventStream();
        }
        
        async function refreshPorts() {
            const r = await fetch('/api/ports');
            const d = await r.json();
            const iS = document.getElementById('inputPort'), oS = document.getElementById('outputPort');
            iS.innerHTML = '<option value="">Select input...</option>';
            oS.innerHTML = '<option value="">Select output...</option>';
            d.inputs.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; if (p.toLowerCase().includes('launchpad')) o.selected = true; iS.appendChild(o); });
            d.outputs.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; if (p.toLowerCase().includes('launchpad')) o.selected = true; oS.appendChild(o); });
            log('Found ' + d.inputs.length + ' inputs, ' + d.outputs.length + ' outputs');
        }
        
        async function loadMappings() {
            const r = await fetch('/api/profile');
            const d = await r.json();
            mappings = {};
            Object.values(d.mappings || {}).forEach(m => mappings[m.note] = m);
            document.getElementById('profileName').value = d.name || 'Default';
            document.getElementById('currentProfile').textContent = d.name || 'Default';
            updatePadDisplay();
        }
        
        async function exportProfile() {
            const n = document.getElementById('profileName').value || 'Default';
            const r = await fetch('/api/profile/export?name=' + encodeURIComponent(n));
            const d = await r.json();
            const b = new Blob([JSON.stringify(d, null, 2)], {type: 'application/json'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(b);
            a.download = 'launchpad-' + n.replace(/[^a-z0-9]/gi, '_') + '.json';
            a.click();
            log('Exported: ' + n, 'press');
        }
        
        async function importProfile(e) {
            const f = e.target.files[0];
            if (!f) return;
            const t = await f.text();
            await fetch('/api/profile/import', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: t });
            await loadMappings();
            log('Imported profile', 'press');
            e.target.value = '';
        }
        
        async function clearAllMappings() {
            if (!confirm('Clear all mappings?')) return;
            await fetch('/api/clear', { method: 'POST' });
            mappings = {};
            updatePadDisplay();
            log('Cleared all');
        }
        
        function updateStatus() {
            document.getElementById('connectionDot').classList.toggle('connected', isConnected);
            document.getElementById('connectionStatus').textContent = isConnected ? 'Connected' : 'Disconnected';
            document.getElementById('runningDot').classList.toggle('running', isRunning);
            document.getElementById('runningStatus').textContent = isRunning ? 'Running' : 'Stopped';
            document.getElementById('startBtn').disabled = !isConnected || isRunning;
            document.getElementById('stopBtn').disabled = !isRunning;
        }
        
        function log(msg, type = '') {
            const l = document.getElementById('eventLog');
            const e = document.createElement('div');
            e.className = 'log-entry ' + type;
            e.innerHTML = '<span class="log-time">' + new Date().toLocaleTimeString() + '</span><span class="log-message">' + msg + '</span>';
            l.insertBefore(e, l.firstChild);
            while (l.children.length > 100) l.removeChild(l.lastChild);
        }
        
        function startEventStream() {
            if (eventSource) eventSource.close();
            eventSource = new EventSource('/api/events');
            eventSource.onmessage = (e) => {
                const d = JSON.parse(e.data);
                if (d.type === 'pad_press') {
                    const p = document.querySelector('.pad[data-note="' + d.note + '"]');
                    if (p) { p.classList.add('active'); setTimeout(() => p.classList.remove('active'), 150); }
                    const m = mappings[d.note];
                    log('Pad ' + d.note + (m ? ' → ' + m.key_combo : ' (no mapping)'), 'press');
                } else if (d.type === 'key_repeat') {
                    log('Repeat: ' + d.combo, 'repeat');
                }
            };
        }
        
        function stopEventStream() { if (eventSource) { eventSource.close(); eventSource = null; } }
        
        document.addEventListener('keydown', (e) => { if (e.ctrlKey && e.key === 's') { e.preventDefault(); if (selectedPad !== null) saveMapping(); } });
        document.addEventListener('DOMContentLoaded', () => { initGrid(); initColorPalette(); refreshPorts(); loadMappings(); updateStatus(); log('Launchpad Mapper ready'); });
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
    return jsonify(mapper.get_available_ports())


@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json or {}
    success = mapper.connect(data.get('input_port'), data.get('output_port'))
    return jsonify({"connected": success, "message": "Connected successfully" if success else "Failed to connect"})


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
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile/export')
def export_profile():
    name = request.args.get('name')
    if name:
        mapper.profile.name = name
    return jsonify(mapper.profile.to_dict())


@app.route('/api/profile/import', methods=['POST'])
def import_profile():
    data = request.json
    mapper.profile = Profile.from_dict(data)
    if mapper.running:
        mapper.update_pad_colors()
    return jsonify({"success": True})


@app.route('/api/clear', methods=['POST'])
def clear_mappings():
    mapper.profile = Profile(mapper.profile.name)
    if mapper.running:
        mapper.clear_all_pads()
    return jsonify({"success": True})


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
