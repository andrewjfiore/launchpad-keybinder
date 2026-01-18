# New Features - Launchpad Mapper v2.1

This document describes the new features added to Launchpad Mapper in version 2.1.

## Overview

Version 2.1 introduces five major feature enhancements:

1. **Macro Sequences** - Execute multiple keystrokes in sequence with configurable delays
2. **MIDI Velocity Sensitivity** - Different actions based on how hard you press a pad
3. **Long Press Actions** - Tap vs hold for different behaviors
4. **Application Preset Profiles** - Pre-configured profiles for popular applications
5. **Visual LED Animations** - Pulse, progress bars, and rainbow effects

---

## 1. Macro Sequences

### Description
Execute a sequence of multiple keyboard shortcuts with configurable delays between each step. Perfect for automating complex workflows.

### Use Cases
- Video editing: Select clip → Copy → Paste → Adjust position
- Photo editing: Apply preset → Adjust exposure → Export
- Gaming: Execute build orders or ability rotations
- Productivity: Multi-step automation tasks

### Configuration

Macro sequences are defined in the `macro_steps` field of a pad mapping:

```json
{
  "note": 81,
  "label": "Macro",
  "color": "purple",
  "macro_steps": [
    {"key_combo": "ctrl+c", "delay_after": 0.1},
    {"key_combo": "ctrl+v", "delay_after": 0.2},
    {"key_combo": "enter", "delay_after": 0.0}
  ]
}
```

Each step contains:
- `key_combo`: The keyboard shortcut to execute
- `delay_after`: Delay in seconds before the next step (0 for no delay)

### How It Works
1. Press the pad once
2. Each step executes in sequence
3. Delays occur between steps as configured
4. Runs in a background thread (non-blocking)

---

## 2. MIDI Velocity Sensitivity

### Description
Map different actions to different velocity ranges (how hard the pad is pressed). The Launchpad Mini supports velocity values from 0-127.

### Use Cases
- Soft press = preview, hard press = execute
- Graduated volume/opacity control
- Different shortcuts at different pressures
- Fine vs coarse adjustments

### Configuration

Velocity mappings are defined in the `velocity_mappings` field:

```json
{
  "note": 82,
  "label": "Vol Ctrl",
  "color": "green",
  "velocity_mappings": {
    "0-42": "ctrl+down",
    "43-84": "down",
    "85-127": "shift+down"
  }
}
```

Each range is defined as `"low-high": "key_combo"`:
- **0-42**: Soft press - Execute `ctrl+down`
- **43-84**: Medium press - Execute `down`
- **85-127**: Hard press - Execute `shift+down`

### How It Works
1. Press pad with varying pressure
2. MIDI velocity is measured (0-127)
3. Mapper finds matching range
4. Corresponding action executes
5. Falls back to default `key_combo` if no range matches

---

## 3. Long Press Actions

### Description
Execute different actions for tap (short press) vs hold (long press). Adds a whole new dimension to each pad.

### Use Cases
- Tap = single action, hold = different action
- Long press to enter configuration mode
- Hold for menu, tap for immediate action
- Context-sensitive controls

### Configuration

Long press is configured with three fields:

```json
{
  "note": 83,
  "key_combo": "ctrl+c",
  "label": "Copy/Cut",
  "color": "purple",
  "long_press_enabled": true,
  "long_press_action": "ctrl+x",
  "long_press_threshold": 0.5
}
```

Fields:
- `long_press_enabled`: Enable/disable long press detection
- `long_press_action`: Action to execute on long press
- `long_press_threshold`: Duration in seconds to trigger long press (default: 0.5)

### How It Works
1. Press and hold the pad
2. Timer starts tracking press duration
3. If held beyond threshold: Execute `long_press_action`
4. If released before threshold: Execute `key_combo`
5. Only one action fires per press

**Example:**
- Tap (< 0.5s) = Copy (`ctrl+c`)
- Hold (≥ 0.5s) = Cut (`ctrl+x`)

---

## 4. Application Preset Profiles

### Description
Pre-configured profiles for popular applications. Load a preset and instantly have your Launchpad mapped for that workflow.

### Included Presets

#### Negative Lab Pro (`negative_lab_pro.json`)
- Film scanning and conversion workflow
- Exposure, contrast, temperature, tint controls
- Quick ratings and navigation
- **64 mappings** optimized for film photographers

#### Adobe Lightroom CC (`lightroom_cc.json`)
- Photo editing and organization
- Module switching, adjustments, ratings
- Crop, spot removal, brush tools
- **51 mappings** for complete photo workflow

#### CapCut Desktop (`capcut_desktop.json`)
- Video editing timeline controls
- Playback, navigation, speed controls
- Effects, transitions, text, stickers
- **44 mappings** for video content creation

#### OBS Studio (`obs_studio.json`)
- Streaming and recording controls
- Scene switching (8 scenes)
- Source visibility, audio controls
- **47 mappings** for broadcast workflows

### How to Use Presets

**Via Web Interface:**
1. Open Launchpad Mapper (http://localhost:5000)
2. Navigate to **"Preset Profiles"** section
3. Select a preset from the dropdown
4. Click **"Load Preset"**
5. All mappings instantly configure your Launchpad!

**Via API:**
```javascript
// List presets
GET /api/presets

// Load specific preset
GET /api/presets/lightroom_cc.json

// Import as current profile
POST /api/profile/import
```

### Creating Custom Presets

1. Configure your Launchpad for your workflow
2. Export the profile (Export Profile button)
3. Save the JSON file in `presets/` directory
4. Add documentation to `presets/README.md`
5. Share with the community!

---

## 5. Visual LED Animations

### Description
Animated LED feedback effects on your Launchpad. Provides visual confirmation, progress indication, and aesthetic flair.

### Available Animations

#### Pulse Animation
Pulsate a pad with its color (bright → dim → repeat).

**Use Cases:**
- Visual confirmation of action
- Drawing attention to specific pad
- Layer change feedback (built-in)

**Trigger:**
```javascript
POST /api/animation/pulse
{
  "note": 81,
  "color": "green",
  "duration": 0.5
}
```

**Built-in Integration:**
- Automatically pulses when changing layers
- Can be triggered via API for custom effects

---

#### Progress Bar Animation
Display progress across a row of pads.

**Use Cases:**
- Render progress
- Upload/download status
- Timer countdown
- Battery level

**Trigger:**
```javascript
POST /api/animation/progress
{
  "row": 0,          // Row index (0-7)
  "percentage": 75,  // 0-100
  "color": "green"
}
```

**Example:**
Row 0 with 75% = First 6 pads lit (out of 8)

---

#### Rainbow Cycle Animation
Continuous rainbow pattern across all pads.

**Use Cases:**
- Idle/standby mode
- Demo/presentation mode
- Visual spectacle
- Attract mode

**Trigger:**
```javascript
POST /api/animation/rainbow
{
  "speed": 0.5  // Seconds per cycle
}
```

**Control:**
```javascript
// Stop all animations
POST /api/animation/stop
```

### Animation Engine

Animations run in background threads and can be:
- Started individually or in combination
- Stopped all at once
- Managed automatically (stop on mapper stop)

**Python API:**
```python
# Pulse a pad
mapper.pulse(note=81, color="green", duration=0.5)

# Progress bar
anim = ProgressBarAnimation(mapper, row_notes, percentage=75, color="green")
mapper.start_animation(anim)

# Rainbow cycle
anim = RainbowCycleAnimation(mapper, speed=0.5)
mapper.start_animation(anim)

# Stop all
mapper.stop_all_animations()
```

---

## API Reference

### New Endpoints

#### Animations
- `POST /api/animation/pulse` - Trigger pulse effect
- `POST /api/animation/progress` - Show progress bar
- `POST /api/animation/rainbow` - Start rainbow cycle
- `POST /api/animation/stop` - Stop all animations

#### Presets
- `GET /api/presets` - List available presets
- `GET /api/presets/<filename>` - Load specific preset

#### Mapping (Enhanced)
- `POST /api/mapping` - Now supports:
  - `macro_steps` (list)
  - `velocity_mappings` (dict)
  - `long_press_enabled` (bool)
  - `long_press_action` (string)
  - `long_press_threshold` (float)

---

## Configuration Examples

### Complete Pad Mapping with All Features

```json
{
  "note": 81,
  "key_combo": "ctrl+c",
  "color": "#00FF00",
  "label": "Advanced",
  "enabled": true,
  "action": "key",

  "repeat_enabled": true,
  "repeat_delay": 0.5,
  "repeat_interval": 0.05,

  "macro_steps": [
    {"key_combo": "ctrl+c", "delay_after": 0.1},
    {"key_combo": "ctrl+v", "delay_after": 0.0}
  ],

  "velocity_mappings": {
    "0-42": "ctrl+c",
    "43-127": "ctrl+x"
  },

  "long_press_enabled": true,
  "long_press_action": "ctrl+shift+c",
  "long_press_threshold": 0.5
}
```

**Behavior:**
- **Soft tap**: Copy (`ctrl+c`)
- **Hard tap**: Cut (`ctrl+x`)
- **Long press**: Special copy (`ctrl+shift+c`)
- **Has repeat**: Enabled with delays
- **Has macro**: Copy then paste sequence

---

## Upgrade Guide

### From v2.0 to v2.1

All existing profiles remain **100% compatible**. New fields are optional:

1. Existing mappings continue to work
2. New features disabled by default
3. Export/import preserves all data
4. Presets can be loaded anytime

### Profile Migration

Old profiles automatically upgrade:
- Missing fields use safe defaults
- No manual conversion needed
- Export preserves new features

---

## Performance Notes

- **Macro sequences**: Run in background threads (non-blocking)
- **Long press detection**: Minimal overhead (~1 timer per active press)
- **Velocity sensitivity**: Zero overhead (simple range check)
- **Animations**: Separate threads, stop on mapper stop
- **Presets**: Standard profile loading (instant)

---

## Tips and Best Practices

### Combining Features

**Macro + Velocity:**
```json
{
  "note": 81,
  "macro_steps": [...],
  "velocity_mappings": {
    "0-63": "single_step",
    "64-127": "use_macro"
  }
}
```
- Soft press: Single action
- Hard press: Full macro sequence

**Long Press + Repeat:**
Not recommended - conflicts in behavior. Use one or the other.

### Color Coding

Suggested color scheme for features:
- **Purple**: Macros (multi-step)
- **Magenta**: Velocity-sensitive
- **Amber**: Long press enabled
- **Green**: Standard actions

### Performance

- Limit simultaneous animations to 3-4
- Keep macro delays reasonable (>0.01s)
- Use velocity sensitivity sparingly (complex logic)

---

## Troubleshooting

### Macros Not Firing
- Check `macro_steps` array syntax
- Verify delays are reasonable
- Test individual key combos first

### Velocity Not Working
- Verify range format: `"0-42"` (string with dash)
- Check ranges don't overlap
- Test with varying pressure

### Long Press Issues
- Adjust `long_press_threshold` (try 0.3-1.0)
- Ensure `long_press_enabled` is `true`
- Check that both actions are valid

### Animations Stuck
- Call `POST /api/animation/stop`
- Restart mapper
- Check for error messages

---

## Future Enhancements

Planned for future releases:
- UI controls for macro editing
- Visual velocity range configuration
- More animation types (wave, chase, strobe)
- Preset marketplace/sharing
- Macro recording mode

---

**Version:** 2.1.0
**Release Date:** 2026-01-18
**Compatibility:** Python 3.7+, All platforms (Windows, macOS, Linux)
