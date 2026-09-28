# Adaptive Reading Coach — MVP

An AI-powered oral reading coach and fluency assessment system for upper-primary students (Grades 3–5) in India, aligned with **NEP 2020** and **NIPUN Bharat** foundational literacy benchmarks.

---

## 🎙️ Speech-to-Text (STT) Architecture & Clarification

> **Important Architecture Notice**:
> This system uses **authoritative backend Speech-to-Text (STT)** rather than browser `SpeechRecognition`.
> - **The single source of truth for student reading is the raw audio recorded by `MediaRecorder`.**
> - The recorded audio is streamed/uploaded directly to the FastAPI backend, where **Whisper (via Groq LPU or OpenAI)** transcribes it with sub-second word-level timestamp boundaries.
> - **Groq or OpenAI STT credentials MUST be configured in `backend/.env` before expecting transcription.** (The system will deliberately return an explicit `STT_NOT_CONFIGURED` configuration error instead of silently generating fake/simulated readings).

---

## 🛠️ Recommended 5-Step Debugging Order

If you experience audio, microphone, or transcription issues, follow this exact sequence:

1. **Verify Context (Origin Security)**:
   - Ensure you are accessing the app via `http://localhost:3000` or an HTTPS origin.
   - **Insecure origins (e.g. `http://192.168.x.x:3000`) are permanently blocked by browsers** from invoking `navigator.mediaDevices.getUserMedia()`.
2. **Check Browser Microphone Permission & Device Selection**:
   - Click the lock/tune icon next to the address bar in your browser and confirm **Microphone: Allow**.
   - In the **Input Device** dropdown, confirm your desired physical microphone is selected (defaults to "System Default Microphone").
3. **Watch the Real-Time RMS / dBFS Signal Meter While Speaking**:
   - Click **Start Reading Aloud** and speak.
   - The meter must show active signal: `🟢 Audio Signal Active` with `RMS > 0.005` (typically `-35 dBFS` to `-15 dBFS`).
   - If it displays `⚠️ No Audio Detected (RMS: 0.000 • -∞ dBFS)`, check your physical mic switch or Linux sound mixer (e.g. `pavucontrol` under *Input Devices*).
4. **Check the Logged Hardware `MediaTrackSettings`**:
   - The UI displays the active sample rate and channel count (e.g. `SR: 48000 Hz • CH: 1 • ACTIVE`).
   - Verify the state is `ACTIVE` and **not** `MUTED`. If the OS or hardware has muted the stream, the UI surfaces a prominent `HARDWARE/OS MUTE DETECTED` alert.
5. **Verify the Backend STT API Key**:
   - Only after confirming that microphone audio is captured (RMS meter active), ensure your `GROQ_API_KEY` is configured in `backend/.env`.

---

## 🚀 Quick Setup & Configuration

### 1. Configure Backend Environment (`backend/.env`)

Copy `.env.example`:
```bash
cd /home/noel/Documents/notsanako/backend
cp .env.example .env
```

Add your API keys:
```env
# 1. Speech-to-Text: Get a fast, free Groq API key at https://console.groq.com
GROQ_API_KEY=gsk_your_groq_api_key_here

# 2. Remediation Story Synthesis: Get a Gemini key at https://aistudio.google.com
GEMINI_API_KEY=your_gemini_api_key_here

# 3. Optional: Resend API key for teacher email summaries at https://resend.com
RESEND_API_KEY=re_your_resend_key_here
```

### 2. Start the Backend (FastAPI)

```bash
cd /home/noel/Documents/notsanako/backend
chmod +x run.sh
./run.sh
```
*API will run at `http://localhost:8000` (interactive Swagger docs at `http://localhost:8000/docs`).*

### 3. Start the Frontend (Next.js PWA)

```bash
cd /home/noel/Documents/notsanako/frontend
npm run dev
```
*Open `http://localhost:3000` in Chrome, Edge, or Firefox.*

---

## 🌟 The Closed-Loop Student Remediation Cycle

```text
Baseline Reading (16kHz Audio)
       │
       ▼
Indic Linguistic Diagnosis (Matra, Conjunct, Phonetic, WCPM, Pauses >1.5s, 3+ Stumble Clusters)
       │
       ▼
Pedagogical Error Ranking (Top 3-5 Priority Target Words)
       │
       ▼
Personalized Remediation Story Generation (Gemini, OpenAI, then Groq: 60-80 words, target words embedded 1-2x; shows an error if all providers fail)
       │
       ▼
Retest Reading (MediaRecorder Audio Captured)
       │
       ▼
Mastery Delta Report (Δ = Post-test Target Word Accuracy − Baseline Target Word Accuracy)
```

---

## 📁 Repository Cleanliness & Maintenance

- Tracked cache files (`__pycache__/*.pyc`) and SQLite database files (`*.db`) are strictly excluded from version control via `.gitignore`.
