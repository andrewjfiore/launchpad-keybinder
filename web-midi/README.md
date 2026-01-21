# Launchpad Mapper (Web MIDI)

This directory contains a JavaScript rewrite of the Launchpad Mapper using Node.js and the Web MIDI API. The MIDI
handling runs in the browser (Web MIDI), while the Node.js server provides static assets and profile persistence.

## Features

- Browser-based MIDI input/output using the Web MIDI API.
- Launchpad-style 8x8 pad grid with color feedback.
- Map MIDI notes to key combos that are dispatched inside the page.
- Import/export JSON profiles.

> **Note**: Web MIDI can only dispatch keyboard events within the browser tab. It cannot send OS-level keystrokes the
> way the Python version does.

## Getting Started

```bash
cd web-midi
npm install
npm start
```

Then open `http://localhost:5001` in a Web MIDI-enabled browser (Chrome/Edge).

## Profile Format

```json
{
  "name": "Default",
  "description": "Web MIDI profile",
  "mappings": {
    "81": {
      "note": 81,
      "label": "Play",
      "key_combo": "space",
      "color": "green",
      "enabled": true
    }
  }
}
```
