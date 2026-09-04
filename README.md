# 🎬 One-Drama: AI Manhua & Manga Drama Auto-Dubbing OS

> **Automated End-to-End Localization, Dramatic AI Recap Dubbing, Remastering, and Cloud Publishing Pipeline for Chinese Dynamic Manhua.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#)
[![PyTorch CUDA](https://img.shields.io/badge/PyTorch-CUDA%20Accelerated-orange.svg)](#)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal.svg)](#)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-blue.svg)](#)

---

## 🌟 Key Architecture & Pipeline Stages

One-Drama transforms raw Chinese dynamic manhua episodes into viral, cinematic full-length recap movies with zero manual editing:

```
[ Raw Manhua Episodes (.mp4) ]
             │
             ▼
[ 1. Demucs v4 (CUDA) ] ────────► Separates Vocal & Instrumental BGM
             │
             ▼
[ 2. SenseVoice-Small ] ────────► Timestamped Chinese Speech Recognition
             │
             ▼
[ 3. Gemini 2.5 Flash ] ────────► Dramatic 3rd-Person Hindi Recap Script Adaptation
             │
             ▼
[ 4. F5-TTS / Edge-TTS ] ───────► Zero-Shot Emotional Voice Cloning + atempo Sync
             │
             ▼
[ 5. Remastering Engine ] ──────► 1.04x Zoom, -80px Subtitle Crop, Audio Ducking
             │
             ▼
[ 6. Master Compilation ] ──────► Lossless Full Movie Concat (.mp4)
             │
             ▼
[ 7. YouTube SEO Engine ] ──────► High-CTR Titles, Descriptions, Tags, Midjourney Prompts
             │
             ▼
[ 8. Google Drive Auto-Sync ] ──► Instant Desktop Cloud Upload
```

---

## 🚀 Key Features

- **Split & Retain Score:** Demucs strips original Chinese speech while keeping background scores and sound effects intact.
- **Ultra-Accurate Transcription:** Alibaba SenseVoice-Small + FSMN-VAD transcribe dialogue with millisecond precision.
- **Narrative Recap Adaptation:** Powered by Google Gemini 2.5 Flash with multi-key pool load-balancing to avoid rate limits.
- **Hyper-Realistic Voice Cloning:** F5-TTS Diffusion Flow Matching voices the recap with custom character references.
- **Visual Safety Filters:** 1.04x Lanczos zoom and -80px bottom crop eliminate source platform watermarks and hardcoded subtitles.
- **One-Click Publishing:** Generates YouTube viral metadata package and auto-syncs to Google Drive Desktop.
- **Full Web Studio:** Interactive web UI built with React, Vite, and Tailwind CSS.

---

## 🛠️ Project Structure

```
One-Drama/
├── one_drama_engine/          # Master Python Pipeline & Backend
│   ├── config/                # settings.json and configuration
│   ├── modules/               # Modular stages (demucs, transcriber, translator, tts, etc.)
│   ├── storage/               # Cache, processed stems, and master export
│   ├── pipeline.py            # Master CLI orchestration runner
│   ├── server.py              # FastAPI REST & WebSocket server
│   └── requirements.txt       # Python dependencies
└── web/                       # React + TypeScript Web Studio
    ├── src/                   # Studio UI components & hooks
    ├── package.json           # Frontend dependencies
    └── vite.config.ts         # Vite configuration
```

---

## ⚡ Quick Start

### 1. Engine Setup
```bash
cd one_drama_engine
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the template configuration:
```bash
cp config/settings.example.json config/settings.json
```
Edit `config/settings.json` and insert your Gemini API Key(s).

### 3. Run Pipeline
Place your raw video episodes into `storage/raw_episodes/` and execute:
```bash
python pipeline.py --keep-going --story-context "Your Story Title or Synopsis"
```

### 4. Run Web Studio
```bash
# Terminal 1: Backend
python server.py

# Terminal 2: Frontend
cd web
npm install
npm run dev
```

---

## 📜 License
MIT License. Created by [Ashik-Siddike](https://github.com/Ashik-Siddike).
