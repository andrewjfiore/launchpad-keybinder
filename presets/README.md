# Launchpad Mapper Presets

This directory contains pre-configured profiles for popular applications. Import these profiles to instantly set up your Launchpad for specific workflows.

## Available Presets

### 1. Negative Lab Pro (`negative_lab_pro.json`)
Optimized for Negative Lab Pro in Lightroom - film scanning and conversion workflow.

**Key Features:**
- Quick access to conversion controls (New Conversion, Batch Convert)
- Exposure and contrast adjustments with key repeat
- Temperature and tint controls
- Saturation, highlights, and shadows
- Quick rating and flagging
- Navigation between images

**Best For:** Film photographers who scan negatives and use Negative Lab Pro

---

### 2. Adobe Lightroom CC (`lightroom_cc.json`)
Optimized for Adobe Lightroom CC - photo editing and organization workflow.

**Key Features:**
- Module switching (Grid, Loupe, Compare, Survey, Develop)
- Image navigation with repeating keys
- Exposure, contrast, temperature, and tint adjustments
- Star ratings (1-5 stars) and color labels
- Crop, spot removal, and brush tools
- Quick copy/paste of adjustments
- Export functionality

**Best For:** Photographers using Lightroom for photo editing and organization

---

### 3. CapCut Desktop (`capcut_desktop.json`)
Optimized for CapCut Desktop - video editing workflow with timeline controls.

**Key Features:**
- Playback controls (Play/Pause, JKL controls)
- Timeline navigation (frame-by-frame, 10-frame jumps)
- Mark In/Out points and splitting
- Speed controls (25%, 50%, 100%, 150%, 200%)
- Quick access to text, stickers, audio, effects
- Transitions and filters
- Zoom controls with key repeat
- Copy/Paste and timeline management

**Best For:** Video editors using CapCut for content creation

---

### 4. OBS Studio (`obs_studio.json`)
Optimized for OBS Studio - streaming and recording controls with scene switching.

**Key Features:**
- Quick scene switching (Scenes 1-8)
- Start/Stop streaming and recording
- Microphone and desktop audio mute toggles
- Volume controls with key repeat (Mic and Desktop)
- Source visibility toggles (Sources 1-8)
- Filter controls
- Transition and studio mode
- Screenshot and replay buffer
- Settings and properties access

**Best For:** Streamers and content creators using OBS for broadcasting

---

## How to Import a Preset

### Method 1: Via Web Interface
1. Open Launchpad Mapper in your browser (http://localhost:5000)
2. Go to the **Profile Management** section
3. Click **Import Profile**
4. Navigate to the `presets/` directory
5. Select the preset JSON file you want to use
6. Click Open

The preset will be loaded and all mappings will appear on your Launchpad!

### Method 2: Via File System
1. Copy the desired preset JSON file
2. Load it directly through the import function in the web interface

---

## Customizing Presets

After importing a preset, you can:
- Modify any pad mapping to suit your workflow
- Change colors to match your preference
- Add or remove mappings
- Export your customized version as a new profile

---

## Creating Your Own Preset

To create a preset for a different application:

1. Start with a blank profile in Launchpad Mapper
2. Configure each pad with the appropriate keyboard shortcuts for your application
3. Choose meaningful colors and labels
4. Export the profile using the **Export Profile** button
5. Save the JSON file in the `presets/` directory with a descriptive name
6. (Optional) Add documentation to this README

---

## Tips for Using Presets

1. **Combine with Auto-Switch**: Set up automatic profile switching based on active window title
   - Example: When OBS is active, automatically load the OBS preset

2. **Use Layers**: Some workflows benefit from multiple layers
   - Base layer for primary controls
   - Additional layers for advanced features or different modes

3. **Key Repeat**: Pads with repeat enabled allow you to hold for continuous adjustment
   - Ideal for volume, exposure, zoom, and timeline navigation

4. **Color Coding**: Use consistent color schemes across presets
   - Red: Destructive actions (Delete, Stop, Reset)
   - Green: Positive actions (Start, Apply, Save)
   - Orange: Undo/Redo
   - Purple: Copy/Paste operations
   - Cyan: Navigation

---

## Contributing Presets

If you create a preset for a popular application, consider sharing it!

1. Test your preset thoroughly
2. Document the key mappings
3. Add a description section to this README
4. Submit your preset file

---

## Compatibility Notes

- All presets use standard keyboard shortcuts
- Some applications may require custom keyboard shortcut configuration to match the preset
- Shortcuts may vary between Windows, macOS, and Linux - adjust as needed
- Check your application's keyboard shortcut settings for conflicts

---

## Support

If you encounter issues with a preset:
1. Verify the application's keyboard shortcuts match the preset mappings
2. Check that your Launchpad is connected and the mapper is running
3. Use the "Test Key Combination" feature to verify shortcuts work

---

**Version:** 1.0
**Last Updated:** 2026-01-18
