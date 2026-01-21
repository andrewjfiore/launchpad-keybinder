const LAUNCHPAD_COLORS = {
  off: 0,
  white: 3,
  red: 5,
  red_dim: 7,
  orange: 9,
  orange_dim: 11,
  yellow: 13,
  yellow_dim: 15,
  lime: 17,
  lime_dim: 19,
  green: 21,
  green_dim: 23,
  spring: 29,
  spring_dim: 27,
  cyan: 37,
  cyan_dim: 35,
  sky: 41,
  sky_dim: 39,
  blue: 45,
  blue_dim: 43,
  purple: 49,
  purple_dim: 47,
  magenta: 53,
  magenta_dim: 51,
  pink: 57,
  pink_dim: 55,
  coral: 61,
  coral_dim: 59,
  amber: 65,
  amber_dim: 63
};

const COLOR_HEX = {
  off: "#333333",
  white: "#FFFFFF",
  red: "#FF0000",
  red_dim: "#800000",
  orange: "#FF8000",
  orange_dim: "#804000",
  yellow: "#FFFF00",
  yellow_dim: "#808000",
  lime: "#80FF00",
  lime_dim: "#408000",
  green: "#00FF00",
  green_dim: "#008000",
  spring: "#00FF80",
  spring_dim: "#008040",
  cyan: "#00FFFF",
  cyan_dim: "#008080",
  sky: "#0080FF",
  sky_dim: "#004080",
  blue: "#0000FF",
  blue_dim: "#000080",
  purple: "#8000FF",
  purple_dim: "#400080",
  magenta: "#FF00FF",
  magenta_dim: "#800080",
  pink: "#FF0080",
  pink_dim: "#800040",
  coral: "#FF4040",
  coral_dim: "#802020",
  amber: "#FFBF00",
  amber_dim: "#806000"
};

const midiStatus = document.getElementById("midi-status");
const midiInputSelect = document.getElementById("midi-input");
const midiOutputSelect = document.getElementById("midi-output");
const refreshButton = document.getElementById("refresh-midi");
const connectButton = document.getElementById("connect-midi");
const padGrid = document.getElementById("pad-grid");
const eventLog = document.getElementById("event-log");
const selectedNote = document.getElementById("selected-note");
const mappingLabel = document.getElementById("mapping-label");
const mappingKey = document.getElementById("mapping-key");
const mappingColor = document.getElementById("mapping-color");
const mappingEnabled = document.getElementById("mapping-enabled");
const saveMappingButton = document.getElementById("save-mapping");
const clearMappingButton = document.getElementById("clear-mapping");
const profileName = document.getElementById("profile-name");
const profileDescription = document.getElementById("profile-description");
const saveProfileButton = document.getElementById("save-profile");
const exportProfileButton = document.getElementById("export-profile");
const importProfileInput = document.getElementById("import-profile");

const mainColors = Object.keys(COLOR_HEX).filter((color) => !color.includes("dim"));

let midiAccess;
let activeInput;
let activeOutput;
let currentNote = null;
let profile = {
  name: "Default",
  description: "Web MIDI profile",
  mappings: {}
};

const padButtons = new Map();

function buildGrid() {
  padGrid.innerHTML = "";
  const rows = [];
  for (let row = 8; row >= 1; row -= 1) {
    const notes = [];
    for (let col = 1; col <= 8; col += 1) {
      notes.push(row * 10 + col);
    }
    rows.push(notes);
  }

  rows.forEach((rowNotes) => {
    rowNotes.forEach((note) => {
      const button = document.createElement("button");
      button.className = "pad";
      button.dataset.note = String(note);
      button.textContent = note;
      button.addEventListener("click", () => selectNote(note));
      padGrid.appendChild(button);
      padButtons.set(note, button);
    });
  });
}

function populateColors() {
  mappingColor.innerHTML = "";
  mainColors.forEach((color) => {
    const option = document.createElement("option");
    option.value = color;
    option.textContent = color;
    mappingColor.appendChild(option);
  });
}

function logEvent(message) {
  const entry = document.createElement("div");
  entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  eventLog.prepend(entry);
}

function updateStatus(text) {
  midiStatus.textContent = `MIDI: ${text}`;
}

function updatePadVisual(note) {
  const mapping = profile.mappings[String(note)];
  const pad = padButtons.get(note);
  if (!pad) {
    return;
  }
  const colorName = mapping?.color || "off";
  pad.style.background = COLOR_HEX[colorName] || "#333";
  pad.classList.toggle("disabled", mapping?.enabled === false);
}

function refreshPadGrid() {
  padButtons.forEach((_value, note) => updatePadVisual(note));
}

function selectNote(note) {
  currentNote = note;
  selectedNote.textContent = String(note);
  const mapping = profile.mappings[String(note)];
  mappingLabel.value = mapping?.label ?? "";
  mappingKey.value = mapping?.key_combo ?? "";
  mappingColor.value = mapping?.color ?? "green";
  mappingEnabled.checked = mapping?.enabled ?? true;
  padButtons.forEach((button) => button.classList.remove("selected"));
  padButtons.get(note)?.classList.add("selected");
}

function saveMapping() {
  if (!currentNote) {
    return;
  }
  profile.mappings[String(currentNote)] = {
    note: currentNote,
    label: mappingLabel.value.trim(),
    key_combo: mappingKey.value.trim(),
    color: mappingColor.value,
    enabled: mappingEnabled.checked
  };
  updatePadVisual(currentNote);
  sendPadColor(currentNote);
  persistProfile();
}

function clearMapping() {
  if (!currentNote) {
    return;
  }
  delete profile.mappings[String(currentNote)];
  updatePadVisual(currentNote);
  persistProfile();
}

function renderProfile() {
  profileName.value = profile.name || "";
  profileDescription.value = profile.description || "";
  refreshPadGrid();
}

function updateProfileMeta() {
  profile.name = profileName.value.trim() || "Default";
  profile.description = profileDescription.value.trim();
  persistProfile();
}

async function persistProfile() {
  await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile)
  });
}

function triggerKeyCombo(combo) {
  if (!combo) {
    return;
  }
  const parts = combo.toLowerCase().split("+").map((part) => part.trim()).filter(Boolean);
  if (!parts.length) {
    return;
  }
  const modifiers = new Set(["shift", "ctrl", "control", "alt", "meta", "cmd", "command"]);
  const keyPart = parts.find((part) => !modifiers.has(part)) || parts[parts.length - 1];
  const eventInit = {
    key: keyPart,
    ctrlKey: parts.includes("ctrl") || parts.includes("control"),
    shiftKey: parts.includes("shift"),
    altKey: parts.includes("alt"),
    metaKey: parts.includes("meta") || parts.includes("cmd") || parts.includes("command"),
    bubbles: true
  };
  document.dispatchEvent(new KeyboardEvent("keydown", eventInit));
  document.dispatchEvent(new KeyboardEvent("keyup", eventInit));
  logEvent(`Triggered key combo: ${combo}`);
}

function sendPadColor(note, overrideColor) {
  if (!activeOutput) {
    return;
  }
  const mapping = profile.mappings[String(note)];
  const colorName = overrideColor || mapping?.color || "off";
  const velocity = LAUNCHPAD_COLORS[colorName] ?? 0;
  activeOutput.send([0x90, note, velocity]);
}

function handleMidiMessage(event) {
  const [status, note, velocity] = event.data;
  const messageType = status & 0xf0;
  if (messageType !== 0x90 && messageType !== 0x80) {
    return;
  }
  const isNoteOn = messageType === 0x90 && velocity > 0;
  const pad = padButtons.get(note);
  if (pad) {
    pad.classList.toggle("active", isNoteOn);
  }
  logEvent(`MIDI ${isNoteOn ? "Note On" : "Note Off"}: ${note}`);
  if (isNoteOn) {
    const mapping = profile.mappings[String(note)];
    if (mapping?.enabled !== false) {
      triggerKeyCombo(mapping?.key_combo);
      sendPadColor(note, "white");
    }
  } else {
    sendPadColor(note);
  }
}

function clearMidiHandlers() {
  if (activeInput) {
    activeInput.onmidimessage = null;
  }
}

function connectMidi() {
  clearMidiHandlers();
  const inputId = midiInputSelect.value;
  const outputId = midiOutputSelect.value;
  activeInput = midiAccess?.inputs.get(inputId) || null;
  activeOutput = midiAccess?.outputs.get(outputId) || null;
  if (activeInput) {
    activeInput.onmidimessage = handleMidiMessage;
  }
  if (activeOutput) {
    refreshPadGrid();
  }
  updateStatus(activeInput ? "Connected" : "No input selected");
}

function populatePorts() {
  midiInputSelect.innerHTML = "";
  midiOutputSelect.innerHTML = "";
  if (!midiAccess) {
    return;
  }
  midiAccess.inputs.forEach((input) => {
    const option = document.createElement("option");
    option.value = input.id;
    option.textContent = input.name || `Input ${input.id}`;
    midiInputSelect.appendChild(option);
  });
  midiAccess.outputs.forEach((output) => {
    const option = document.createElement("option");
    option.value = output.id;
    option.textContent = output.name || `Output ${output.id}`;
    midiOutputSelect.appendChild(option);
  });
}

async function requestMidiAccess() {
  if (!navigator.requestMIDIAccess) {
    updateStatus("Web MIDI not supported");
    return;
  }
  midiAccess = await navigator.requestMIDIAccess({ sysex: true });
  populatePorts();
  updateStatus("Ready");
}

async function loadProfile() {
  const response = await fetch("/api/profile");
  if (!response.ok) {
    return;
  }
  profile = await response.json();
  if (!profile.mappings) {
    profile.mappings = {};
  }
  renderProfile();
}

function exportProfile() {
  const payload = JSON.stringify(profile, null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${profile.name || "profile"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function importProfile(file) {
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const parsed = JSON.parse(reader.result);
      profile = {
        name: parsed.name || "Imported",
        description: parsed.description || "",
        mappings: parsed.mappings || {}
      };
      renderProfile();
      await persistProfile();
      logEvent("Imported profile JSON");
    } catch (error) {
      logEvent("Failed to import profile JSON");
    }
  };
  reader.readAsText(file);
}

refreshButton.addEventListener("click", requestMidiAccess);
connectButton.addEventListener("click", connectMidi);
saveMappingButton.addEventListener("click", saveMapping);
clearMappingButton.addEventListener("click", clearMapping);
saveProfileButton.addEventListener("click", updateProfileMeta);
exportProfileButton.addEventListener("click", exportProfile);
importProfileInput.addEventListener("change", (event) => {
  importProfile(event.target.files[0]);
});

buildGrid();
populateColors();
requestMidiAccess();
loadProfile();
