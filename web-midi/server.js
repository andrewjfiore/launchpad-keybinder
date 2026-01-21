import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { promises as fs } from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const dataDir = path.join(__dirname, "data");
const profilePath = path.join(dataDir, "profile.json");
const port = process.env.PORT || 5001;

const defaultProfile = {
  name: "Default",
  description: "Web MIDI profile",
  mappings: {}
};

app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

async function ensureDataDir() {
  await fs.mkdir(dataDir, { recursive: true });
}

async function loadProfile() {
  try {
    const contents = await fs.readFile(profilePath, "utf-8");
    return JSON.parse(contents);
  } catch (error) {
    return { ...defaultProfile };
  }
}

async function saveProfile(profile) {
  await ensureDataDir();
  const payload = JSON.stringify(profile, null, 2);
  await fs.writeFile(profilePath, payload, "utf-8");
}

app.get("/api/profile", async (_req, res) => {
  const profile = await loadProfile();
  res.json(profile);
});

app.post("/api/profile", async (req, res) => {
  const profile = req.body;
  if (!profile || typeof profile !== "object") {
    res.status(400).json({ error: "Invalid profile payload" });
    return;
  }
  await saveProfile(profile);
  res.json({ ok: true });
});

app.get("/api/profile/export", async (_req, res) => {
  const profile = await loadProfile();
  res.json(profile);
});

app.post("/api/profile/import", async (req, res) => {
  const profile = req.body;
  if (!profile || typeof profile !== "object") {
    res.status(400).json({ error: "Invalid profile payload" });
    return;
  }
  await saveProfile(profile);
  res.json({ ok: true });
});

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.listen(port, () => {
  console.log(`Web MIDI server listening on http://localhost:${port}`);
});
