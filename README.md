# 🎹 Launchpad Mapper

Map MIDI controller inputs (Launchpad and other devices) to keyboard shortcuts with configurable LED feedback and profiles.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **MIDI to Keyboard Mapping**: Map MIDI notes to keyboard shortcuts
- **Full Key Support**: Single keys, modifiers (Ctrl, Shift, Alt, Cmd), function keys, media keys
- **LED Color Control**: Set pad colors from 28 available colors (Launchpad) or simple on/off for generic devices
- **Profile System**: Import/export JSON profiles for different use cases
- **Real-time Feedback**: See pad presses in the web UI with live event logging
- **Auto-detection**: Automatically finds connected MIDI devices
- **MIDI Backend Selection**: Switch and refresh the active `mido` backend from the UI
- **Emulation Mode**: Click pads in the web UI to trigger mapped actions without hardware
- **Log Export**: Download a runtime log for debugging

## Project Problems and Goals

This project explicitly targets these problems and design constraints. See `.cursor/rules/project-problems-goals.mdc` for full detail (Cursor context).

| Area | Goal | Current approach |
|------|------|------------------|
| **Windows keystrokes** | Reliably send shortcuts to the active window | `keyboard` library; warn if admin needed |
| **MIDI detection** | Auto-detect Launchpad, avoid "won't connect" | Heuristics, retries, clear errors, exclusivity handling |
| **Port opens** | No UI freezes when opening MIDI ports | Worker thread + hard timeout (`_open_with_timeout`) |
| **Cross-model Launchpad** | Consistent grid/top-row/scene across MK2, MK3/X/Pro | Device detection, normalize CCs to 91–98, device-specific LED output |
| **Mapping features** | Layers, macros, long-press, velocity, repeats | Layers + LED updates; macro steps; long-press; repeat tuning |
| **UI/UX** | Fast, low-friction mapping | One-page UI, click-to-edit, drag-drop, duplicate, event log |
| **Lightroom** | Optional TCP control without spam/blocking | Background sender, queue, throttled logs, rate-limited sliders |
| **Thread safety** | No races (MIDI vs UI vs profile/layers) | `connection_lock`, `profile_lock`, `self.running` gating |
| **Persistence** | Predictable paths, import/export | `~/.launchpad_mapper/profiles`, env presets, JSON |
| **Auto-switch** | Profile by active window | UI + persistence exist; **window monitoring not yet implemented** |

## Installation

### Prerequisites

- Python 3.8 or higher
- A MIDI device (Launchpad models work best for LED feedback, but other devices are supported)

## Packaging (Windows EXE with PyInstaller)

If you want a double-clickable Windows EXE, you can build one with PyInstaller:

```bash
pip install pyinstaller
pyinstaller pyinstaller.spec
```

The EXE will be available under `dist/launchpad-mapper/launchpad-mapper.exe`.

You can also run `build_exe.bat` on Windows to perform the same steps automatically.

### macOS

```bash
# Install dependencies
pip install -r requirements.txt

# Run the mapper
python server.py
```

### Windows

```bash
# Install dependencies
pip install -r requirements.txt

# Run the mapper
python server.py
```

### Linux

```bash
# You may need to add yourself to the audio group for MIDI access
sudo usermod -a -G audio $USER

# Install dependencies
pip install -r requirements.txt

# Run the mapper
python server.py
```

## Usage

1. **Start the application**:
   ```bash
   python server.py
   ```

2. **Open the web interface**: Navigate to `http://localhost:5000` in your browser

3. **Connect your MIDI device**:
   - Select your MIDI Input/Output ports from the dropdowns
   - Click "Connect"

4. **Configure pad mappings**:
   - Click on any pad in the grid
   - Enter a label (optional, shown on the pad)
   - Enter a key combination (e.g., `ctrl+c`, `space`, `shift+alt+f1`)
   - Select a color
   - Click "Save Mapping"

5. **Start the mapper**: Click "Start" to begin sending keystrokes
6. **Emulation (optional)**: Toggle "Emulation" to trigger actions by clicking pads

## Key Combination Syntax

| Type | Examples |
|------|----------|
| Single key | `a`, `b`, `1`, `space`, `enter`, `f1` |
| With modifier | `ctrl+c`, `shift+a`, `alt+tab`, `cmd+s` |
| Multiple modifiers | `ctrl+shift+s`, `ctrl+alt+delete` |
| Arrow keys | `up`, `down`, `left`, `right` |
| Navigation | `home`, `end`, `pageup`, `pagedown` |
| Media keys | `playpause`, `next`, `previous`, `mute`, `volumeup`, `volumedown` |

## Profile Management

### Export a Profile

1. Enter a profile name
2. Click "Export Profile"
3. Save the JSON file

### Import a Profile

1. Click "Import Profile"
2. Select a JSON file
3. Mappings will be loaded immediately

### Profile JSON Format

```json
{
  "name": "Video Editing",
  "description": "Shortcuts for DaVinci Resolve",
  "mappings": {
    "81": {
      "note": 81,
      "key_combo": "space",
      "color": "green",
      "label": "Play",
      "enabled": true
    },
    "82": {
      "note": 82,
      "key_combo": "j",
      "color": "blue",
      "label": "Rev",
      "enabled": true
    }
  }
}
```

## Available Colors

| Main Colors | Dim Variants |
|-------------|--------------|
| off | - |
| white | - |
| red | red_dim |
| orange | orange_dim |
| yellow | yellow_dim |
| lime | lime_dim |
| green | green_dim |
| spring | spring_dim |
| cyan | cyan_dim |
| sky | sky_dim |
| blue | blue_dim |
| purple | purple_dim |
| magenta | magenta_dim |
| pink | pink_dim |
| coral | coral_dim |
| amber | amber_dim |

## Launchpad Note Map (Programmer Mode)

```
[91] [92] [93] [94] [95] [96] [97] [98]  <- Control buttons
[81] [82] [83] [84] [85] [86] [87] [88] [89]
[71] [72] [73] [74] [75] [76] [77] [78] [79]
[61] [62] [63] [64] [65] [66] [67] [68] [69]
[51] [52] [53] [54] [55] [56] [57] [58] [59]  <- Scene buttons (right column)
[41] [42] [43] [44] [45] [46] [47] [48] [49]
[31] [32] [33] [34] [35] [36] [37] [38] [39]
[21] [22] [23] [24] [25] [26] [27] [28] [29]
[11] [12] [13] [14] [15] [16] [17] [18] [19]
```

## Troubleshooting

### No MIDI ports found

- Make sure your MIDI device is connected via USB
- On Linux, ensure you're in the `audio` group
- Try unplugging and reconnecting the device

### Keyboard shortcuts not working

- Make sure the mapper is in "Running" state
- On macOS, you may need to grant Accessibility permissions to your terminal/Python
- On Linux, you may need to run as root or configure uinput permissions

### Colors not showing on Launchpad

- Make sure you've connected the MIDI Output port
- Some Launchpad models may need to be in Programmer mode (consult your Launchpad manual)
- For non-Launchpad devices, LED feedback is limited to basic on/off

### Lightroom Classic sliders not responding

Slider commands (e.g. `lrslider:N` pads, or `set_exposure:0.5`) are sent over TCP to the **Lightroom Slider Control** plugin. If Lightroom does not respond:

1. **Install and enable the plugin**
   - Copy `Modules/LightroomSliderControl.lrplugin` into Lightroom’s plugin folder (e.g. `%APPDATA%\Adobe\Lightroom\Modules` on Windows), or add it via **File → Plugin Manager**.
   - Ensure the plugin is **enabled**. It loads `SocketServer.lua`, which listens on **port 55555**.

2. **Lightroom Classic must be running**
   - Start Lightroom Classic **before** (or while) using the mapper. The socket server runs only when the plugin is loaded.

3. **Check connection**
   - Open `http://localhost:5000`, then call `GET /api/lightroom/status` (or use a REST client) to see `connected: true/false` and any `last_error`.
   - Use `POST /api/lightroom/test` to force a connection attempt. If it fails, the plugin is not reachable (not running, wrong port, or firewall).

4. **Port and host**
   - Default is `127.0.0.1:55555`. Override with `LR_SOCKET_HOST` and `LR_SOCKET_PORT` if needed.

5. **Use a profile with slider mappings**
   - Ensure the active profile has pads mapped to `lrslider:N` (e.g. import **Lightroom Classic** preset) and the mapper is **Started**.

6. **Develop module**
   - The plugin runs commands in the **Develop** module. It will switch to Develop when you trigger a slider; have a **photo selected** so adjustments apply.

7. **Plugin logs**
   - Check `Documents\lrClassicLogs\SliderControlSocket.log` (or `~/Documents/lrClassicLogs/` on Mac) for "Listening on port 55555", "Client connected", and "Received command: '…'".

### Config / profiles permission errors

- Profiles and config are stored under `%APPDATA%\launchpad-mapper` (Windows) or `~/.config/launchpad-mapper` (Linux/macOS).
- Set `LAUNCHPAD_MAPPER_DATA_DIR` to a writable directory to override (e.g. a folder inside the project).

## Testing

```bash
pip install -r requirements.txt -r requirements-test.txt
pytest tests/ -v --tb=short
```

On Windows you can use `run_tests.bat`, which installs test deps and runs pytest. Tests use a temp directory for persistence (no writes to APPDATA).

## Example Profiles

### Streaming/OBS

- F13-F24 for scene switching
- Media keys for audio control
- Mute toggle

### Video Editing

- J/K/L for playback control
- I/O for in/out points
- Space for play/pause

### Gaming

- Number keys for abilities
- WASD alternatives
- Push-to-talk

## API Reference

The web interface communicates with the server via REST API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ports` | GET | List available MIDI ports |
| `/api/connect` | POST | Connect to MIDI ports |
| `/api/disconnect` | POST | Disconnect from MIDI |
| `/api/start` | POST | Start the mapper |
| `/api/stop` | POST | Stop the mapper |
| `/api/mapping` | POST | Save a pad mapping |
| `/api/mapping/<note>` | DELETE | Delete a mapping |
| `/api/profile` | GET | Get current profile |
| `/api/profile/export` | GET | Export profile as JSON |
| `/api/profile/import` | POST | Import a profile |
| `/api/events` | GET | SSE stream of MIDI events |
| `/api/midi-backend` | GET/POST | Get or set the active MIDI backend |
| `/api/midi-backend/refresh` | POST | Reinitialize the current backend and refresh ports |
| `/api/logs/download` | GET | Download the runtime log |
| `/api/emulate` | POST | Trigger a mapped pad action from the UI |
| `/api/lightroom/status` | GET | Lightroom socket connection status (for slider commands) |
| `/api/lightroom/test` | POST | Test connection to Lightroom plugin |

## License

MIT License - feel free to use and modify!

## Contributing

Pull requests welcome! Please ensure your code follows the existing style.
